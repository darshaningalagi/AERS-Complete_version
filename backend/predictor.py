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
    print("WARNING: model.pkl or vectorizer.pkl not found. Using rule-based fallback.")


# ─── Text cleaning (mirrors train.py) ───────────────────────────────
def clean_text(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r'[^\w\s]', ' ', text)  # Replace punctuation with space
    text = re.sub(r'\s+', ' ', text)      # Collapse whitespace
    # Remove numbers-only tokens
    text = ' '.join(word for word in text.split() if not word.isdigit())
    return text.strip()


# ─── Input sanitization ─────────────────────────────────────────────
def sanitize_input(text: str) -> str:
    """Sanitize user input - remove potentially harmful content."""
    if not text:
        return ""
    text = str(text)
    # Remove HTML/script tags
    text = re.sub(r'<[^>]*>', '', text)
    # Limit length
    text = text[:500]
    return text


def validate_coordinates(lat: float, lng: float) -> tuple[bool, str]:
    """Validate latitude and longitude values."""
    if lat is None or lng is None:
        return False, "Coordinates are required"
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        return False, "Coordinates must be numbers"
    if not (-90 <= lat <= 90):
        return False, "Latitude must be between -90 and 90"
    if not (-180 <= lng <= 180):
        return False, "Longitude must be between -180 and 180"
    return True, ""


# ─── Risk level meta ────────────────────────────────────────────────
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


# ─── Rule-based fallback ────────────────────────────────────────────
# Keywords for rule-based triage when ML fails
CRITICAL_KEYWORDS = [
    "not breathing", "no pulse", "cardiac arrest", "unconscious", "unresponsive",
    "severe bleeding", "heavy bleeding", "drowning", "choking", "overdose",
    "heart attack", "stroke", "seizure", "not stopping", "crushing chest",
    "radiating", "left arm", "diaphoresis", "sweating", "throat swelling",
    "anaphylaxis", "severe allergic", "burns", "40 percent", "50 percent",
    "gunshot", "stab wound", "ejected", "vehicle collision", "accident",
    "collapsed", "sudden", "slurred speech", "facial drooping", "arm weakness",
    "cannot breathe", "difficulty breathing", "blue lips", "cyanosis",
    "pediatric", "child", "baby", "infant", "near drowning", "fall from height",
    "neck injury", "spinal", "paralysis", "internal bleeding", "aortic",
]

URGENT_KEYWORDS = [
    "broken", "fracture", "bleeding", "cut", "laceration", "stitches",
    "moderate pain", "severe pain", "high fever", "104", "seizure history",
    "diabetic", "low blood sugar", "asthma", "attack", "allergic reaction",
    "mild", "moderate", "urgent", "conscious", "stable", "moving",
]

LOW_KEYWORDS = [
    "mild", "minor", "small", "superficial", "bruise", "scrape",
    "headache", "fever", "cold", "flu", "nausea", "dizziness",
    "sprain", "strain", "twisted", "painful", "walking",
]


def rule_based_triage(description: str) -> dict:
    """
    Fallback rule-based triage when ML model is unavailable.
    Uses keyword matching to determine risk level.
    """
    text = description.lower()

    # Count matches
    critical_count = sum(1 for kw in CRITICAL_KEYWORDS if kw in text)
    urgent_count = sum(1 for kw in URGENT_KEYWORDS if kw in text)
    low_count = sum(1 for kw in LOW_KEYWORDS if kw in text)

    # Determine risk based on counts and weights
    if critical_count >= 2 or (critical_count >= 1 and urgent_count >= 1):
        risk_level = "Critical"
        confidence = min(95, 50 + critical_count * 10)
    elif critical_count >= 1:
        risk_level = "Critical"
        confidence = min(85, 40 + critical_count * 10)
    elif urgent_count >= 2:
        risk_level = "Urgent"
        confidence = min(80, 40 + urgent_count * 8)
    elif urgent_count >= 1:
        risk_level = "Urgent"
        confidence = min(70, 35 + urgent_count * 8)
    elif low_count >= 1:
        risk_level = "Low"
        confidence = min(70, 40 + low_count * 5)
    else:
        # Default to Urgent if no keywords matched
        risk_level = "Urgent"
        confidence = 50

    meta = RISK_META.get(risk_level, RISK_META["Low"])

    return {
        "success": True,
        "risk_level": risk_level,
        "confidence": round(confidence, 1),
        "probabilities": {
            "Critical": round(100 if risk_level == "Critical" else 100 - confidence, 1),
            "Urgent": round(100 if risk_level == "Urgent" else (100 - confidence) / 2, 1),
            "Low": round(100 if risk_level == "Low" else (100 - confidence) / 3, 1),
        },
        "color": meta["color"],
        "response_time": meta["response_time"],
        "action": meta["action"],
        "priority": meta["priority"],
        "cleaned_input": clean_text(description),
        "fallback": True,  # Indicates this used rule-based fallback
    }


# ─── Main prediction function ─────────────────────────────────────────
def predict_risk(description: str) -> dict:
    """
    Run triage classification on the emergency description.
    Returns risk level, confidence, and action metadata.
    """
    # Sanitize input first
    description = sanitize_input(description)

    # Input validation
    if not description or not str(description).strip():
        return {
            "success": False,
            "error": "Empty input - please describe the emergency.",
        }

    cleaned = clean_text(description)

    # Edge case: check for valid text after cleaning
    if len(cleaned) < 3:
        return {
            "success": False,
            "error": "Input too short. Please provide a valid description of the emergency.",
        }

    # Check for gibberish/invalid input
    words = cleaned.split()
    if len(words) < 2:
        return {
            "success": False,
            "error": "Please provide more details about the emergency.",
        }

    # If model not loaded, use fallback
    if not MODEL_LOADED:
        return rule_based_triage(description)

    try:
        # Vectorize and predict
        vec = _vectorizer.transform([cleaned])
        risk_level = _model.predict(vec)[0]
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
            "fallback": False,  # ML model used successfully
        }

    except Exception as e:
        # If ML prediction fails, fall back to rule-based
        print(f"ML prediction failed: {e}. Using rule-based fallback.")
        return rule_based_triage(description)