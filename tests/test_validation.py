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
    assert result is None


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
