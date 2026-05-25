# EcomfyApp Mini Lead Routing Engine — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an MVP lead routing engine that receives leads via API, validates them, distributes to buyers via ping tree, manages balances/ledger, handles returns, and generates reports with alerts.

**Architecture:** FastAPI monolith with SQLite via SQLAlchemy. Services layer separates validation, routing, delivery simulation, ledger, and alerts. Buyer webhook behavior is simulated in-process.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Pydantic, pytest, OpenAI API, Slack webhooks, uvicorn.

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `app/__init__.py`
- Create: `app/database.py`
- Create: `tests/__init__.py`

**Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
pydantic[email]==2.9.0
pydantic-settings==2.5.0
python-dotenv==1.0.1
httpx==0.27.0
openai==1.50.0
pytest==8.3.0
```

**Step 2: Create .env.example**

```
DATABASE_URL=sqlite:///./ecomfy.db
OPENAI_API_KEY=sk-your-key-here
SLACK_WEBHOOK_URL=
BUYER_TIMEOUT_SECONDS=3
```

**Step 3: Create .gitignore**

```
__pycache__/
*.pyc
.env
*.db
.pytest_cache/
venv/
```

**Step 4: Create app/database.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ecomfy.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Step 5: Create empty __init__.py files**

Empty files for `app/__init__.py` and `tests/__init__.py`.

**Step 6: Install dependencies and verify**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully.

**Step 7: Commit**

```bash
git add requirements.txt .env.example .gitignore app/ tests/
git commit -m "feat: project scaffolding with FastAPI + SQLAlchemy"
```

---

### Task 2: SQLAlchemy models

**Files:**
- Create: `app/models.py`

**Step 1: Create all models**

```python
import uuid
from datetime import datetime, time
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, Time,
    ForeignKey, JSON, Text
)
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Lead(Base):
    __tablename__ = "leads"

    lead_id = Column(String, primary_key=True, default=generate_uuid)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    email = Column(String, nullable=False)
    state = Column(String, nullable=False)
    vertical = Column(String, nullable=False)
    source = Column(String, nullable=False)
    trusted_form_cert_url = Column(String, nullable=True)
    jornaya_lead_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    rejection_reason = Column(String, nullable=True)
    assigned_buyer_id = Column(String, ForeignKey("buyers.buyer_id"), nullable=True)
    sold_price = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    delivery_attempts = relationship("DeliveryAttempt", back_populates="lead")
    assigned_buyer = relationship("Buyer", back_populates="leads")


class Buyer(Base):
    __tablename__ = "buyers"

    buyer_id = Column(String, primary_key=True, default=generate_uuid)
    buyer_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    balance = Column(Float, nullable=False, default=0.0)
    daily_cap = Column(Integer, nullable=False, default=10)
    leads_received_today = Column(Integer, nullable=False, default=0)
    allowed_states = Column(JSON, nullable=False, default=list)
    allowed_verticals = Column(JSON, nullable=False, default=list)
    schedule_start = Column(String, nullable=False, default="08:00")
    schedule_end = Column(String, nullable=False, default="20:00")
    campaign_active = Column(Boolean, nullable=False, default=True)
    ping_tree_assigned = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=1)
    price_per_lead = Column(Float, nullable=False, default=10.0)
    webhook_behavior = Column(String, nullable=False, default="accept")

    leads = relationship("Lead", back_populates="assigned_buyer")
    delivery_attempts = relationship("DeliveryAttempt", back_populates="buyer")
    ledger_entries = relationship("LedgerEntry", back_populates="buyer")


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"

    attempt_id = Column(String, primary_key=True, default=generate_uuid)
    lead_id = Column(String, ForeignKey("leads.lead_id"), nullable=False)
    buyer_id = Column(String, ForeignKey("buyers.buyer_id"), nullable=False)
    attempt_order = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    rejection_reason = Column(String, nullable=True)
    latency_ms = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="delivery_attempts")
    buyer = relationship("Buyer", back_populates="delivery_attempts")


class LedgerEntry(Base):
    __tablename__ = "ledger"

    transaction_id = Column(String, primary_key=True, default=generate_uuid)
    buyer_id = Column(String, ForeignKey("buyers.buyer_id"), nullable=False)
    lead_id = Column(String, ForeignKey("leads.lead_id"), nullable=False)
    type = Column(String, nullable=False)  # debit | refund
    amount = Column(Float, nullable=False)
    balance_before = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    buyer = relationship("Buyer", back_populates="ledger_entries")


class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(String, primary_key=True, default=generate_uuid)
    severity = Column(String, nullable=False)  # info | warning | critical
    entity_id = Column(String, nullable=False)
    message = Column(String, nullable=False)
    suggested_action = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
```

**Step 2: Verify models load**

Run: `python -c "from app.models import Lead, Buyer, DeliveryAttempt, LedgerEntry, Alert; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add app/models.py
git commit -m "feat: add SQLAlchemy models for leads, buyers, delivery_attempts, ledger, alerts"
```

---

### Task 3: Pydantic schemas

**Files:**
- Create: `app/schemas.py`

**Step 1: Create all request/response schemas**

```python
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
import re


