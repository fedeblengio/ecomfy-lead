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
