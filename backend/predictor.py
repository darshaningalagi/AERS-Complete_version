import re
import pickle
import os

# ─── Load model & vectorizer at startup ──────────────────────────────
_BASE = os.path.join(os.path.dirname(__file__), '..', 'model')
_MODEL_PATH = os.path.join(_BASE, 'model.pkl')
_VEC_PATH   = os.path.join(_BASE, 'vectorizer.pkl')

try:
    with open(_MODEL_PATH, 'rb') as f:
        _model = pickle.load(f)
    with open(_VEC_PATH, 'rb') as f:
        _vectorizer = pickle.load(f)
    MODEL_LOADED = True
except FileNotFoundError:
    _model = None
    _vectorizer = None
    MODEL_LOADED = False
    print("WARNING: model.pkl or vectorizer.pkl not found. Run model/train.py first.")


# ─── Text cleaning (mirrors train.py) ────────────────────────────────
def clean_text(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ─── Risk level meta ──────────────────────────────────────────────────
RISK_META = {
    "Critical": {
        "color": "red",
        "response_time": "< 2 minutes",
        "action": "Deploy ALS unit immediately. Full trauma team on standby.",
        "priority": 1,
    },
    "Urgent": {
        "color": "orange",
        "response_time": "< 10 minutes",
        "action": "Dispatch BLS unit. Notify relevant hospital department.",
        "priority": 2,
    },
    "Low": {
        "color": "green",
        "response_time": "< 30 minutes",
        "action": "Schedule BLS response. Standard intake procedure.",
        "priority": 3,
    },
}


# ─── Main prediction function ─────────────────────────────────────────
def predict_risk(description: str) -> dict:
    """
    Run triage classification on the emergency description.
    Returns risk level, confidence, and action metadata.
    """
    if not description or not str(description).strip():
        return {
            "success": False,
            "error": "Empty input — please describe the emergency.",
        }

    if not MODEL_LOADED:
        return {
            "success": False,
            "error": "ML model not loaded. Run: python model/train.py",
        }

    cleaned = clean_text(description)

    # Edge case: check for valid text after cleaning (not just numbers/symbols)
    if len(cleaned) < 2:
        return {
            "success": False,
            "error": "Input too short or contains only special characters. Please provide a valid description.",
        }

    # Vectorize and predict
    vec = _vectorizer.transform([cleaned])
    risk_level = _model.predict(vec)[0]          # Critical / Urgent / Low
    probabilities = _model.predict_proba(vec)[0]
    confidence = round(float(max(probabilities)) * 100, 1)

    # Build probability breakdown
    classes = list(_model.classes_)
    prob_breakdown = {c: round(float(p) * 100, 1) for c, p in zip(classes, probabilities)}

    meta = RISK_META.get(risk_level, RISK_META["Low"])

    return {
        "success": True,
        "risk_level": risk_level,
        "confidence": confidence,
        "probabilities": prob_breakdown,
        "color": meta["color"],
        "response_time": meta["response_time"],
        "action": meta["action"],
        "priority": meta["priority"],
        "cleaned_input": cleaned,
    }
