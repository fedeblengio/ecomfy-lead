# EcomfyApp Mini Lead Routing Engine — Design

## Stack
- Python + FastAPI
- SQLite (via SQLAlchemy)
- OpenAI API (AI summary)
- Slack webhook (alerts)
- pytest + TestClient + Postman collection

## Architecture

Monolith FastAPI app with SQLite. Single process, run with `uvicorn`.

```
ecomfy-lead-engine/
├── app/
│   ├── main.py              # FastAPI app + endpoints
│   ├── models.py            # SQLAlchemy models
│   ├── database.py          # DB connection + session
│   ├── schemas.py           # Pydantic schemas (request/response)
│   ├── services/
│   │   ├── validation.py    # Lead validation logic
│   │   ├── routing.py       # Buyer selection + ping tree
│   │   ├── delivery.py      # Simulate webhook delivery to buyers
│   │   ├── ledger.py        # Balance operations + ledger entries
│   │   ├── alerts.py        # Alert generation + Slack webhook
│   │   └── ai_summary.py   # OpenAI summary of daily report
│   └── seed.py              # Data seed (10 leads, 5 buyers)
├── tests/
│   └── test_api.py          # 8+ pytest tests with TestClient
├── postman/
│   └── collection.json      # Postman collection
├── docs/
│   └── technical.md         # Technical document
├── requirements.txt
├── .env.example
└── README.md
```

## Data Model (5 tables)

### leads
- lead_id (PK, UUID)
- first_name, last_name, phone, email
- state, vertical, source
- trusted_form_cert_url, jornaya_lead_id
- status: pending | pending_distribution | sold | rejected | returned | unsold
- rejection_reason (nullable)
- assigned_buyer_id (FK, nullable)
- sold_price (nullable)
- created_at

### buyers
- buyer_id (PK, UUID)
- buyer_name
- status: active | inactive
- balance (decimal)
- daily_cap (int)
- leads_received_today (int)
- allowed_states (JSON array)
- allowed_verticals (JSON array)
- schedule_start, schedule_end (time)
- campaign_active (bool)
- ping_tree_assigned (bool)
- priority (int, lower = higher priority)
- price_per_lead (decimal)
- webhook_behavior: accept | reject_duplicate | timeout

### delivery_attempts
- attempt_id (PK, UUID)
- lead_id (FK)
- buyer_id (FK)
- attempt_order (int)
- status: accepted | rejected | timeout | error
- rejection_reason (nullable)
- latency_ms (int)
- created_at

### ledger
- transaction_id (PK, UUID)
- buyer_id (FK)
- lead_id (FK)
- type: debit | refund
- amount (decimal)
- balance_before (decimal)
- balance_after (decimal)
- notes (nullable)
- created_at

### alerts
- alert_id (PK, UUID)
- severity: info | warning | critical
- entity_id (str)
- message (str)
- suggested_action (str)
- created_at

## Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/leads` | Receive and process a lead |
| POST | `/leads/{id}/return` | Return a sold lead with refund |
| GET | `/reports/daily-summary` | Daily operational report |
| GET | `/leads` | List all leads |
| GET | `/buyers` | List all buyers |
| POST | `/seed` | Load seed data |

## Routing Flow

1. Validate lead (email, phone, state, vertical, source, cert/jornaya, dedup 24h)
2. If fails → status=rejected, save rejection_reason, generate alert
3. If passes → status=pending_distribution
4. Filter eligible buyers:
   - status = active
   - campaign_active = true
   - ping_tree_assigned = true
   - balance >= price_per_lead
   - leads_received_today < daily_cap
   - state in allowed_states
   - vertical in allowed_verticals
   - current time within schedule_start..schedule_end
5. Sort by priority (ascending)
6. Ping tree: attempt delivery one by one
7. Simulate buyer response based on webhook_behavior
8. If accepted → status=sold, deduct balance, create ledger debit, increment cap
9. If all fail → status=unsold, generate alert

## Buyer Simulation

| Buyer | webhook_behavior | Effect |
|-------|-----------------|--------|
| A | accept | Always accepts |
| B | reject_duplicate | Rejects if already received lead with same phone/email |
| C | timeout | Simulates timeout (3s+ delay) |
| D | (filtered out) | Balance too low, never reaches delivery |
| E | (filtered out) | Cap full or campaign inactive |

## Slack + AI

- **Slack**: Configurable webhook in `.env`. If not set, alerts saved to DB only.
- **AI Summary**: OpenAI `gpt-4o-mini` generates executive summary from calculated metrics. Key in `.env`. If not set, report returns without summary.
