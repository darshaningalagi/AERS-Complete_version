"""
AERS Ambulance Module — v4
Priority Queue + Preemption + Auto-Assign on Release

When fleet is full:
  1. PREEMPTION  — Critical can steal a unit from a Low case
  2. PRIORITY QUEUE — if preemption not possible, case waits in queue
  3. AUTO-ASSIGN — when any unit is released, top queue item gets it instantly
"""

import math
import asyncio
from datetime import datetime
from typing import Optional

# ─── Fleet ────────────────────────────────────────────────────────────
# Tracking fields: destination_hospital_id, destination_hospital_name,
#                  destination_hospital_lat/lng, patient_location, patient_description
AMBULANCES = [
    {"id":"AMB-01","driver":"Rajesh Sharma", "phone":"+91-9876543210",
     "type":"ALS","location":"Central Station","lat":14.4673,"lng":75.9238,
     "status":"available","assigned_case":None,"assigned_risk":None,"current_phase":"available",
     "equipment":["defibrillator","ventilator","cardiac monitor","IV kit"],
     "destination_hospital_id":None,"destination_hospital_name":None,
     "destination_hospital_lat":None,"destination_hospital_lng":None,
     "patient_location_lat":None,"patient_location_lng":None,
     "patient_description":None,"case_id":None,
     "maintenance_status":"good","fuel_pct":80,"last_maintenance":"2024-01-15","notes":""},
    {"id":"AMB-03","driver":"Kavita Patel",  "phone":"+91-9876543211",
     "type":"ALS","location":"North Post",    "lat":14.4820,"lng":75.9310,
     "status":"available","assigned_case":None,"assigned_risk":None,"current_phase":"available",
     "equipment":["defibrillator","ventilator","cardiac monitor","IV kit"],
     "destination_hospital_id":None,"destination_hospital_name":None,
     "destination_hospital_lat":None,"destination_hospital_lng":None,
     "patient_location_lat":None,"patient_location_lng":None,
     "patient_description":None,"case_id":None,
     "maintenance_status":"good","fuel_pct":75,"last_maintenance":"2024-01-20","notes":""},
    {"id":"AMB-07","driver":"Manoj Kumar",   "phone":"+91-9876543212",
     "type":"BLS","location":"West Unit",     "lat":14.4590,"lng":75.9100,
     "status":"available","assigned_case":None,"assigned_risk":None,"current_phase":"available",
     "equipment":["stretcher","oxygen","first aid","spine board"],
     "destination_hospital_id":None,"destination_hospital_name":None,
     "destination_hospital_lat":None,"destination_hospital_lng":None,
     "patient_location_lat":None,"patient_location_lng":None,
     "patient_description":None,"case_id":None,
     "maintenance_status":"needs_service","fuel_pct":45,"last_maintenance":"2023-12-10","notes":"Brake pads due"},
    {"id":"AMB-12","driver":"Sunita Reddy",  "phone":"+91-9876543213",
     "type":"BLS","location":"South Base",    "lat":14.4520,"lng":75.9280,
     "status":"available","assigned_case":None,"assigned_risk":None,"current_phase":"available",
     "equipment":["stretcher","oxygen","first aid","spine board"],
     "destination_hospital_id":None,"destination_hospital_name":None,
     "destination_hospital_lat":None,"destination_hospital_lng":None,
     "patient_location_lat":None,"patient_location_lng":None,
     "patient_description":None,"case_id":None,
     "maintenance_status":"good","fuel_pct":90,"last_maintenance":"2024-01-25","notes":""},
]

# Scene time per risk level (minutes)
SCENE_TIME = {"Critical": 20, "Urgent": 15, "Low": 10}

# Hospital transport time (minutes) - time to drive from scene to hospital
HOSPITAL_TRANSPORT_TIME = 2

# Priority value — lower = more urgent
PRIORITY = {"Critical": 1, "Urgent": 2, "Low": 3}

