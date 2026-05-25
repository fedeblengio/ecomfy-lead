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
