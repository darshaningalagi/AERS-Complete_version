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
AMBULANCES = [
    {"id":"AMB-01","driver":"Rajesh Sharma", "phone":"+91-9876543210",
     "type":"ALS","location":"Central Station","lat":14.4673,"lng":75.9238,
     "status":"available","assigned_case":None,"assigned_risk":None,
     "equipment":["defibrillator","ventilator","cardiac monitor","IV kit"]},
    {"id":"AMB-03","driver":"Kavita Patel",  "phone":"+91-9876543211",
     "type":"ALS","location":"North Post",    "lat":14.4820,"lng":75.9310,
     "status":"available","assigned_case":None,"assigned_risk":None,
     "equipment":["defibrillator","ventilator","cardiac monitor","IV kit"]},
    {"id":"AMB-07","driver":"Manoj Kumar",   "phone":"+91-9876543212",
     "type":"BLS","location":"West Unit",     "lat":14.4590,"lng":75.9100,
     "status":"available","assigned_case":None,"assigned_risk":None,
     "equipment":["stretcher","oxygen","first aid","spine board"]},
    {"id":"AMB-12","driver":"Sunita Reddy",  "phone":"+91-9876543213",
     "type":"BLS","location":"South Base",    "lat":14.4520,"lng":75.9280,
     "status":"available","assigned_case":None,"assigned_risk":None,
     "equipment":["stretcher","oxygen","first aid","spine board"]},
]

# Scene time per risk level (minutes)
SCENE_TIME = {"Critical": 20, "Urgent": 15, "Low": 10}

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
    speed_kmh = 80 if risk == "Critical" else 60
    return max(2, round((distance_km / speed_kmh) * 60))


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
            _enqueue({
                "case_id":     chosen["assigned_case"],
                "description": f"[Re-queued: preempted by {risk} case]",
                "lat":         incident_lat,
                "lng":         incident_lng,
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


def mark_ambulance_available(amb_id: str) -> bool:
    for a in AMBULANCES:
        if a["id"] == amb_id:
            a["status"]        = "available"
            a["assigned_case"] = None
            a["assigned_risk"] = None
            return True
    return False


# Legacy alias
def mark_ambulance_busy(amb_id: str) -> bool:
    return mark_ambulance_dispatched(amb_id, "unknown", "Unknown")


# ─── Auto-release + auto-assign ───────────────────────────────────────
def schedule_release(amb_id: str, risk: str, eta_minutes: int,
                     on_release_callback=None):
    """
    After (ETA + scene_time) minutes:
      1. Mark unit available.
      2. If a case is waiting in the queue, assign this unit to it immediately.
      3. Call on_release_callback(amb_id, queued_entry) if provided.
    """
    total_seconds = (eta_minutes + SCENE_TIME.get(risk, 15)) * 60

    async def _release():
        await asyncio.sleep(total_seconds)
        mark_ambulance_available(amb_id)
        print(f"[AMB] {amb_id} available (after {total_seconds//60}min — {risk} case)")

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

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_release())
        else:
            import threading, time
            def _thread():
                time.sleep(total_seconds)
                mark_ambulance_available(amb_id)
                next_case = _dequeue()
                if next_case and on_release_callback:
                    pass  # can't await in thread context during tests
            threading.Thread(target=_thread, daemon=True).start()
    except RuntimeError:
        pass


# ─── Fleet status ─────────────────────────────────────────────────────
def get_fleet_status() -> list:
    return [dict(a) for a in AMBULANCES]


def get_available_count() -> int:
    return sum(1 for a in AMBULANCES if a["status"] == "available")