# ─── Priority Queue ───────────────────────────────────────────────────
# Each entry: dict with keys: case_id, description, lat, lng, risk,
#             queued_at, caller_name, caller_phone, resolve_fn (optional)
WAITING_QUEUE: list[dict] = []


def get_queue() -> list:
    """Return current waiting queue (safe copy, no callbacks)."""
    return [
        {k: v for k, v in e.items() if k != "resolve_fn"}
        for e in WAITING_QUEUE
    ]


def queue_size() -> int:
    return len(WAITING_QUEUE)


def _enqueue(entry: dict):
    """Insert into queue sorted by priority (Critical first)."""
    WAITING_QUEUE.append(entry)
    WAITING_QUEUE.sort(key=lambda x: PRIORITY.get(x["risk"], 99))


def _dequeue() -> Optional[dict]:
    """Pop the highest-priority waiting case."""
    if WAITING_QUEUE:
        return WAITING_QUEUE.pop(0)
    return None


def remove_from_queue(case_id: str) -> bool:
    """Remove a specific case from the queue (e.g. cancelled)."""
    global WAITING_QUEUE
    before = len(WAITING_QUEUE)
    WAITING_QUEUE = [e for e in WAITING_QUEUE if e["case_id"] != case_id]
    return len(WAITING_QUEUE) < before


