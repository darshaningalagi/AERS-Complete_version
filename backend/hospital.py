from typing import Optional
from backend.ambulance import haversine

HOSPITALS = [
    {
        "id": "H-001",
        "name": "City General Hospital",
        "lat": 14.4700, "lng": 75.9300,
        "specialties": ["trauma", "cardiac", "neuro", "general"],
        "capacity_pct": 72, "icu_beds": 8,
        "contact": "+91-8360001111",
        "address": "Main Road, Haveri",
    },
    {
        "id": "H-002",
        "name": "Apollo Medical Center",
        "lat": 14.4850, "lng": 75.9400,
        "specialties": ["cardiac", "burns", "ortho", "general"],
        "capacity_pct": 58, "icu_beds": 12,
        "contact": "+91-8360002222",
        "address": "Hospital Road, Haveri",
    },
    {
        "id": "H-003",
        "name": "St. Mary's Hospital",
        "lat": 14.4600, "lng": 75.9180,
        "specialties": ["pediatric", "maternity", "general"],
        "capacity_pct": 88, "icu_beds": 3,
        "contact": "+91-8360003333",
        "address": "Church Street, Haveri",
    },
    {
        "id": "H-004",
        "name": "NIMHANS Trauma Center",
        "lat": 14.4750, "lng": 75.9450,
        "specialties": ["neuro", "trauma", "burns", "ortho"],
        "capacity_pct": 61, "icu_beds": 15,
        "contact": "+91-8360004444",
        "address": "Bypass Road, Haveri",
    },
]

RISK_SPECIALTY_MAP = {
    "cardiac": "cardiac", "heart": "cardiac", "chest": "cardiac",
    "trauma": "trauma", "accident": "trauma", "injury": "trauma",
    "brain": "neuro", "neuro": "neuro", "stroke": "neuro", "head": "neuro",
    "burn": "burns", "fire": "burns",
    "child": "pediatric", "baby": "pediatric", "infant": "pediatric",
    "bone": "ortho", "fracture": "ortho", "orthopedic": "ortho",
}


def infer_specialty(description: str, case_type: str) -> str:
    text = (description + " " + case_type).lower()
    for keyword, specialty in RISK_SPECIALTY_MAP.items():
        if keyword in text:
            return specialty
    return "general"


def score_hospital(hospital: dict, distance_km: float, specialty: str, risk: str) -> float:
    specialty_match = 50 if specialty in hospital["specialties"] else 0
    free_cap = (100 - hospital["capacity_pct"]) * 0.3
    icu_weight = hospital["icu_beds"] * 1.5
    proximity = (1 / max(distance_km, 0.1)) * 10
    if risk == "Critical":
        icu_weight *= 2.0
    return specialty_match + free_cap + icu_weight + proximity


# FIX BUG-03: Return type hint changed from `dict | None` (Python 3.10+
# only) to Optional[dict] so it works on Python 3.9 and above without
# a TypeError at import time.
def get_best_hospital(incident_lat: float, incident_lng: float,
                      description: str, case_type: str, risk: str) -> Optional[dict]:
    specialty = infer_specialty(description, case_type)
    eligible = [h for h in HOSPITALS if h["capacity_pct"] < 95]
    if not eligible:
        eligible = HOSPITALS[:]

    scored = []
    for h in eligible:
        dist = haversine(incident_lat, incident_lng, h["lat"], h["lng"])
        score = score_hospital(h, dist, specialty, risk)
        scored.append((score, dist, h))

    scored.sort(key=lambda x: -x[0])
    best_score, best_dist, best = scored[0]

    return {
        "id": best["id"],
        "name": best["name"],
        "address": best["address"],
        "contact": best["contact"],
        "specialty_matched": specialty,
        "distance_km": round(best_dist, 2),
        "capacity_pct": best["capacity_pct"],
        "icu_beds": best["icu_beds"],
        "score": round(best_score, 1),
    }


def get_hospital_list() -> list:
    return HOSPITALS
