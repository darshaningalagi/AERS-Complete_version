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
     "patient_description":None,"case_id":None},
    {"id":"AMB-03","driver":"Kavita Patel",  "phone":"+91-9876543211",
     "type":"ALS","location":"North Post",    "lat":14.4820,"lng":75.9310,
     "status":"available","assigned_case":None,"assigned_risk":None,"current_phase":"available",
     "equipment":["defibrillator","ventilator","cardiac monitor","IV kit"],
     "destination_hospital_id":None,"destination_hospital_name":None,
     "destination_hospital_lat":None,"destination_hospital_lng":None,
     "patient_location_lat":None,"patient_location_lng":None,
     "patient_description":None,"case_id":None},
    {"id":"AMB-07","driver":"Manoj Kumar",   "phone":"+91-9876543212",
     "type":"BLS","location":"West Unit",     "lat":14.4590,"lng":75.9100,
     "status":"available","assigned_case":None,"assigned_risk":None,"current_phase":"available",
     "equipment":["stretcher","oxygen","first aid","spine board"],
     "destination_hospital_id":None,"destination_hospital_name":None,
     "destination_hospital_lat":None,"destination_hospital_lng":None,
     "patient_location_lat":None,"patient_location_lng":None,
     "patient_description":None,"case_id":None},
    {"id":"AMB-12","driver":"Sunita Reddy",  "phone":"+91-9876543213",
     "type":"BLS","location":"South Base",    "lat":14.4520,"lng":75.9280,
     "status":"available","assigned_case":None,"assigned_risk":None,"current_phase":"available",
     "equipment":["stretcher","oxygen","first aid","spine board"],
     "destination_hospital_id":None,"destination_hospital_name":None,
     "destination_hospital_lat":None,"destination_hospital_lng":None,
     "patient_location_lat":None,"patient_location_lng":None,
     "patient_description":None,"case_id":None},
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
    # Return 1 minute to reach patient + 1 minute to hospital = 2 min total
    return 2


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
            # Clear all dispatch tracking details
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
            except:
                pass

        # Wait 1 more minute then mark as delivered
        await asyncio.sleep(ARRIVAL_DELAY)
        update_ambulance_status(amb_id, "delivered", case_id)
        print(f"[AMB] {amb_id} - Patient delivered at hospital (auto-progress)")

        # Now release ambulance
        mark_ambulance_available(amb_id)
        print(f"[AMB] {amb_id} available (after auto-progress)")

        # Release hospital bed if patient was admitted and remove from incoming
        if hospital_id:
            import backend.hospital as hos_mod
            hos_mod.release_bed(hospital_id)
            result = hos_mod.remove_incoming_patient(hospital_id, case_id)
            print(f"[HOSPITAL] Bed released at {hospital_id}")
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
            except:
                pass

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
            hos_mod.release_bed(hospital_id)
            hos_mod.remove_incoming_patient(hospital_id, case_id)
            print(f"[HOSPITAL] Bed released at {hospital_id}")

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
            except:
                pass

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
            }
        }
        for a in AMBULANCES
    ]