class LeadCreate(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: EmailStr
    state: str
    vertical: str
    source: str
    trusted_form_cert_url: Optional[str] = None
    jornaya_lead_id: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        cleaned = re.sub(r"[\s\-\(\)\.]", "", v)
        if not re.match(r"^\+?1?\d{10}$", cleaned):
            raise ValueError("Invalid phone number")
        return cleaned


class LeadResponse(BaseModel):
    lead_id: str
    first_name: str
    last_name: str
    phone: str
    email: str
    state: str
    vertical: str
    source: str
    trusted_form_cert_url: Optional[str]
    jornaya_lead_id: Optional[str]
    status: str
    rejection_reason: Optional[str]
    assigned_buyer_id: Optional[str]
    sold_price: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class LeadReturnRequest(BaseModel):
    reason: str


class BuyerResponse(BaseModel):
    buyer_id: str
    buyer_name: str
    status: str
    balance: float
    daily_cap: int
    leads_received_today: int
    allowed_states: list
    allowed_verticals: list
    schedule_start: str
    schedule_end: str
    campaign_active: bool
    ping_tree_assigned: bool
    priority: int
    price_per_lead: float
    webhook_behavior: str

    class Config:
        from_attributes = True


class BuyerEvaluation(BaseModel):
    buyer_id: str
    buyer_name: str
    eligible: bool
    reason_if_not_eligible: Optional[str] = None


class DeliveryAttemptResponse(BaseModel):
    attempt_id: str
    lead_id: str
    buyer_id: str
    attempt_order: int
    status: str
    rejection_reason: Optional[str]
    latency_ms: int
    created_at: datetime

    class Config:
        from_attributes = True


class DailySummary(BaseModel):
    total_leads_received: int
    rejected_leads: int
    sold_leads: int
    unsold_leads: int
    returned_leads: int
    gross_revenue: float
    refunds: float
    net_revenue: float
    top_buyer_by_spend: Optional[str]
    buyers_with_low_balance: list[str]
    buyers_with_cap_reached: list[str]
    top_rejection_reasons: list[dict]
    average_routing_latency_ms: float
    ai_summary: Optional[str] = None


class AlertResponse(BaseModel):
    alert_id: str
    severity: str
    entity_id: str
    message: str
    suggested_action: str
    created_at: datetime

    class Config:
        from_attributes = True
```

**Step 2: Verify schemas load**

Run: `python -c "from app.schemas import LeadCreate, LeadResponse; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add app/schemas.py
git commit -m "feat: add Pydantic schemas for API request/response"
```

---

### Task 4: Seed data

**Files:**
- Create: `app/seed.py`

**Step 1: Create seed function with 10 leads and 5 buyers**

```python
from app.models import Lead, Buyer
from sqlalchemy.orm import Session


def seed_buyers(db: Session):
    buyers = [
        Buyer(
            buyer_id="buyer-a",
            buyer_name="Buyer A - Always Accepts",
            status="active",
            balance=500.0,
            daily_cap=20,
            leads_received_today=0,
            allowed_states=["FL", "TX", "CA", "NY", "OH"],
            allowed_verticals=["Life Insurance", "Health Insurance", "Auto Insurance"],
            schedule_start="00:00",
            schedule_end="23:59",
            campaign_active=True,
            ping_tree_assigned=True,
            priority=3,
            price_per_lead=25.0,
            webhook_behavior="accept",
        ),
        Buyer(
            buyer_id="buyer-b",
            buyer_name="Buyer B - Rejects Duplicates",
            status="active",
            balance=300.0,
            daily_cap=15,
            leads_received_today=0,
            allowed_states=["FL", "TX", "CA"],
            allowed_verticals=["Life Insurance", "Health Insurance"],
            schedule_start="00:00",
            schedule_end="23:59",
            campaign_active=True,
            ping_tree_assigned=True,
            priority=1,
            price_per_lead=30.0,
            webhook_behavior="reject_duplicate",
        ),
        Buyer(
            buyer_id="buyer-c",
            buyer_name="Buyer C - Timeout",
            status="active",
            balance=400.0,
            daily_cap=10,
            leads_received_today=0,
            allowed_states=["FL", "TX", "NY"],
            allowed_verticals=["Life Insurance", "Auto Insurance"],
            schedule_start="00:00",
            schedule_end="23:59",
            campaign_active=True,
            ping_tree_assigned=True,
            priority=2,
            price_per_lead=20.0,
            webhook_behavior="timeout",
        ),
        Buyer(
            buyer_id="buyer-d",
            buyer_name="Buyer D - Low Balance",
            status="active",
            balance=5.0,
            daily_cap=10,
            leads_received_today=0,
            allowed_states=["FL", "TX", "CA", "NY"],
            allowed_verticals=["Life Insurance", "Health Insurance", "Auto Insurance"],
            schedule_start="00:00",
            schedule_end="23:59",
            campaign_active=True,
            ping_tree_assigned=True,
            priority=4,
            price_per_lead=25.0,
            webhook_behavior="accept",
        ),
        Buyer(
            buyer_id="buyer-e",
            buyer_name="Buyer E - Cap Full / Inactive",
            status="active",
            balance=600.0,
            daily_cap=5,
            leads_received_today=5,
            allowed_states=["FL", "TX", "CA", "NY", "OH"],
            allowed_verticals=["Life Insurance", "Health Insurance"],
            schedule_start="00:00",
            schedule_end="23:59",
            campaign_active=False,
            ping_tree_assigned=True,
            priority=5,
            price_per_lead=15.0,
            webhook_behavior="accept",
        ),
    ]
    for buyer in buyers:
        existing = db.query(Buyer).filter_by(buyer_id=buyer.buyer_id).first()
        if not existing:
            db.add(buyer)
    db.commit()
    return buyers


def seed_leads():
    return [
        {
            "first_name": "John",
            "last_name": "Smith",
            "phone": "3051234567",
            "email": "john.smith@example.com",
            "state": "FL",
            "vertical": "Life Insurance",
            "source": "google_ads",
            "trusted_form_cert_url": "https://cert.trustedform.com/abc123",
        },
        {
            "first_name": "Maria",
            "last_name": "Garcia",
            "phone": "7131234567",
            "email": "maria.garcia@example.com",
            "state": "TX",
            "vertical": "Health Insurance",
            "source": "facebook",
            "jornaya_lead_id": "jorn-001",
        },
        {
            "first_name": "James",
            "last_name": "Johnson",
            "phone": "2121234567",
            "email": "james.j@example.com",
            "state": "NY",
            "vertical": "Auto Insurance",
            "source": "organic",
            "trusted_form_cert_url": "https://cert.trustedform.com/def456",
        },
        {
            "first_name": "Sarah",
            "last_name": "Williams",
            "phone": "4151234567",
            "email": "sarah.w@example.com",
            "state": "CA",
            "vertical": "Life Insurance",
            "source": "referral",
            "jornaya_lead_id": "jorn-002",
        },
        {
            "first_name": "Robert",
            "last_name": "Brown",
            "phone": "6141234567",
            "email": "robert.b@example.com",
            "state": "OH",
            "vertical": "Health Insurance",
            "source": "google_ads",
            "trusted_form_cert_url": "https://cert.trustedform.com/ghi789",
        },
        {
            "first_name": "Emily",
            "last_name": "Davis",
            "phone": "3052345678",
            "email": "emily.d@example.com",
            "state": "FL",
            "vertical": "Life Insurance",
            "source": "facebook",
            "jornaya_lead_id": "jorn-003",
        },
        {
            "first_name": "Michael",
            "last_name": "Wilson",
            "phone": "7132345678",
            "email": "michael.w@example.com",
            "state": "TX",
            "vertical": "Auto Insurance",
            "source": "organic",
            "trusted_form_cert_url": "https://cert.trustedform.com/jkl012",
        },
        {
            "first_name": "Jennifer",
            "last_name": "Martinez",
            "phone": "2122345678",
            "email": "jennifer.m@example.com",
            "state": "NY",
            "vertical": "Life Insurance",
            "source": "google_ads",
            "jornaya_lead_id": "jorn-004",
        },
        {
            "first_name": "David",
            "last_name": "Anderson",
            "phone": "4152345678",
            "email": "david.a@example.com",
            "state": "CA",
            "vertical": "Health Insurance",
            "source": "referral",
            "trusted_form_cert_url": "https://cert.trustedform.com/mno345",
        },
        {
            "first_name": "Lisa",
            "last_name": "Taylor",
            "phone": "3051234567",  # duplicate phone of lead 1
            "email": "lisa.t@example.com",
            "state": "FL",
            "vertical": "Life Insurance",
            "source": "facebook",
            "jornaya_lead_id": "jorn-005",
        },
    ]
```

**Step 2: Verify seed loads**

Run: `python -c "from app.seed import seed_leads, seed_buyers; print(f'{len(seed_leads())} leads ready')"`
Expected: `10 leads ready`

**Step 3: Commit**

```bash
git add app/seed.py
git commit -m "feat: add seed data with 10 leads and 5 buyers"
```

---

### Task 5: Validation service

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/validation.py`
- Create: `tests/test_validation.py`

**Step 1: Write failing tests**

```python
# tests/test_validation.py
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from app.services.validation import validate_lead


def make_lead_data(**overrides):
    base = {
        "first_name": "John",
        "last_name": "Doe",
        "phone": "3051234567",
        "email": "john@example.com",
        "state": "FL",
        "vertical": "Life Insurance",
        "source": "google_ads",
        "trusted_form_cert_url": "https://cert.trustedform.com/abc",
    }
    base.update(overrides)
    return base


def test_valid_lead_passes():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    result = validate_lead(make_lead_data(), db)
    assert result is None  # None means no error


def test_missing_state_rejected():
    db = MagicMock()
    result = validate_lead(make_lead_data(state=""), db)
    assert result == "state is required"


def test_missing_vertical_rejected():
    db = MagicMock()
    result = validate_lead(make_lead_data(vertical=""), db)
    assert result == "vertical is required"


def test_missing_source_rejected():
    db = MagicMock()
    result = validate_lead(make_lead_data(source=""), db)
    assert result == "source is required"


def test_missing_cert_and_jornaya_rejected():
    db = MagicMock()
    data = make_lead_data(trusted_form_cert_url=None)
    data.pop("jornaya_lead_id", None)
    result = validate_lead(data, db)
    assert result == "trusted_form_cert_url or jornaya_lead_id is required"


def test_duplicate_phone_rejected():
    db = MagicMock()
    existing = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing
    result = validate_lead(make_lead_data(), db)
    assert "duplicate" in result.lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_validation.py -v`
Expected: FAIL (module not found)

**Step 3: Implement validation service**

```python
# app/services/validation.py
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models import Lead


def validate_lead(data: dict, db: Session) -> str | None:
    """Returns rejection reason string if invalid, None if valid."""
    if not data.get("state"):
        return "state is required"

    if not data.get("vertical"):
        return "vertical is required"

    if not data.get("source"):
        return "source is required"

    if not data.get("trusted_form_cert_url") and not data.get("jornaya_lead_id"):
        return "trusted_form_cert_url or jornaya_lead_id is required"

    # Check duplicates in last 24 hours
    cutoff = datetime.utcnow() - timedelta(hours=24)
    duplicate = (
        db.query(Lead)
        .filter(
            Lead.created_at >= cutoff,
            or_(
                Lead.phone == data["phone"],
                Lead.email == data["email"],
            ),
        )
        .first()
    )
    if duplicate:
        return f"duplicate lead: phone or email already received in last 24h (existing lead: {duplicate.lead_id})"

    return None
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_validation.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add app/services/ tests/test_validation.py
git commit -m "feat: add lead validation service with dedup check"
```

---

### Task 6: Alerts service

**Files:**
- Create: `app/services/alerts.py`

**Step 1: Implement alerts service**

```python
# app/services/alerts.py
import os
import json
import httpx
from sqlalchemy.orm import Session
from app.models import Alert


def create_alert(
    db: Session,
    severity: str,
    entity_id: str,
    message: str,
    suggested_action: str,
) -> Alert:
    alert = Alert(
        severity=severity,
        entity_id=entity_id,
        message=message,
        suggested_action=suggested_action,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # Send to Slack if configured
    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    if slack_url:
        _send_slack(slack_url, alert)

    return alert


def _send_slack(webhook_url: str, alert: Alert):
    emoji = {"info": ":information_source:", "warning": ":warning:", "critical": ":rotating_light:"}.get(
        alert.severity, ":bell:"
    )
    payload = {
        "text": f"{emoji} *[{alert.severity.upper()}]* {alert.message}\n"
        f"> Entity: `{alert.entity_id}`\n"
        f"> Action: {alert.suggested_action}",
    }
    try:
        httpx.post(webhook_url, json=payload, timeout=5)
    except Exception:
        pass  # Don't fail lead processing if Slack is down
```

**Step 2: Commit**

```bash
git add app/services/alerts.py
git commit -m "feat: add alerts service with Slack webhook integration"
```

---

### Task 7: Ledger service

**Files:**
- Create: `app/services/ledger.py`

**Step 1: Implement ledger service**

```python
# app/services/ledger.py
from sqlalchemy.orm import Session
from app.models import Buyer, LedgerEntry


def debit_buyer(db: Session, buyer: Buyer, lead_id: str, amount: float, notes: str = None) -> LedgerEntry:
    balance_before = buyer.balance
    buyer.balance -= amount
    buyer.leads_received_today += 1
    balance_after = buyer.balance

    entry = LedgerEntry(
        buyer_id=buyer.buyer_id,
        lead_id=lead_id,
        type="debit",
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        notes=notes or f"Lead purchase: {lead_id}",
    )
    db.add(entry)
    return entry


def refund_buyer(db: Session, buyer: Buyer, lead_id: str, amount: float, notes: str = None) -> LedgerEntry:
    balance_before = buyer.balance
    buyer.balance += amount
    balance_after = buyer.balance

    entry = LedgerEntry(
        buyer_id=buyer.buyer_id,
        lead_id=lead_id,
        type="refund",
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        notes=notes or f"Lead return refund: {lead_id}",
    )
    db.add(entry)
    return entry
```

**Step 2: Commit**

```bash
git add app/services/ledger.py
git commit -m "feat: add ledger service for debit/refund operations"
```

---

### Task 8: Delivery simulation service

**Files:**
- Create: `app/services/delivery.py`

**Step 1: Implement delivery simulation**

```python
# app/services/delivery.py
import time
import os
from sqlalchemy.orm import Session
from app.models import Buyer, Lead, DeliveryAttempt


TIMEOUT_SECONDS = int(os.getenv("BUYER_TIMEOUT_SECONDS", "3"))


def simulate_delivery(db: Session, buyer: Buyer, lead: Lead) -> DeliveryAttempt:
    """Simulate delivering a lead to a buyer based on webhook_behavior."""
    start = time.time()

    if buyer.webhook_behavior == "accept":
        status = "accepted"
        rejection_reason = None
        # Simulate small latency
        time.sleep(0.05)

    elif buyer.webhook_behavior == "reject_duplicate":
        # Check if buyer already received a lead with same phone or email
        existing = (
            db.query(DeliveryAttempt)
            .join(Lead, DeliveryAttempt.lead_id == Lead.lead_id)
            .filter(
                DeliveryAttempt.buyer_id == buyer.buyer_id,
                DeliveryAttempt.status == "accepted",
                (Lead.phone == lead.phone) | (Lead.email == lead.email),
            )
            .first()
        )
        if existing:
            status = "rejected"
            rejection_reason = "duplicate: buyer already received lead with same phone/email"
        else:
            status = "accepted"
            rejection_reason = None
        time.sleep(0.05)

    elif buyer.webhook_behavior == "timeout":
        status = "timeout"
        rejection_reason = "buyer webhook timed out"
        time.sleep(0.1)  # Simulate a short delay (not actual 3s in tests)

    else:
        status = "error"
        rejection_reason = f"unknown webhook behavior: {buyer.webhook_behavior}"

    latency_ms = int((time.time() - start) * 1000)

    return DeliveryAttempt(
        lead_id=lead.lead_id,
        buyer_id=buyer.buyer_id,
        attempt_order=0,  # Set by caller
        status=status,
        rejection_reason=rejection_reason,
        latency_ms=latency_ms,
    )
```

**Step 2: Commit**

```bash
git add app/services/delivery.py
git commit -m "feat: add delivery simulation service with buyer behaviors"
```

---

### Task 9: Routing service

**Files:**
- Create: `app/services/routing.py`

**Step 1: Implement routing logic**

```python
# app/services/routing.py
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Buyer, Lead
from app.schemas import BuyerEvaluation
from app.services.delivery import simulate_delivery
from app.services.ledger import debit_buyer
from app.services.alerts import create_alert


def evaluate_buyers(db: Session, lead: Lead) -> list[BuyerEvaluation]:
    """Evaluate all buyers and return eligibility list."""
    buyers = db.query(Buyer).order_by(Buyer.priority).all()
    evaluations = []
    now = datetime.utcnow().strftime("%H:%M")

    for buyer in buyers:
        if buyer.status != "active":
            evaluations.append(BuyerEvaluation(
                buyer_id=buyer.buyer_id, buyer_name=buyer.buyer_name,
                eligible=False, reason_if_not_eligible="buyer status is not active"
            ))
        elif not buyer.campaign_active:
            evaluations.append(BuyerEvaluation(
                buyer_id=buyer.buyer_id, buyer_name=buyer.buyer_name,
                eligible=False, reason_if_not_eligible="campaign is not active"
            ))
        elif not buyer.ping_tree_assigned:
            evaluations.append(BuyerEvaluation(
                buyer_id=buyer.buyer_id, buyer_name=buyer.buyer_name,
                eligible=False, reason_if_not_eligible="not assigned to ping tree"
            ))
        elif buyer.balance < buyer.price_per_lead:
            evaluations.append(BuyerEvaluation(
                buyer_id=buyer.buyer_id, buyer_name=buyer.buyer_name,
                eligible=False, reason_if_not_eligible=f"insufficient balance: {buyer.balance} < {buyer.price_per_lead}"
            ))
        elif buyer.leads_received_today >= buyer.daily_cap:
            evaluations.append(BuyerEvaluation(
                buyer_id=buyer.buyer_id, buyer_name=buyer.buyer_name,
                eligible=False, reason_if_not_eligible=f"daily cap reached: {buyer.leads_received_today}/{buyer.daily_cap}"
            ))
        elif lead.state not in buyer.allowed_states:
            evaluations.append(BuyerEvaluation(
                buyer_id=buyer.buyer_id, buyer_name=buyer.buyer_name,
                eligible=False, reason_if_not_eligible=f"state {lead.state} not in allowed states"
            ))
        elif lead.vertical not in buyer.allowed_verticals:
            evaluations.append(BuyerEvaluation(
                buyer_id=buyer.buyer_id, buyer_name=buyer.buyer_name,
                eligible=False, reason_if_not_eligible=f"vertical {lead.vertical} not in allowed verticals"
            ))
        elif not (buyer.schedule_start <= now <= buyer.schedule_end):
            evaluations.append(BuyerEvaluation(
                buyer_id=buyer.buyer_id, buyer_name=buyer.buyer_name,
                eligible=False, reason_if_not_eligible=f"outside schedule: {buyer.schedule_start}-{buyer.schedule_end}"
            ))
        else:
            evaluations.append(BuyerEvaluation(
                buyer_id=buyer.buyer_id, buyer_name=buyer.buyer_name,
                eligible=True
            ))

    return evaluations


def route_lead(db: Session, lead: Lead) -> dict:
    """Route a lead through the ping tree. Returns routing result."""
    evaluations = evaluate_buyers(db, lead)
    eligible_buyers = [e for e in evaluations if e.eligible]

    if not eligible_buyers:
        lead.status = "unsold"
        db.commit()
        create_alert(
            db, severity="critical", entity_id=lead.lead_id,
            message=f"No eligible buyers for lead {lead.lead_id} ({lead.state}, {lead.vertical})",
            suggested_action="Review buyer configurations, balances, and caps"
        )
        return {"status": "unsold", "evaluations": evaluations, "attempts": []}

    attempts = []
    for order, eval_item in enumerate(eligible_buyers, 1):
        buyer = db.query(Buyer).filter_by(buyer_id=eval_item.buyer_id).first()
        attempt = simulate_delivery(db, buyer, lead)
        attempt.attempt_order = order
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        attempts.append(attempt)

        if attempt.status == "accepted":
            lead.status = "sold"
            lead.assigned_buyer_id = buyer.buyer_id
            lead.sold_price = buyer.price_per_lead
            debit_buyer(db, buyer, lead.lead_id, buyer.price_per_lead)
            db.commit()

            if buyer.balance < buyer.price_per_lead:
                create_alert(
                    db, severity="warning", entity_id=buyer.buyer_id,
                    message=f"Buyer {buyer.buyer_name} has low balance: ${buyer.balance:.2f}",
                    suggested_action="Notify buyer to add funds"
                )
            if buyer.leads_received_today >= buyer.daily_cap:
                create_alert(
                    db, severity="warning", entity_id=buyer.buyer_id,
                    message=f"Buyer {buyer.buyer_name} has reached daily cap: {buyer.leads_received_today}/{buyer.daily_cap}",
                    suggested_action="Increase cap or pause routing to this buyer"
                )

            return {"status": "sold", "buyer_id": buyer.buyer_id, "evaluations": evaluations, "attempts": attempts}

        # Generate alert for failed attempt
        if attempt.status == "timeout":
            create_alert(
                db, severity="warning", entity_id=buyer.buyer_id,
                message=f"Buyer {buyer.buyer_name} timed out for lead {lead.lead_id}",
                suggested_action="Check buyer webhook health"
            )

    # All eligible buyers failed
    lead.status = "unsold"
    db.commit()
    create_alert(
        db, severity="critical", entity_id=lead.lead_id,
        message=f"Lead {lead.lead_id} unsold: all eligible buyers failed",
        suggested_action="Review buyer webhook configurations"
    )
    return {"status": "unsold", "evaluations": evaluations, "attempts": attempts}
```

**Step 2: Commit**

```bash
git add app/services/routing.py
git commit -m "feat: add routing service with buyer evaluation and ping tree"
```

---

### Task 10: AI summary service

**Files:**
- Create: `app/services/ai_summary.py`

**Step 1: Implement AI summary**

```python
# app/services/ai_summary.py
import os
from openai import OpenAI


def generate_summary(metrics: dict) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    client = OpenAI(api_key=api_key)

    prompt = f"""You are an operations analyst for a lead distribution company.
Based on these daily metrics, provide a brief executive summary with:
1. General overview (2-3 sentences)
2. Main problems identified
3. Recommended actions

Metrics:
- Total leads received: {metrics.get('total_leads_received', 0)}
- Rejected leads: {metrics.get('rejected_leads', 0)}
- Sold leads: {metrics.get('sold_leads', 0)}
- Unsold leads: {metrics.get('unsold_leads', 0)}
- Returned leads: {metrics.get('returned_leads', 0)}
- Gross revenue: ${metrics.get('gross_revenue', 0):.2f}
- Refunds: ${metrics.get('refunds', 0):.2f}
- Net revenue: ${metrics.get('net_revenue', 0):.2f}
- Top buyer by spend: {metrics.get('top_buyer_by_spend', 'N/A')}
- Buyers with low balance: {metrics.get('buyers_with_low_balance', [])}
- Buyers with cap reached: {metrics.get('buyers_with_cap_reached', [])}
- Top rejection reasons: {metrics.get('top_rejection_reasons', [])}
- Average routing latency: {metrics.get('average_routing_latency_ms', 0):.0f}ms

Be concise and actionable. Do not invent data beyond what is provided."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.3,
    )
    return response.choices[0].message.content
```

**Step 2: Commit**

```bash
git add app/services/ai_summary.py
git commit -m "feat: add AI summary service using OpenAI"
```

---

### Task 11: FastAPI main app with all endpoints

**Files:**
- Create: `app/main.py`

**Step 1: Implement all endpoints**

```python
# app/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from app.database import Base, engine, get_db
from app.models import Lead, Buyer, DeliveryAttempt, LedgerEntry, Alert
from app.schemas import (
    LeadCreate, LeadResponse, LeadReturnRequest, BuyerResponse,
    DailySummary, DeliveryAttemptResponse, AlertResponse, BuyerEvaluation,
)
from app.services.validation import validate_lead
from app.services.routing import route_lead
from app.services.ledger import refund_buyer
from app.services.alerts import create_alert
from app.services.ai_summary import generate_summary
from app.seed import seed_buyers, seed_leads

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EcomfyApp Mini Lead Routing Engine",
    description="MVP lead routing engine with ping tree, ledger, and reporting",
    version="1.0.0",
)


@app.post("/seed")
def load_seed_data(db: Session = Depends(get_db)):
    """Load seed data: 5 buyers and optionally process 10 sample leads."""
    seed_buyers(db)
    leads_data = seed_leads()
    return {
        "message": "Seed data loaded",
        "buyers_created": 5,
        "sample_leads_available": len(leads_data),
        "sample_leads": leads_data,
    }


@app.post("/leads", response_model=LeadResponse)
def create_lead(lead_data: LeadCreate, db: Session = Depends(get_db)):
    """Receive a lead, validate it, and route through ping tree."""
    data = lead_data.model_dump()

    # Validate
    rejection_reason = validate_lead(data, db)

    if rejection_reason:
        lead = Lead(**data, status="rejected", rejection_reason=rejection_reason)
        db.add(lead)
        db.commit()
        db.refresh(lead)
        create_alert(
            db, severity="warning", entity_id=lead.lead_id,
            message=f"Lead rejected: {rejection_reason}",
            suggested_action="Review lead data quality from source"
        )
        return lead

    # Create lead as pending_distribution
    lead = Lead(**data, status="pending_distribution")
    db.add(lead)
    db.commit()
    db.refresh(lead)

    # Route
    result = route_lead(db, lead)
    db.refresh(lead)

    return lead


@app.post("/leads/{lead_id}/return", response_model=LeadResponse)
def return_lead(lead_id: str, return_req: LeadReturnRequest, db: Session = Depends(get_db)):
    """Return a sold lead and process refund."""
    lead = db.query(Lead).filter_by(lead_id=lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if lead.status != "sold":
        raise HTTPException(status_code=400, detail=f"Can only return sold leads. Current status: {lead.status}")

    buyer = db.query(Buyer).filter_by(buyer_id=lead.assigned_buyer_id).first()
    if not buyer:
        raise HTTPException(status_code=500, detail="Assigned buyer not found")

    # Process refund
    refund_buyer(db, buyer, lead.lead_id, lead.sold_price, notes=f"Return reason: {return_req.reason}")
    lead.status = "returned"
    lead.rejection_reason = f"Returned: {return_req.reason}"
    db.commit()
    db.refresh(lead)

    # Check for high returns from buyer
    recent_returns = (
        db.query(Lead)
        .filter(Lead.assigned_buyer_id == buyer.buyer_id, Lead.status == "returned")
        .count()
    )
    total_sold = (
        db.query(Lead)
        .filter(Lead.assigned_buyer_id == buyer.buyer_id, Lead.status.in_(["sold", "returned"]))
        .count()
    )
    if total_sold > 0 and recent_returns / total_sold > 0.3:
        create_alert(
            db, severity="critical", entity_id=buyer.buyer_id,
            message=f"High return rate from buyer {buyer.buyer_name}: {recent_returns}/{total_sold}",
            suggested_action="Review buyer quality and consider pausing"
        )

    return lead


@app.get("/reports/daily-summary", response_model=DailySummary)
def daily_summary(db: Session = Depends(get_db)):
    """Generate daily operational summary report."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    total = db.query(Lead).filter(Lead.created_at >= today_start).count()
    rejected = db.query(Lead).filter(Lead.created_at >= today_start, Lead.status == "rejected").count()
    sold = db.query(Lead).filter(Lead.created_at >= today_start, Lead.status == "sold").count()
    unsold = db.query(Lead).filter(Lead.created_at >= today_start, Lead.status == "unsold").count()
    returned = db.query(Lead).filter(Lead.created_at >= today_start, Lead.status == "returned").count()

    gross_revenue = db.query(func.coalesce(func.sum(LedgerEntry.amount), 0.0)).filter(
        LedgerEntry.created_at >= today_start, LedgerEntry.type == "debit"
    ).scalar()

    refunds = db.query(func.coalesce(func.sum(LedgerEntry.amount), 0.0)).filter(
        LedgerEntry.created_at >= today_start, LedgerEntry.type == "refund"
    ).scalar()

    net_revenue = gross_revenue - refunds

    # Top buyer by spend
    top_buyer_row = (
        db.query(Buyer.buyer_name, func.sum(LedgerEntry.amount).label("total_spend"))
        .join(LedgerEntry, LedgerEntry.buyer_id == Buyer.buyer_id)
        .filter(LedgerEntry.created_at >= today_start, LedgerEntry.type == "debit")
        .group_by(Buyer.buyer_name)
        .order_by(func.sum(LedgerEntry.amount).desc())
        .first()
    )
    top_buyer = top_buyer_row[0] if top_buyer_row else None

    # Low balance buyers
    low_balance = [
        b.buyer_name for b in db.query(Buyer).filter(Buyer.balance < Buyer.price_per_lead).all()
    ]

    # Cap reached buyers
    cap_reached = [
        b.buyer_name for b in db.query(Buyer).filter(Buyer.leads_received_today >= Buyer.daily_cap).all()
    ]

    # Top rejection reasons
    rejection_rows = (
        db.query(Lead.rejection_reason, func.count().label("count"))
        .filter(Lead.created_at >= today_start, Lead.status == "rejected", Lead.rejection_reason.isnot(None))
        .group_by(Lead.rejection_reason)
        .order_by(func.count().desc())
        .limit(5)
        .all()
    )
    top_rejections = [{"reason": r[0], "count": r[1]} for r in rejection_rows]

    # Average routing latency
    avg_latency = db.query(func.coalesce(func.avg(DeliveryAttempt.latency_ms), 0.0)).filter(
        DeliveryAttempt.created_at >= today_start
    ).scalar()

    metrics = {
        "total_leads_received": total,
        "rejected_leads": rejected,
        "sold_leads": sold,
        "unsold_leads": unsold,
        "returned_leads": returned,
        "gross_revenue": float(gross_revenue),
        "refunds": float(refunds),
        "net_revenue": float(net_revenue),
        "top_buyer_by_spend": top_buyer,
        "buyers_with_low_balance": low_balance,
        "buyers_with_cap_reached": cap_reached,
        "top_rejection_reasons": top_rejections,
        "average_routing_latency_ms": float(avg_latency),
    }

    # AI summary
    ai_summary = None
    try:
        ai_summary = generate_summary(metrics)
    except Exception:
        pass

    return DailySummary(**metrics, ai_summary=ai_summary)


@app.get("/leads", response_model=list[LeadResponse])
def list_leads(db: Session = Depends(get_db)):
    return db.query(Lead).order_by(Lead.created_at.desc()).all()


@app.get("/buyers", response_model=list[BuyerResponse])
def list_buyers(db: Session = Depends(get_db)):
    return db.query(Buyer).order_by(Buyer.priority).all()


@app.get("/alerts", response_model=list[AlertResponse])
def list_alerts(db: Session = Depends(get_db)):
    return db.query(Alert).order_by(Alert.created_at.desc()).limit(50).all()
```

**Step 2: Verify app starts**

Run: `cd ecomfy-lead-engine && uvicorn app.main:app --reload`
Expected: Server starts, Swagger at http://127.0.0.1:8000/docs

**Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: add FastAPI app with all endpoints"
```

---

### Task 12: Integration tests (8+ required test cases)

**Files:**
- Create: `tests/test_api.py`

**Step 1: Write all 8+ required tests**

```python
# tests/test_api.py
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


# Test 2: Lead vendido después de rechazo del primer buyer
def test_lead_sold_after_first_buyer_rejection(seeded_client):
    # First, send a lead that buyer B will accept
    resp1 = seeded_client.post("/leads", json=make_lead(
        phone="3058888888", email="first@example.com"
    ))
    assert resp1.json()["status"] == "sold"

    # Send duplicate phone/email that buyer B (priority 1) will reject as duplicate
    # but buyer C (priority 2, timeout) will timeout
    # and buyer A (priority 3) should accept
    resp2 = seeded_client.post("/leads", json=make_lead(
        phone="3058888888", email="second@example.com",
        first_name="Another", last_name="Person",
    ))
    data = resp2.json()
    assert data["status"] == "sold"


# Test 3: Lead duplicado rechazado
def test_duplicate_lead_rejected(seeded_client):
    # Send first lead
    resp1 = seeded_client.post("/leads", json=make_lead())
    assert resp1.json()["status"] == "sold"

    # Send same lead again - should be rejected by validation (system-level dedup)
    resp2 = seeded_client.post("/leads", json=make_lead())
    data = resp2.json()
    assert data["status"] == "rejected"
    assert "duplicate" in data["rejection_reason"].lower()


# Test 4: Lead sin email rechazado
def test_lead_without_valid_email_rejected(seeded_client):
    resp = seeded_client.post("/leads", json=make_lead(email="not-an-email"))
    assert resp.status_code == 422  # Pydantic validation error


# Test 5: Buyer sin balance descartado
def test_buyer_without_balance_skipped(seeded_client):
    # Buyer D has balance=5 and price_per_lead=25, so it should be skipped
    # We verify by checking that buyer D is never the assigned buyer
    resp = seeded_client.post("/leads", json=make_lead())
    data = resp.json()
    assert data["assigned_buyer_id"] != "buyer-d"


# Test 6: Buyer con cap lleno descartado
def test_buyer_with_full_cap_skipped(seeded_client):
    # Buyer E has leads_received_today=5 and daily_cap=5, so it's full
    resp = seeded_client.post("/leads", json=make_lead())
    data = resp.json()
    assert data["assigned_buyer_id"] != "buyer-e"


# Test 7: Buyer timeout y fallback
def test_buyer_timeout_triggers_fallback(seeded_client):
    # Buyer C (priority 2) will timeout, system should fallback to next buyer
    # Send a lead for Auto Insurance in TX - only buyer C and buyer A match
    # Buyer B doesn't allow Auto Insurance? Actually it does through allowed_verticals
    # Let's use a state/vertical combo. Buyer C allows Auto Insurance.
    resp = seeded_client.post("/leads", json=make_lead(
        vertical="Auto Insurance",
        phone="3057777777",
        email="timeout_test@example.com",
    ))
    data = resp.json()
    assert data["status"] == "sold"
    # Should not be buyer C (timeout)
    assert data["assigned_buyer_id"] != "buyer-c"


# Test 8: Lead sold devuelto con refund
def test_sold_lead_returned_with_refund(seeded_client):
    # Create and sell a lead
    resp = seeded_client.post("/leads", json=make_lead())
    lead_id = resp.json()["lead_id"]
    buyer_id = resp.json()["assigned_buyer_id"]
    assert resp.json()["status"] == "sold"

    # Get buyer balance after sale
    buyers = seeded_client.get("/buyers").json()
    buyer_balance_after_sale = next(b["balance"] for b in buyers if b["buyer_id"] == buyer_id)

    # Return the lead
    ret_resp = seeded_client.post(f"/leads/{lead_id}/return", json={"reason": "bad quality"})
    assert ret_resp.json()["status"] == "returned"

    # Verify buyer balance was refunded
    buyers_after = seeded_client.get("/buyers").json()
    buyer_balance_after_refund = next(b["balance"] for b in buyers_after if b["buyer_id"] == buyer_id)
    assert buyer_balance_after_refund > buyer_balance_after_sale


# Test 9: Cannot return a non-sold lead
def test_cannot_return_non_sold_lead(seeded_client):
    # Create a duplicate lead that gets rejected
    seeded_client.post("/leads", json=make_lead())
    resp = seeded_client.post("/leads", json=make_lead())
    lead_id = resp.json()["lead_id"]

    ret_resp = seeded_client.post(f"/leads/{lead_id}/return", json={"reason": "test"})
    assert ret_resp.status_code == 400


# Test 10: Lead missing cert and jornaya rejected
def test_lead_missing_cert_rejected(seeded_client):
    lead = make_lead()
    del lead["trusted_form_cert_url"]
    # Also no jornaya_lead_id
    resp = seeded_client.post("/leads", json=lead)
    data = resp.json()
    assert data["status"] == "rejected"
    assert "trusted_form" in data["rejection_reason"].lower() or "jornaya" in data["rejection_reason"].lower()


# Test 11: Daily summary report works
def test_daily_summary_report(seeded_client):
    # Send a few leads
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
    # Send a duplicate lead to trigger alert
    seeded_client.post("/leads", json=make_lead())
    seeded_client.post("/leads", json=make_lead())

    resp = seeded_client.get("/alerts")
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) > 0
```

**Step 2: Run all tests**

Run: `pytest tests/test_api.py -v`
Expected: All 12 tests PASS

**Step 3: Commit**

```bash
git add tests/test_api.py
git commit -m "feat: add 12 integration tests covering all required scenarios"
```

---

### Task 13: Postman collection

**Files:**
- Create: `postman/ecomfy_collection.json`

**Step 1: Create Postman collection**

Generate a JSON Postman collection with requests for:
1. POST /seed
2. POST /leads (valid lead)
3. POST /leads (duplicate - rejected)
4. POST /leads (missing email)
5. POST /leads (missing cert)
6. GET /leads
7. GET /buyers
8. POST /leads/{id}/return
9. GET /reports/daily-summary
10. GET /alerts

Each request should have the base URL set to `{{base_url}}` with default `http://localhost:8000`.

