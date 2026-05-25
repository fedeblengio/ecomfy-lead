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
