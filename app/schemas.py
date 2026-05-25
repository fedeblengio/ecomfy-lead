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
