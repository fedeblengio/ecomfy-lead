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
