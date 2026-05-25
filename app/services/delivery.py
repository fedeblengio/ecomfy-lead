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
