# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AERS (AI-Based Enhanced Emergency Response System) is a FastAPI-based emergency response system with ML-powered triage, ambulance dispatch, and hospital selection. The system uses a Logistic Regression classifier with TF-IDF vectorization for risk assessment.

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Train/update ML model
python model/train.py

# Run the server
uvicorn app:app --reload --port 8000

# Run tests
python tests.py

# Access the application
# Main UI:     http://localhost:8000
# Simulator:   http://localhost:8000/simulator
# Analytics:   http://localhost:8000/analytics
```

## Architecture

The system follows a modular pipeline architecture:

```
Request → Triage (ML) → Ambulance Dispatch → Hospital Selection → Response
```

### Core Modules

- **`app.py`** - FastAPI server, WebSocket manager, route handlers
- **`backend/predictor.py`** - ML triage engine (loads `model/model.pkl`)
- **`backend/ambulance.py`** - Fleet management, GPS dispatch, queue system
- **`backend/hospital.py`** - Hospital registry with weighted scoring algorithm
- **`backend/decision.py`** - Orchestrates the full pipeline, manages case lifecycle
- **`backend/database.py`** - SQLite persistence for cases and analytics
- **`backend/ws_manager.py`** - WebSocket broadcast for real-time updates
- **`simulator/engine.py`** - Test scenario generator for load testing

### Data Flow

1. Emergency description text is triaged via ML model → risk level
2. Nearest available ambulance is dispatched (or queued if none available)
3. Best hospital is selected based on specialty match, capacity, and proximity
4. Case is persisted to SQLite and broadcast via WebSocket

### Key API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/analyze` | Full pipeline: triage + dispatch + hospital |
| POST | `/triage` | Triage only (no dispatch) |
| GET | `/status` | System status (fleet, hospitals, model) |
| GET | `/ambulances` | Fleet status |
| GET | `/hospitals` | Hospital list |
| GET | `/cases` | Recent case history |
| GET | `/queue` | Waiting queue status |
| GET | `/api/analytics` | Analytics data |
| WS | `/ws` | Real-time updates |

### WebSocket Events

The system broadcasts events via WebSocket:
- `new_case` - New emergency case created
- `queue_resolved` - Queued case assigned to freed ambulance
- `ambulance_status` - Fleet status changes

## Database

SQLite is used for persistence (`aers.db`). Key tables:
- `cases` - Emergency case records
- `ambulance_events` - Dispatch/release events
- `analytics` - Aggregated statistics

## Testing

`tests.py` is a manual test suite that verifies:
- ML triage predictions (including edge cases)
- Ambulance dispatch logic
- Hospital selection algorithm
- End-to-end decision engine

## Frontend

- **`frontend/index.html`** - Main emergency response dashboard
- **`frontend/analytics.html`** - Analytics and charts
- **`simulator/dashboard.html`** - Load testing simulator