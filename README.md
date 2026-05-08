# AERS — AI-Based Enhanced Emergency Response System

**BCA Final Year Project | Darshan Ingalagi | 2025-26**

A complete AI-powered emergency response system with automated triage (ML), ambulance dispatch, hospital selection, and a real-time web dashboard.

---

## Project Structure

```
emergency-system/
├── app.py               ← FastAPI main server (run this)
├── requirements.txt     ← Python dependencies
├── tests.py             ← Full test suite
│
├── backend/
│   ├── __init__.py
│   ├── predictor.py     ← ML triage engine (loads model, runs prediction)
│   ├── ambulance.py     ← Fleet data + dispatch logic + GPS distance
│   ├── hospital.py      ← Hospital registry + selection algorithm
│   └── decision.py      ← Decision engine (combines all modules)
│
├── model/
│   ├── train.py         ← Model training script
│   ├── model.pkl        ← Trained Logistic Regression (auto-generated)
│   └── vectorizer.pkl   ← TF-IDF vectorizer (auto-generated)
│
├── data/
│   └── data.csv         ← 135 labeled emergency cases
│
└── frontend/
    └── index.html       ← Complete web UI (served by FastAPI)
```

---

## Setup (3 steps)

### Step 1 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 2 — Train the ML model
```bash
python model/train.py
```
Expected output: `Model Accuracy: ~85%` and `model.pkl` + `vectorizer.pkl` saved in `/model/`.

### Step 3 — Start the server
```bash
uvicorn app:app --reload --port 8000
```

Open your browser at: **http://localhost:8000**

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Serve frontend UI |
| GET | `/test` | Health check |
| GET | `/status` | Full system status (fleet, hospitals, model) |
| POST | `/triage` | Triage only (no dispatch) |
| POST | `/analyze` | Full pipeline: triage + dispatch + hospital |
| GET | `/ambulances` | Fleet status |
| POST | `/ambulances/status` | Update unit status (admin) |
| GET | `/hospitals` | Hospital list |
| GET | `/cases` | Last 20 case history |

### Example API call
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"description": "65 year old, chest pain, sweating, left arm pain", "lat": 14.4673, "lng": 75.9238}'
```

---

## How Each Module Works

### Module 1 — FastAPI Backend (`app.py`)
- REST API with CORS enabled
- Serves frontend from `/frontend/index.html`
- Input validation via Pydantic models
- Error handling for empty inputs and model failures

### Module 2 — Data (`data/data.csv`)
- 135 labeled emergency descriptions
- Three classes: `Critical`, `Urgent`, `Low`
- Balanced across real-world emergency scenarios

### Module 3 — ML Triage (`model/train.py` + `backend/predictor.py`)
- Text cleaning: lowercase, remove punctuation, trim spaces
- TF-IDF vectorization (500 features, 1-2 ngrams)
- Logistic Regression classifier (~85% accuracy)
- Returns: risk level, confidence %, probability breakdown

### Module 4 — Prediction Integration (`backend/predictor.py`)
- Loads saved model at server startup
- Handles empty input gracefully
- Returns structured dict with risk, confidence, action

### Module 5 — Ambulance Dispatch (`backend/ambulance.py`)
- 4 units: 2 ALS (Advanced Life Support), 2 BLS (Basic)
- Haversine GPS distance calculation
- Critical cases: prefer ALS units first
- ETA calculation based on risk level (80 km/h for critical)
- Status tracking: available / busy

### Module 6 — Hospital Selection (`backend/hospital.py`)
- 4 hospitals with specialties, capacity, ICU beds
- Weighted scoring: `specialty(50) + free_capacity(0.3) + ICU(1.5×2 for Critical) + proximity(10/km)`
- Specialty inferred from emergency description keywords
- Hospitals over 95% capacity excluded

### Module 7 — Decision Engine (`backend/decision.py`)
- Orchestrates all modules in sequence
- Generates unique Case ID (EM-XXXXXXXX)
- Logs all cases in memory (replace with PostgreSQL for production)
- Returns complete structured response with timeline

### Module 8 — Frontend (`frontend/index.html`)
- Connects to backend via configurable URL
- Voice input simulation (Whisper integration point)
- Live case timeline with phase progression
- Fleet and hospital status panels
- System audit log

---

## Running Tests
```bash
python tests.py
```
Tests all 9 modules including edge cases (empty input, random text, mixed language).

---

## Tech Stack
| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+ · FastAPI · Uvicorn |
| ML | scikit-learn · Logistic Regression · TF-IDF |
| Data | pandas · 135 labeled emergency cases |
| Distance | Haversine formula (GPS coordinates) |
| Frontend | Vanilla HTML/CSS/JavaScript |
| API | REST (JSON) |

---

## Module 10 Upgrades (After Submission)
- Replace Whisper simulation with real `openai-whisper` STT
- Replace static hospital/ambulance data with PostgreSQL
- Add real Google Maps routing via `googlemaps` library
- Upgrade ML model to fine-tuned BERT/BioBERT
- Add JWT authentication for admin endpoints
- Add real-time WebSocket updates

---

## Viva Talking Points
1. **Why Logistic Regression?** Fast, interpretable, works well with TF-IDF features. BioBERT would give better accuracy but needs GPU and is overkill for a BCA project.
2. **Why TF-IDF and not word embeddings?** TF-IDF works offline, no internet needed, and achieves 85% on this dataset. Embeddings add latency without proportional gain at this scale.
3. **Hospital scoring formula** — the weighted multi-criteria approach is the strongest technical differentiator. Nearest-hospital routing ignores specialty and capacity.
4. **Haversine vs Google Maps** — Haversine gives direct distance (accurate enough for dispatch ordering). Google Maps would give road distance + traffic-aware ETA in production.
