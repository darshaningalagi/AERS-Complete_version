from typing import Optional
from datetime import datetime
from backend.ambulance import haversine

# Total ICU beds per hospital (used for capacity calculations)
TOTAL_ICU_BEDS = 20

HOSPITALS = [
    {
        "id": "H-001",
        "name": "City General Hospital",
        "lat": 14.4700, "lng": 75.9300,
        "specialties": ["trauma", "cardiac", "neuro", "general"],
        "capacity_pct": 60, "icu_beds": 8,  # 60% occupied, 8 free beds
        "contact": "+91-8360001111",
        "address": "Main Road, Haveri",
    },
    {
        "id": "H-002",
        "name": "Apollo Medical Center",
        "lat": 14.4850, "lng": 75.9400,
        "specialties": ["cardiac", "burns", "ortho", "general"],
        "capacity_pct": 40, "icu_beds": 12,  # 40% occupied, 12 free beds
        "contact": "+91-8360002222",
        "address": "Hospital Road, Haveri",
    },
    {
        "id": "H-003",
        "name": "St. Mary's Hospital",
        "lat": 14.4600, "lng": 75.9180,
        "specialties": ["pediatric", "maternity", "general"],
        "capacity_pct": 85, "icu_beds": 3,  # 85% occupied, 3 free beds
        "contact": "+91-8360003333",
        "address": "Church Street, Haveri",
    },
    {
        "id": "H-004",
        "name": "NIMHANS Trauma Center",
        "lat": 14.4750, "lng": 75.9450,
        "specialties": ["neuro", "trauma", "burns", "ortho"],
        "capacity_pct": 25, "icu_beds": 15,  # 25% occupied, 15 free beds
        "contact": "+91-8360004444",
        "address": "Bypass Road, Haveri",
    },
    {
        "id": "H-005",
        "name": "LifeCare Hospital",
        "lat": 14.4500, "lng": 75.9150,
        "specialties": ["cardiac", "general", "ortho"],
        "capacity_pct": 50, "icu_beds": 10,  # 50% occupied, 10 free beds
        "contact": "+91-8360005555",
        "address": "Gandhi Road, Haveri",
    },
    {
        "id": "H-006",
        "name": "Child Care Institute",
        "lat": 14.4800, "lng": 75.9350,
        "specialties": ["pediatric", "maternity", "neonatal"],
        "capacity_pct": 70, "icu_beds": 6,  # 70% occupied, 6 free beds
        "contact": "+91-8360006666",
        "address": "Station Road, Haveri",
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

    # Score all hospitals and pick the best one
    scored = []
    for h in HOSPITALS:
        distance_km = haversine(incident_lat, incident_lng, h["lat"], h["lng"])
        score = score_hospital(h, distance_km, specialty, risk)
        scored.append((score, h, distance_km))

    # Sort by score (highest first)
    scored.sort(key=lambda x: x[0], reverse=True)
    best, distance_km = scored[0][1], scored[0][2]

    return {
        "id": best["id"],
        "name": best["name"],
        "address": best["address"],
        "contact": best["contact"],
        "lat": best["lat"],
        "lng": best["lng"],
        "specialty_matched": specialty,
        "distance_km": round(distance_km, 2),
        "capacity_pct": best["capacity_pct"],
        "icu_beds": best["icu_beds"],
        "score": round(scored[0][0], 2),
    }


def get_hospital_list() -> list:
    return HOSPITALS


def fill_bed(hospital_id: str) -> bool:
    """Mark a bed as occupied when patient arrives (decreases available beds)."""
    for h in HOSPITALS:
        if h["id"] == hospital_id and h["icu_beds"] > 0:
            h["icu_beds"] -= 1
            # Update capacity % (occupied / total * 100)
            occupied = TOTAL_ICU_BEDS - h["icu_beds"]
            h["capacity_pct"] = min(100, int((occupied / TOTAL_ICU_BEDS) * 100))
            return True
    return False


def free_bed(hospital_id: str) -> bool:
    """Mark a bed as available when patient is discharged."""
    for h in HOSPITALS:
        if h["id"] == hospital_id and h["icu_beds"] < TOTAL_ICU_BEDS:
            h["icu_beds"] += 1
            # Update capacity %
            occupied = TOTAL_ICU_BEDS - h["icu_beds"]
            h["capacity_pct"] = min(100, int((occupied / TOTAL_ICU_BEDS) * 100))
            return True
    return False


# Legacy aliases for backward compatibility
occupy_bed = fill_bed
release_bed = free_bed


def recalculate_capacity(hospital_id: str) -> bool:
    """Recalculate capacity % for a hospital based on current icu_beds."""
    for h in HOSPITALS:
        if h["id"] == hospital_id:
            occupied = TOTAL_ICU_BEDS - h["icu_beds"]
            h["capacity_pct"] = min(100, int((occupied / TOTAL_ICU_BEDS) * 100))
            return True
    return False


def get_available_beds(hospital_id: str) -> int:
    """Get available ICU beds for a hospital."""
    for h in HOSPITALS:
        if h["id"] == hospital_id:
            return h["icu_beds"]
    return 0


# ─── Hospital Bed Management (CRUD) ──────────────────────────────────────
def update_hospital_info(hospital_id: str, icu_beds: int = None, capacity_pct: int = None) -> bool:
    """Update hospital ICU beds or capacity percentage."""
    for h in HOSPITALS:
        if h["id"] == hospital_id:
            if icu_beds is not None:
                h["icu_beds"] = max(0, min(icu_beds, 50))
            if capacity_pct is not None:
                h["capacity_pct"] = max(0, min(capacity_pct, 100))
            return True
    return False


def add_icu_beds(hospital_id: str, beds: int = 1) -> bool:
    """Add ICU beds to hospital (increases available beds, decreases occupancy %)."""
    for h in HOSPITALS:
        if h["id"] == hospital_id:
            h["icu_beds"] = min(h["icu_beds"] + beds, TOTAL_ICU_BEDS)
            # Recalculate capacity % (beds used / total = occupied %)
            occupied = TOTAL_ICU_BEDS - h["icu_beds"]
            h["capacity_pct"] = min(100, int((occupied / TOTAL_ICU_BEDS) * 100))
            return True
    return False


def remove_icu_beds(hospital_id: str, beds: int = 1) -> bool:
    """Remove ICU beds from hospital (decreases available beds, increases occupancy %)."""
    for h in HOSPITALS:
        if h["id"] == hospital_id:
            h["icu_beds"] = max(0, h["icu_beds"] - beds)
            # Recalculate capacity %
            occupied = TOTAL_ICU_BEDS - h["icu_beds"]
            h["capacity_pct"] = min(100, int((occupied / TOTAL_ICU_BEDS) * 100))
            return True
    return False


# ─── Hospital CRUD ─────────────────────────────────────────────────────
def add_hospital(hospital_data: dict) -> dict:
    """Add a new hospital to the system. Returns the new hospital."""
    # Generate ID if not provided
    if "id" not in hospital_data:
        max_id = 0
        for h in HOSPITALS:
            if h["id"].startswith("H-"):
                try:
                    num = int(h["id"].split("-")[1])
                    max_id = max(max_id, num)
                except:
                    pass
        hospital_data["id"] = f"H-{max_id + 1:03d}"

    # Set defaults
    hospital_data.setdefault("name", "New Hospital")
    hospital_data.setdefault("lat", 14.4700)
    hospital_data.setdefault("lng", 75.9300)
    hospital_data.setdefault("specialties", ["general"])
    hospital_data.setdefault("capacity_pct", 50)
    hospital_data.setdefault("icu_beds", 10)
    hospital_data.setdefault("contact", "+91-8360000000")
    hospital_data.setdefault("address", "Address not set")

    HOSPITALS.append(hospital_data)
    return hospital_data


def delete_hospital(hospital_id: str) -> bool:
    """Remove a hospital from the system."""
    global HOSPITALS
    before = len(HOSPITALS)
    HOSPITALS = [h for h in HOSPITALS if h["id"] != hospital_id]
    return len(HOSPITALS) < before


def update_hospital_details(hospital_id: str, updates: dict) -> Optional[dict]:
    """Update hospital details."""
    for h in HOSPITALS:
        if h["id"] == hospital_id:
            for key, value in updates.items():
                if key != "id" and value is not None:
                    h[key] = value
            return h
    return None


# ─── Hospital Interface Functions ───────────────────────────────────────
# Track incoming patients for hospital dashboard
INCOMING_PATIENTS: dict = {}


def get_hospital_status(hospital_id: str) -> Optional[dict]:
    """Get hospital status including ICU beds for hospital dashboard."""
    for h in HOSPITALS:
        if h["id"] == hospital_id:
            return {
                "id": h["id"],
                "name": h["name"],
                "address": h["address"],
                "contact": h["contact"],
                "specialties": h["specialties"],
                "capacity_pct": h["capacity_pct"],
                "icu_beds": h["icu_beds"],
                "available_beds": get_available_beds(hospital_id),
                "total_beds": TOTAL_ICU_BEDS,
            }
    return None


def get_all_hospitals_status() -> list:
    """Get status of all hospitals."""
    return [
        {
            "id": h["id"],
            "name": h["name"],
            "address": h["address"],
            "capacity_pct": h["capacity_pct"],
            "icu_beds": h["icu_beds"],
            "specialties": h["specialties"],
        }
        for h in HOSPITALS
    ]


def notify_hospital(hospital_id: str, case_id: str, patient_name: str,
                    eta_minutes: int, description: str, risk_level: str) -> bool:
    """
    Notify hospital that a patient is being brought in.
    Called when ambulance picks up patient.
    """
    for h in HOSPITALS:
        if h["id"] == hospital_id:
            if hospital_id not in INCOMING_PATIENTS:
                INCOMING_PATIENTS[hospital_id] = []

            INCOMING_PATIENTS[hospital_id].append({
                "case_id": case_id,
                "patient_name": patient_name,
                "eta_minutes": eta_minutes,
                "description": description,
                "risk_level": risk_level,
                "notified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "incoming",
            })
            return True
    return False


def get_incoming_patients(hospital_id: str) -> list:
    """Get list of incoming patients for a hospital."""
    return INCOMING_PATIENTS.get(hospital_id, [])


def remove_incoming_patient(hospital_id: str, case_id: str) -> bool:
    """Remove patient from incoming list when delivered."""
    if hospital_id in INCOMING_PATIENTS:
        before = len(INCOMING_PATIENTS[hospital_id])
        INCOMING_PATIENTS[hospital_id] = [
            p for p in INCOMING_PATIENTS[hospital_id]
            if p["case_id"] != case_id
        ]
        return len(INCOMING_PATIENTS[hospital_id]) < before
    return False


def clear_incoming_patients(hospital_id: str):
    """Clear all incoming patients for a hospital."""
    INCOMING_PATIENTS[hospital_id] = []