**Step 2: Commit**

```bash
git add postman/
git commit -m "feat: add Postman collection for API testing"
```

---

### Task 14: Documentation

**Files:**
- Create: `README.md`
- Create: `docs/technical.md`

**Step 1: Create README with setup instructions**

Cover:
- Project description
- Prerequisites (Python 3.11+)
- Setup steps (venv, pip install, .env)
- How to run (`uvicorn app.main:app --reload`)
- How to seed data
- How to run tests (`pytest -v`)
- API endpoints summary
- Postman collection location

**Step 2: Create technical document**

Cover all items from the spec:
- Architecture
- Data model
- Routing logic
- Error handling
- Duplicate prevention
- Timeout handling
- Double-charge prevention
- Production scaling (PostgreSQL, connection pooling, async workers)
- Integration with Phonexa, Everflow, GHL, Stripe

**Step 3: Commit**

```bash
git add README.md docs/technical.md
git commit -m "docs: add README and technical documentation"
```

---

### Task 15: Final verification

**Step 1: Clean run**

```bash
rm -f ecomfy.db
uvicorn app.main:app &
curl -X POST http://localhost:8000/seed
# Send all 10 seed leads
curl -X POST http://localhost:8000/leads -H "Content-Type: application/json" -d '{"first_name":"John","last_name":"Smith","phone":"3051234567","email":"john.smith@example.com","state":"FL","vertical":"Life Insurance","source":"google_ads","trusted_form_cert_url":"https://cert.trustedform.com/abc123"}'
# ... repeat for all leads
curl http://localhost:8000/reports/daily-summary
curl http://localhost:8000/alerts
```

**Step 2: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore: final verification and cleanup"
```
