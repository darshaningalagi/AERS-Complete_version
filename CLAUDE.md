# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AERS (AI-Based Enhanced Emergency Response System) is a FastAPI-based emergency response system with ML-powered triage, ambulance dispatch, and hospital selection. Uses Logistic Regression with TF-IDF vectorization for risk assessment.

## Project Rules

- Analyze entire repository before answering
- Prefer concise code
- Use existing architecture
- Do not invent files or folders
- Ask before major refactors
- Focus on FastAPI backend and AI integrations

## Setup & Commands

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Train/update ML model
python model/train.py

# Run the server
uvicorn app:app --reload --port 8000

# Run tests
python tests.py
```

## Project Structure

```
AERS-Complete_version/
├── app.py              # FastAPI server, routes, WebSocket
├── requirements.txt    # Python dependencies
├── tests.py            # Test suite
├── CLAUDE.md           # Claude Code guidance
├── README.md           # Project documentation
├── LICENSE             # MIT License
├── backend/            # Core backend modules
│   ├── ambulance.py     # Fleet management, dispatch, movement
│   ├── database.py    # SQLite persistence
│   ├── decision.py     # Decision pipeline orchestration
│   ├── hospital.py    # Hospital registry & selection
│   ├── predictor.py   # ML triage engine
│   └── ws_manager.py  # WebSocket broadcast
├── frontend/           # Web dashboards
│   ├── index.html     # Main dashboard
│   ├── analytics.html # Analytics view
│   ├── tracking.html  # Live fleet tracking
│   ├── admin.html     # Admin panel
│   ├── patient.html   # Patient portal
│   ├── driver.html    # Driver dashboard
│   └── hospital.html  # Hospital dashboard
├── model/              # ML model files
│   ├── model.pkl      # Trained classifier
│   ├── vectorizer.pkl # TF-IDF vectorizer
│   └── train.py       # Model training script
├── simulator/          # Load testing
│   ├── engine.py      # Scenario generator
│   ├── dashboard.html # Simulator UI
│   └── scenarios.py   # Test scenarios
└── data/               # Runtime data
    └── aers.db        # SQLite database
```

## Core Modules

- **`app.py`** - FastAPI server, WebSocket manager, route handlers
- **`backend/predictor.py`** - ML triage engine (loads `model/model.pkl`)
- **`backend/ambulance.py`** - Fleet management, GPS dispatch, queue, movement
- **`backend/hospital.py`** - Hospital registry with weighted scoring
- **`backend/decision.py`** - Orchestrates full pipeline
- **`backend/database.py`** - SQLite persistence for cases/analytics
- **`backend/ws_manager.py`** - Real-time WebSocket broadcast

## Key Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/analyze` | Full pipeline: triage + dispatch + hospital |
| POST | `/triage` | Triage only |
| GET | `/status` | System status (fleet, hospitals, model) |
| GET | `/ambulances` | Fleet status |
| GET | `/hospitals` | Hospital list |
| GET | `/cases` | Recent case history |
| GET | `/api/analytics` | Analytics data |
| WS | `/ws` | Real-time updates |

## WebSocket Events

- `new_case` - New emergency case created
- `queue_resolved` - Queued case assigned
- `ambulance_status` - Fleet status changes
- `patient_picked_up` - Patient picked up
- `patient_delivered` - Patient arrived at hospital

## Frontend Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | index.html | Main emergency dashboard |
| `/analytics` | analytics.html | Charts and stats |
| `/tracking` | tracking.html | Live fleet tracking with map |
| `/admin` | admin.html | Manage hospitals & ambulances |
| `/patient` | patient.html | Patient portal with tracking |
| `/driver` | driver.html | Driver dashboard with nav map |
| `/hospital` | hospital.html | Hospital dashboard |
| `/simulator` | dashboard.html | Load testing simulator |

## Database

SQLite (`data/aers.db`) with tables: `cases`, `ambulance_events`, `analytics`.

## Key Features

- ML-powered triage using Logistic Regression + TF-IDF
- Priority queue with preemption for Critical cases
- Real-time ambulance movement tracking
- Movement trails and smooth animations on map
- WebSocket real-time updates
- Admin panel for hospital/ambulance management