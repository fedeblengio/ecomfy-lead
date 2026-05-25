import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def seeded_client(client):
    client.post("/seed")
    return client


def make_lead(**overrides):
    base = {
        "first_name": "Test",
        "last_name": "User",
        "phone": "3059999999",
        "email": "test@example.com",
        "state": "FL",
        "vertical": "Life Insurance",
        "source": "google_ads",
        "trusted_form_cert_url": "https://cert.trustedform.com/test123",
    }
    base.update(overrides)
    return base


# Test 1: Lead válido vendido al primer buyer
def test_valid_lead_sold_to_first_buyer(seeded_client):
    resp = seeded_client.post("/leads", json=make_lead())
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sold"
    assert data["assigned_buyer_id"] is not None
    assert data["sold_price"] is not None


# Test 2: Lead sold after first eligible buyer rejects (fallback through ping tree)
def test_lead_sold_after_first_buyer_rejection(seeded_client):
    # Send a lead with vertical="Auto Insurance" and state="FL"
    # Buyer B (priority 1): allowed_verticals=["Life Insurance","Health Insurance"] -> NOT eligible
    # Buyer C (priority 2): allowed_verticals=["Life Insurance","Auto Insurance"] -> eligible but TIMEOUT
    # Buyer A (priority 3): allowed_verticals=["Life Insurance","Health Insurance","Auto Insurance"] -> accepts
    # This proves the ping tree falls through rejected/timed-out buyers to the next eligible one.
    resp = seeded_client.post("/leads", json=make_lead(
        phone="3058888888", email="fallback@example.com",
        vertical="Auto Insurance",
    ))
    data = resp.json()
    assert data["status"] == "sold"
    # Buyer C timed out, so buyer A should have accepted
    assert data["assigned_buyer_id"] == "buyer-a"


# Test 3: Lead duplicado rechazado
def test_duplicate_lead_rejected(seeded_client):
    resp1 = seeded_client.post("/leads", json=make_lead())
    assert resp1.json()["status"] == "sold"

    resp2 = seeded_client.post("/leads", json=make_lead())
    data = resp2.json()
    assert data["status"] == "rejected"
    assert "duplicate" in data["rejection_reason"].lower()


# Test 4: Lead sin email rechazado
def test_lead_without_valid_email_rejected(seeded_client):
    resp = seeded_client.post("/leads", json=make_lead(email="not-an-email"))
    assert resp.status_code == 422


# Test 5: Buyer sin balance descartado
def test_buyer_without_balance_skipped(seeded_client):
    resp = seeded_client.post("/leads", json=make_lead())
    data = resp.json()
    assert data["assigned_buyer_id"] != "buyer-d"


# Test 6: Buyer con cap lleno descartado
def test_buyer_with_full_cap_skipped(seeded_client):
    resp = seeded_client.post("/leads", json=make_lead())
    data = resp.json()
    assert data["assigned_buyer_id"] != "buyer-e"


# Test 7: Buyer timeout y fallback
def test_buyer_timeout_triggers_fallback(seeded_client):
    resp = seeded_client.post("/leads", json=make_lead(
        vertical="Auto Insurance",
        phone="3057777777",
        email="timeout_test@example.com",
    ))
    data = resp.json()
    assert data["status"] == "sold"
    assert data["assigned_buyer_id"] != "buyer-c"


# Test 8: Lead sold devuelto con refund
def test_sold_lead_returned_with_refund(seeded_client):
    resp = seeded_client.post("/leads", json=make_lead())
    lead_id = resp.json()["lead_id"]
    buyer_id = resp.json()["assigned_buyer_id"]
    assert resp.json()["status"] == "sold"

    buyers = seeded_client.get("/buyers").json()
    buyer_balance_after_sale = next(b["balance"] for b in buyers if b["buyer_id"] == buyer_id)

    ret_resp = seeded_client.post(f"/leads/{lead_id}/return", json={"reason": "bad quality"})
    assert ret_resp.json()["status"] == "returned"

    buyers_after = seeded_client.get("/buyers").json()
    buyer_balance_after_refund = next(b["balance"] for b in buyers_after if b["buyer_id"] == buyer_id)
    assert buyer_balance_after_refund > buyer_balance_after_sale


# Test 9: Cannot return a non-sold lead
def test_cannot_return_non_sold_lead(seeded_client):
    seeded_client.post("/leads", json=make_lead())
    resp = seeded_client.post("/leads", json=make_lead())
    lead_id = resp.json()["lead_id"]

    ret_resp = seeded_client.post(f"/leads/{lead_id}/return", json={"reason": "test"})
    assert ret_resp.status_code == 400


# Test 10: Lead missing cert and jornaya rejected
def test_lead_missing_cert_rejected(seeded_client):
    lead = make_lead()
    del lead["trusted_form_cert_url"]
    resp = seeded_client.post("/leads", json=lead)
    data = resp.json()
    assert data["status"] == "rejected"
    assert "trusted_form" in data["rejection_reason"].lower() or "jornaya" in data["rejection_reason"].lower()


# Test 11: Daily summary report works
def test_daily_summary_report(seeded_client):
    seeded_client.post("/leads", json=make_lead())
    seeded_client.post("/leads", json=make_lead(
        phone="3056666666", email="another@example.com"
    ))

    resp = seeded_client.get("/reports/daily-summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_leads_received"] >= 2
    assert data["sold_leads"] >= 1
    assert data["gross_revenue"] > 0


# Test 12: Alerts are generated
def test_alerts_generated(seeded_client):
    seeded_client.post("/leads", json=make_lead())
    seeded_client.post("/leads", json=make_lead())

    resp = seeded_client.get("/alerts")
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) > 0