# ─── Geometry ─────────────────────────────────────────────────────────
def haversine(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def estimate_eta(distance_km: float, risk: str) -> int:
    """
    Estimate ETA in minutes based on distance and risk level.
    Uses average speed: 30 km/h in city, faster for Critical (40 km/h)
    """
    if distance_km <= 0:
        return 1

    # Speed depends on risk priority
    speed_kmh = 40 if risk == "Critical" else (35 if risk == "Urgent" else 30)

    # Time to reach = distance / speed, convert to minutes
    eta_minutes = int((distance_km / speed_kmh) * 60)

    # Add 1 minute for scene time (loading patient)
    eta_minutes += 1

    # Minimum 1 minute, maximum 30 minutes
    return max(1, min(eta_minutes, 30))


# ─── Priority pool selection ──────────────────────────────────────────
def _select_pool(available: list, risk: str) -> tuple:
    als = [a for a in available if a["type"] == "ALS"]
    bls = [a for a in available if a["type"] == "BLS"]
    if risk == "Critical":
        if als: return als, "ALS unit (Critical priority)"
        return bls,  "WARNING: No ALS — BLS dispatched for Critical"
    if risk == "Low":
        if bls: return bls, "BLS unit (preserving ALS for Critical)"
        return als, "NOTE: No BLS — ALS used for Low case"
    return available, "Nearest available unit (Urgent)"


# ─── Preemption ───────────────────────────────────────────────────────
def _try_preempt(incident_lat: float, incident_lng: float,
                  risk: str) -> Optional[dict]:
    """
    If a Critical case has no available units, try to steal a unit
    currently assigned to a lower-priority case.

    Preemption order:
      Critical can steal from: Low → Urgent (never from Critical)
      Urgent  can steal from:  Low only
      Low     cannot preempt anyone
    """
    if risk == "Low":
        return None

    steal_from = []
    if risk == "Critical":
        steal_from = ["Low", "Urgent"]   # prefer stealing Low first
    elif risk == "Urgent":
        steal_from = ["Low"]

    for victim_risk in steal_from:
        victims = [
            a for a in AMBULANCES
            if a["status"] == "dispatched" and a["assigned_risk"] == victim_risk
        ]
        if not victims:
            continue

        # Among victims pick nearest to new incident
        scored = [(haversine(incident_lat, incident_lng, a["lat"], a["lng"]), a)
                  for a in victims]
        scored.sort(key=lambda x: x[0])
        dist, chosen = scored[0]

        # Queue the victim's case so it gets the next free unit
        if chosen["assigned_case"] and chosen["assigned_risk"]:
            # Use original patient location from the ambulance's tracking data
            victim_lat = chosen.get("patient_location_lat", chosen["lat"])
            victim_lng = chosen.get("patient_location_lng", chosen["lng"])
            _enqueue({
                "case_id":     chosen["assigned_case"],
                "description": f"[Re-queued: preempted by {risk} case]",
                "lat":         victim_lat,
                "lng":         victim_lng,
                "risk":        chosen["assigned_risk"],
                "queued_at":   datetime.now().strftime("%H:%M:%S"),
                "caller_name": "System",
                "caller_phone":"—",
                "resolve_fn":  None,
            })

        eta = estimate_eta(dist, risk)
        chosen["assigned_case"] = None
        chosen["assigned_risk"] = None

        return {
            "id":          chosen["id"],
            "driver":      chosen["driver"],
            "phone":       chosen["phone"],
            "type":        chosen["type"],
            "location":    chosen["location"],
            "distance_km": round(dist, 2),
            "eta_minutes": eta,
            "equipment":   chosen["equipment"],
            "dispatch_note": (
                f"PREEMPTED from {victim_risk} case — "
                f"{victim_risk} case re-queued for next available unit"
            ),
        }

    return None


# ─── Main dispatch ────────────────────────────────────────────────────
def get_nearest_ambulance(incident_lat: float, incident_lng: float,
                           risk: str) -> Optional[dict]:
    """
    Returns ambulance dict if one can be dispatched immediately,
    or None if the case must be queued.
    Preemption is attempted before queuing for Critical/Urgent.
    """
    available = [a for a in AMBULANCES if a["status"] == "available"]

    if available:
        pool, note = _select_pool(available, risk)
        scored = [(haversine(incident_lat, incident_lng, a["lat"], a["lng"]), a)
                  for a in pool]
        scored.sort(key=lambda x: x[0])
        dist, chosen = scored[0]
        eta = estimate_eta(dist, risk)
        return {
            "id":          chosen["id"],
            "driver":      chosen["driver"],
            "phone":       chosen["phone"],
            "type":        chosen["type"],
            "location":    chosen["location"],
            "distance_km": round(dist, 2),
            "eta_minutes": eta,
            "equipment":   chosen["equipment"],
            "dispatch_note": note,
        }

    # No unit available — try preemption
    preempted = _try_preempt(incident_lat, incident_lng, risk)
    if preempted:
        return preempted

    # Cannot dispatch now — caller must queue this case
    return None


# ─── Status management ────────────────────────────────────────────────
def mark_ambulance_dispatched(amb_id: str, case_id: str,
                               risk: str = "Unknown") -> bool:
    for a in AMBULANCES:
        if a["id"] == amb_id:
            a["status"]        = "dispatched"
            a["assigned_case"] = case_id
            a["assigned_risk"] = risk
            return True
    return False


def set_dispatch_details(amb_id: str, case_id: str, patient_lat: float, patient_lng: float,
                        patient_description: str, hospital_id: str, hospital_name: str,
                        hospital_lat: float, hospital_lng: float) -> bool:
    """Set complete dispatch details including tracking info."""
    for a in AMBULANCES:
        if a["id"] == amb_id:
            a["case_id"] = case_id
            a["patient_location_lat"] = patient_lat
            a["patient_location_lng"] = patient_lng
            a["patient_description"] = patient_description
            a["destination_hospital_id"] = hospital_id
            a["destination_hospital_name"] = hospital_name
            a["destination_hospital_lat"] = hospital_lat
            a["destination_hospital_lng"] = hospital_lng
            return True
    return False


def clear_dispatch_details(amb_id: str) -> bool:
    """Clear dispatch details when ambulance becomes available."""
    for a in AMBULANCES:
        if a["id"] == amb_id:
            a["case_id"] = None
            a["patient_location_lat"] = None
            a["patient_location_lng"] = None
            a["patient_description"] = None
            a["destination_hospital_id"] = None
            a["destination_hospital_name"] = None
            a["destination_hospital_lat"] = None
            a["destination_hospital_lng"] = None
            return True
    return False


def mark_ambulance_available(amb_id: str) -> bool:
    for a in AMBULANCES:
        if a["id"] == amb_id:
            a["status"]        = "available"
            a["assigned_case"] = None
            a["assigned_risk"] = None
            # Clear all dispatch tracking details using the dedicated function
            clear_dispatch_details(amb_id)
            return True
    return False


# Legacy alias
def mark_ambulance_busy(amb_id: str) -> bool:
    return mark_ambulance_dispatched(amb_id, "unknown", "Unknown")


# ─── Auto-release + auto-assign ───────────────────────────────────────
# Timeline progression times (in seconds)
PICKUP_DELAY = 60  # 1 minute after dispatch to pick up patient
ARRIVAL_DELAY = 60  # 1 minute after pickup to arrive at hospital

def schedule_release(amb_id: str, risk: str, eta_minutes: int,
                     on_release_callback=None, hospital_id=None, case_id=None):
    """
    Automatic timeline progression:
    1. At dispatch: phase = dispatched (set in decision.py)
    2. After PICKUP_DELAY (1 min): phase = patient_picked, notify hospital
    3. After ARRIVAL_DELAY more (1 min): phase = delivered, release ambulance

    Timeline: dispatch → pickup (1 min) → delivered (1 min) → available
    """
    # Get case_id from ambulance if not provided
    if not case_id:
        for a in AMBULANCES:
            if a["id"] == amb_id:
                case_id = a.get("case_id")
                break

    async def _auto_progress():
        # Wait 1 minute then mark as picked up
        await asyncio.sleep(PICKUP_DELAY)
        update_ambulance_status(amb_id, "patient_picked", case_id)
        print(f"[AMB] {amb_id} - Patient picked up (auto-progress)")

        # Notify hospital about incoming patient
        if hospital_id:
            from backend.hospital import notify_hospital, get_hospital_list
            # Find hospital name
            hospital_name = hospital_id
            for h in get_hospital_list():
                if h["id"] == hospital_id:
                    hospital_name = h["name"]
                    break
            notify_hospital(hospital_id, case_id or "unknown", "Patient", 1,
                          "Patient picked up", risk)
            print(f"[HOSPITAL] {hospital_name} notified - patient picked up")

        # Broadcast picked up event
        from backend.decision import _broadcast_fn
        if _broadcast_fn:
            try:
                await _broadcast_fn({
                    "type": "patient_picked_up",
                    "data": {
                        "case_id": case_id,
                        "ambulance": amb_id,
                        "hospital": hospital_name,
                        "message": f"Patient picked up by {amb_id}. Auto-progressing to hospital."
                    }
                })
            except Exception:
                pass  # Broadcast failed - non-critical

        # Wait 1 more minute then mark as delivered
        await asyncio.sleep(ARRIVAL_DELAY)
        update_ambulance_status(amb_id, "delivered", case_id)
        print(f"[AMB] {amb_id} - Patient delivered at hospital (auto-progress)")

        # Now release ambulance
        mark_ambulance_available(amb_id)
        print(f"[AMB] {amb_id} available (after auto-progress)")

        # Fill hospital bed (patient now occupies it)
        if hospital_id:
            import backend.hospital as hos_mod
            hos_mod.fill_bed(hospital_id)
            result = hos_mod.remove_incoming_patient(hospital_id, case_id)
            print(f"[HOSPITAL] Bed filled at {hospital_id}")
            print(f"[DEBUG] Removed incoming {case_id}: {result}")

        # Broadcast delivered event
        if _broadcast_fn:
            try:
                await _broadcast_fn({
                    "type": "patient_delivered",
                    "data": {
                        "case_id": case_id,
                        "ambulance": amb_id,
                        "message": f"Patient delivered to hospital. {amb_id} is now available."
                    }
                })
            except Exception:
                pass  # Broadcast failed - non-critical

        # Auto-assign to next waiting case
        next_case = _dequeue()
        if next_case:
            print(f"[QUEUE] Auto-assigning {amb_id} to queued case "
                  f"{next_case['case_id']} ({next_case['risk']})")
            if on_release_callback:
                try:
                    await on_release_callback(amb_id, next_case)
                except Exception as e:
                    print(f"[QUEUE] Callback error: {e}")

    def _sync_progress():
        """Synchronous version for when event loop is not running."""
        import time
        # Phase 1: Wait 1 min, then pickup
        time.sleep(PICKUP_DELAY)
        update_ambulance_status(amb_id, "patient_picked", case_id)
        print(f"[AMB] {amb_id} - Patient picked up (auto-progress)")
        if hospital_id:
            from backend.hospital import notify_hospital, get_hospital_list
            hospital_name = hospital_id
            for h in get_hospital_list():
                if h["id"] == hospital_id:
                    hospital_name = h["name"]
                    break
            notify_hospital(hospital_id, case_id or "unknown", "Patient", 1,
                          "Patient picked up", risk)
            print(f"[HOSPITAL] {hospital_name} notified - patient picked up")

        # Phase 2: Wait 1 more min, then deliver
        time.sleep(ARRIVAL_DELAY)
        update_ambulance_status(amb_id, "delivered", case_id)
        print(f"[AMB] {amb_id} - Patient delivered (auto-progress)")

        # Release ambulance and hospital resources
        mark_ambulance_available(amb_id)
        print(f"[AMB] {amb_id} available (after auto-progress)")
        if hospital_id:
            import backend.hospital as hos_mod
            hos_mod.fill_bed(hospital_id)
            hos_mod.remove_incoming_patient(hospital_id, case_id)
            print(f"[HOSPITAL] Bed filled at {hospital_id}")

        # Broadcast delivered event
        from backend.decision import _broadcast_fn
        if _broadcast_fn:
            try:
                import asyncio
                asyncio.create_task(_broadcast_fn({
                    "type": "patient_delivered",
                    "data": {
                        "case_id": case_id,
                        "ambulance": amb_id,
                        "message": f"Patient delivered to hospital. {amb_id} is now available."
                    }
                }))
            except Exception:
                pass  # Broadcast failed - non-critical

        # Auto-assign to next waiting case
        next_case = _dequeue()
        if next_case:
            print(f"[QUEUE] Auto-assigning {amb_id} to queued case "
                  f"{next_case['case_id']} ({next_case['risk']})")
            if on_release_callback:
                try:
                    # Run callback in a new event loop if needed
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(on_release_callback(amb_id, next_case))
                    except RuntimeError:
                        pass
                except Exception as e:
                    print(f"[QUEUE] Callback error: {e}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_auto_progress())
        else:
            import threading
            threading.Thread(target=_sync_progress, daemon=True).start()
    except RuntimeError:
        import threading
        threading.Thread(target=_sync_progress, daemon=True).start()


# ─── Ambulance CRUD ───────────────────────────────────────────────────
def add_ambulance(ambulance_data: dict) -> dict:
    """Add a new ambulance to the fleet. Returns the new ambulance."""
    # Generate ID if not provided
    if "id" not in ambulance_data:
        max_id = 0
        for a in AMBULANCES:
            if a["id"].startswith("AMB-"):
                try:
                    num = int(a["id"].split("-")[1])
                    max_id = max(max_id, num)
                except (ValueError, IndexError):
                    pass  # Skip invalid ID formats
        ambulance_data["id"] = f"AMB-{max_id + 1:02d}"

    # Set defaults
    ambulance_data.setdefault("driver", "Unassigned Driver")
    ambulance_data.setdefault("phone", "+91-9876500000")
    ambulance_data.setdefault("type", "BLS")
    ambulance_data.setdefault("location", "HQ")
    ambulance_data.setdefault("lat", 14.4700)
    ambulance_data.setdefault("lng", 75.9300)
    ambulance_data.setdefault("status", "available")
    ambulance_data.setdefault("assigned_case", None)
    ambulance_data.setdefault("assigned_risk", None)
    ambulance_data.setdefault("current_phase", "available")

    # Equipment based on type
    if ambulance_data["type"] == "ALS":
        ambulance_data.setdefault("equipment", ["defibrillator", "ventilator", "cardiac monitor", "IV kit"])
    else:
        ambulance_data.setdefault("equipment", ["stretcher", "oxygen", "first aid", "spine board"])

    # Tracking fields
    ambulance_data.setdefault("destination_hospital_id", None)
    ambulance_data.setdefault("destination_hospital_name", None)
    ambulance_data.setdefault("destination_hospital_lat", None)
    ambulance_data.setdefault("destination_hospital_lng", None)
    ambulance_data.setdefault("patient_location_lat", None)
    ambulance_data.setdefault("patient_location_lng", None)
    ambulance_data.setdefault("patient_description", None)
    ambulance_data.setdefault("case_id", None)
    ambulance_data.setdefault("maintenance_status", "good")
    ambulance_data.setdefault("fuel_pct", 80)
    ambulance_data.setdefault("last_maintenance", datetime.now().strftime("%Y-%m-%d"))
    ambulance_data.setdefault("notes", "")

    AMBULANCES.append(ambulance_data)
    return ambulance_data


def delete_ambulance(amb_id: str) -> bool:
    """Remove an ambulance from the fleet."""
    global AMBULANCES
    before = len(AMBULANCES)
    AMBULANCES = [a for a in AMBULANCES if a["id"] != amb_id]
    return len(AMBULANCES) < before


def update_ambulance_details(amb_id: str, updates: dict) -> Optional[dict]:
    """Update ambulance details."""
    for a in AMBULANCES:
        if a["id"] == amb_id:
            for key, value in updates.items():
                if key != "id" and value is not None:
                    a[key] = value
            return a
    return None


# ─── Fleet status ─────────────────────────────────────────────────────
def get_fleet_status() -> list:
    return [dict(a) for a in AMBULANCES]


def get_available_count() -> int:
    return sum(1 for a in AMBULANCES if a["status"] == "available")


# ─── Extended Status Tracking ───────────────────────────────────────────
# Status flow: available → dispatched → enroute → arrived → patient_picked → hospital_enroute → delivered → available
AMBULANCE_PHASES = [
    "available", "dispatched", "enroute", "arrived",
    "patient_picked", "hospital_enroute", "delivered"
]


def get_ambulance_by_id(amb_id: str) -> Optional[dict]:
    """Get ambulance details by ID."""
    for a in AMBULANCES:
        if a["id"] == amb_id:
            return dict(a)
    return None


def update_ambulance_status(amb_id: str, status: str, case_id: str = None) -> bool:
    """
    Update ambulance status with phase tracking.
    Valid statuses: dispatched, enroute, arrived, patient_picked, hospital_enroute, delivered
    """
    if status not in AMBULANCE_PHASES:
        return False

    for a in AMBULANCES:
        if a["id"] == amb_id:
            a["current_phase"] = status
            if case_id:
                a["assigned_case"] = case_id
            # Record phase start time for movement tracking
            set_phase_start_time(amb_id, status)
            return True
    return False


def get_all_ambulances_status() -> list:
    """Get status of all ambulances including tracking info for main dashboard."""
    return [
        {
            "id": a["id"],
            "driver": a["driver"],
            "phone": a["phone"],
            "type": a["type"],
            "status": a["status"],
            "current_phase": a.get("current_phase", "available"),
            "assigned_case": a.get("assigned_case"),
            "location": a["location"],
            "lat": a["lat"],
            "lng": a["lng"],
            # Tracking info
            "tracking": {
                "case_id": a.get("case_id"),
                "patient_description": a.get("patient_description"),
                "patient_location_lat": a.get("patient_location_lat"),
                "patient_location_lng": a.get("patient_location_lng"),
                "destination_hospital_id": a.get("destination_hospital_id"),
                "destination_hospital_name": a.get("destination_hospital_name"),
                "destination_hospital_lat": a.get("destination_hospital_lat"),
                "destination_hospital_lng": a.get("destination_hospital_lng"),
            },
            # Movement simulation
            "movement": get_ambulance_movement(a),
        }
        for a in AMBULANCES
    ]


# ─── Movement Simulation ────────────────────────────────────────────────
# Track phase start times for movement calculation
PHASE_TIMES: dict = {}  # amb_id -> {phase: timestamp}


def get_phase_start_time(amb_id: str, phase: str) -> Optional[datetime]:
    """Get when a phase started."""
    if amb_id not in PHASE_TIMES:
        return None
    return PHASE_TIMES[amb_id].get(phase)


def set_phase_start_time(amb_id: str, phase: str):
    """Record when a phase started."""
    if amb_id not in PHASE_TIMES:
        PHASE_TIMES[amb_id] = {}
    PHASE_TIMES[amb_id][phase] = datetime.now()


def get_ambulance_movement(amb: dict) -> dict:
    """
    Calculate current position and progress for an ambulance.
    Returns current lat/lng, progress %, and ETA to destination.
    Uses time elapsed since phase start for real-time movement.
    """
    phase = amb.get("current_phase", "available")
    if phase == "available":
        return {"phase": "available", "progress": 0, "current_lat": amb["lat"], "current_lng": amb["lng"], "speed_kmh": 0}

    # Get key locations
    start_lat, start_lng = amb["lat"], amb["lng"]
    patient_lat = amb.get("patient_location_lat")
    patient_lng = amb.get("patient_location_lng")
    hospital_lat = amb.get("destination_hospital_lat")
    hospital_lng = amb.get("destination_hospital_lng")

    # Get phase start time for timing calculation
    phase_start = PHASE_TIMES.get(amb["id"], {}).get(phase)
    if phase_start:
        elapsed_seconds = (datetime.now() - phase_start).total_seconds()
    else:
        elapsed_seconds = 0

    # Determine what route the ambulance is on
    route_type = None
    if phase in ["dispatched", "enroute"]:
        route_type = "to_patient"
    elif phase in ["arrived", "patient_picked"]:
        route_type = "to_hospital"
    elif phase == "hospital_enroute":
        route_type = "to_hospital"

    # Calculate position based on route and elapsed time
    if route_type == "to_patient" and patient_lat and patient_lng:
        # Heading to patient
        distance_total = haversine(start_lat, start_lng, patient_lat, patient_lng)
        if distance_total > 0:
            # Average speed 35 km/h, convert to degrees
            speed_deg_per_sec = (35 / 111) / 3600  # ~0.000097 degrees per second
            distance_covered = speed_deg_per_sec * elapsed_seconds * 1000  # Convert to approx km then degrees

            # Calculate progress percentage
            progress = min(50, int((elapsed_seconds / 60) * 50))  # 50% for first leg, takes ~1 min

            # Interpolate position
            ratio = min(1, distance_covered / distance_total)
            current_lat = start_lat + (patient_lat - start_lat) * ratio
            current_lng = start_lng + (patient_lng - start_lng) * ratio

            # Calculate ETA
            remaining_dist = distance_total - (distance_total * ratio)
            eta_seconds = int(remaining_dist / 35 * 3600) if distance_total > 0 else 0

            return {
                "phase": phase,
                "progress": progress,
                "current_lat": round(current_lat, 6),
                "current_lng": round(current_lng, 6),
                "eta_seconds": max(0, eta_seconds),
                "speed_kmh": 35,
                "route": "to_patient",
                "distance_km": round(distance_total, 2)
            }

    elif route_type == "to_hospital" and patient_lat and patient_lng and hospital_lat and hospital_lng:
        # Heading to hospital from patient location
        distance_total = haversine(patient_lat, patient_lng, hospital_lat, hospital_lng)
        if distance_total > 0:
            # After pickup, progress from 50% to 100%
            speed_deg_per_sec = (35 / 111) / 3600
            distance_covered = speed_deg_per_sec * elapsed_seconds * 1000

            # Progress from 50% (after pickup) to 100%
            time_to_cover = 60  # Assume 1 minute to reach hospital
            progress = min(100, 50 + int((elapsed_seconds / time_to_cover) * 50))

            # Interpolate position from patient to hospital
            ratio = min(1, distance_covered / distance_total)
            current_lat = patient_lat + (hospital_lat - patient_lat) * ratio
            current_lng = patient_lng + (hospital_lng - patient_lng) * ratio

            remaining_dist = distance_total - (distance_total * ratio)
            eta_seconds = int(remaining_dist / 35 * 3600) if distance_total > 0 else 0

            return {
                "phase": phase,
                "progress": progress,
                "current_lat": round(current_lat, 6),
                "current_lng": round(current_lng, 6),
                "eta_seconds": max(0, eta_seconds),
                "speed_kmh": 35,
                "route": "to_hospital",
                "distance_km": round(distance_total, 2)
            }

    # Fallback - return current position
    return {
        "phase": phase,
        "progress": 0,
        "current_lat": start_lat,
        "current_lng": start_lng,
        "eta_seconds": 0,
        "speed_kmh": 0,
        "route": "unknown"
    }


def update_ambulance_position(amb_id: str, new_lat: float, new_lng: float) -> bool:
    """Manually update ambulance GPS coordinates."""
    for a in AMBULANCES:
        if a["id"] == amb_id:
            a["lat"] = new_lat
            a["lng"] = new_lng
            return True
    return False


# ─── Maintenance Tracking ───────────────────────────────────────────────
def update_maintenance_status(amb_id: str, status: str, fuel_pct: int = None, notes: str = None) -> bool:
    """Update ambulance maintenance status."""
    valid_statuses = ["good", "needs_service", "maintenance", "out_of_service"]
    if status not in valid_statuses:
        return False

    for a in AMBULANCES:
        if a["id"] == amb_id:
            a["maintenance_status"] = status
            if fuel_pct is not None:
                a["fuel_pct"] = max(0, min(100, fuel_pct))
            if notes is not None:
                a["notes"] = notes
            if status in ["needs_service", "maintenance", "out_of_service"]:
                # Set status to unavailable if needs maintenance
                if a["status"] == "available":
                    a["status"] = "maintenance"
            return True
    return False


def record_maintenance(amb_id: str) -> bool:
    """Record maintenance completed, reset status to good."""
    today = datetime.now().strftime("%Y-%m-%d")
    for a in AMBULANCES:
        if a["id"] == amb_id:
            a["maintenance_status"] = "good"
            a["last_maintenance"] = today
            a["notes"] = ""
            # Restore availability if was in maintenance
            if a.get("status") == "maintenance":
                a["status"] = "available"
            return True
    return False


def get_ambulance_maintenance(amb_id: str) -> Optional[dict]:
    """Get maintenance info for an ambulance."""
    for a in AMBULANCES:
        if a["id"] == amb_id:
            return {
                "ambulance_id": a["id"],
                "maintenance_status": a.get("maintenance_status", "good"),
                "fuel_pct": a.get("fuel_pct", 0),
                "last_maintenance": a.get("last_maintenance", "Unknown"),
                "notes": a.get("notes", ""),
            }
    return None


def get_fleet_maintenance() -> list:
    """Get maintenance status for entire fleet."""
    return [
        {
            "ambulance_id": a["id"],
            "driver": a["driver"],
            "type": a["type"],
            "maintenance_status": a.get("maintenance_status", "good"),
            "fuel_pct": a.get("fuel_pct", 0),
            "last_maintenance": a.get("last_maintenance", "Unknown"),
            "notes": a.get("notes", ""),
            "status": a["status"],
        }
        for a in AMBULANCES
    ]
