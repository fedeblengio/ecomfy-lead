# EcomfyApp Mini Lead Routing Engine

MVP lead routing engine that receives leads via API, validates them, distributes to buyers via ping tree, manages balances/ledger, handles returns, and generates operational reports with alerts.

## Stack

- Python 3.11+ / FastAPI
- SQLite (SQLAlchemy ORM)
- OpenAI API (optional - AI summary)
- Slack webhooks (optional - alerts)

## Prerequisites

- Python 3.11+
- pip

## Setup

```bash
# Clone the repo
git clone <repo-url>
cd ecomfy-lead-engine

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys (optional)
```

## Running

```bash
# Start the server
uvicorn app.main:app --reload

# Open Swagger docs
# http://localhost:8000/docs
```

## Seed Data

```bash
# Load 5 test buyers
curl -X POST http://localhost:8000/seed
```

## Running Tests

```bash
pytest tests/ -v
```

## API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/seed` | Load seed data (5 buyers) |
| POST | `/leads` | Receive and route a lead |
| POST | `/leads/{id}/return` | Return a sold lead with refund |
| GET | `/reports/daily-summary` | Daily operational report |
| GET | `/leads` | List all leads |
| GET | `/buyers` | List all buyers |
| GET | `/alerts` | List recent alerts |

## Postman Collection

Import `postman/ecomfy_collection.json` into Postman to test all endpoints.

## Test Buyers

| Buyer | Behavior | Purpose |
|-------|----------|---------|
| Buyer A | Always accepts | Happy path |
| Buyer B | Rejects duplicates | Duplicate handling |
| Buyer C | Timeout | Fallback testing |
| Buyer D | Low balance ($5) | Balance filtering |
| Buyer E | Cap full + inactive | Cap/campaign filtering |

## Architecture

See `docs/technical.md` for detailed technical documentation.
