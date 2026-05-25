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
