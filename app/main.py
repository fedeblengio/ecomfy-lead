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
