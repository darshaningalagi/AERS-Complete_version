import uuid
from datetime import datetime
from backend.predictor import predict_risk
from backend.ambulance import (
    get_nearest_ambulance, mark_ambulance_dispatched,
    mark_ambulance_busy, schedule_release,
    _enqueue, get_queue, queue_size
)
from backend.hospital import get_best_hospital
from backend.database import save_case, get_recent_cases, log_ambulance_event

# Broadcast hook — set by app.py
_broadcast_fn = None

def set_decision_broadcast(fn):
    global _broadcast_fn
    _broadcast_fn = fn


async def _queue_resolve_callback(amb_id: str, queued_entry: dict):
    """Called when a unit is released and a queued case is next."""
    from backend.ambulance import mark_ambulance_dispatched, schedule_release, haversine, estimate_eta, AMBULANCES

    # Find the unit that just became free
    amb_obj = next((a for a in AMBULANCES if a["id"] == amb_id), None)
    if not amb_obj:
        return

    risk = queued_entry["risk"]
    dist = haversine(queued_entry["lat"], queued_entry["lng"],
                     amb_obj["lat"], amb_obj["lng"])
    eta  = estimate_eta(dist, risk)

    mark_ambulance_dispatched(amb_id, queued_entry["case_id"], risk)
    schedule_release(amb_id, risk, eta, on_release_callback=_queue_resolve_callback)

    # Build a status update and broadcast it
    if _broadcast_fn:
        await _broadcast_fn({
            "type": "queue_resolved",
            "data": {
                "case_id":   queued_entry["case_id"],
                "risk":      risk,
                "ambulance": amb_id,
                "eta":       eta,
                "message":   (
                    f"Unit {amb_id} auto-assigned to queued "
                    f"{risk} case {queued_entry['case_id']} "
                    f"— ETA {eta} min"
                ),
            }
        })


def run_decision_engine(
    description: str,
    incident_lat: float = 14.4673,
    incident_lng: float = 75.9238,
    caller_name: str  = "Anonymous",
    caller_phone: str = "Unknown",
) -> dict:

    # ── 1. Triage
    triage = predict_risk(description)
    if not triage["success"]:
        return {"success": False, "error": triage["error"]}
    risk = triage["risk_level"]

    # ── 2. Dispatch
    case_id   = "EM-" + str(uuid.uuid4())[:8].upper()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ambulance = get_nearest_ambulance(incident_lat, incident_lng, risk)

    if ambulance:
        mark_ambulance_dispatched(ambulance["id"], case_id, risk)
        schedule_release(
            ambulance["id"], risk, ambulance["eta_minutes"],
            on_release_callback=_queue_resolve_callback
        )
        dispatch_status = "dispatched"
        try:
            log_ambulance_event(ambulance["id"], "dispatched", case_id)
        except Exception:
            pass
    else:
        # All units busy and preemption failed → queue the case
        _enqueue({
            "case_id":     case_id,
            "description": description,
            "lat":         incident_lat,
            "lng":         incident_lng,
            "risk":        risk,
            "queued_at":   datetime.now().strftime("%H:%M:%S"),
            "caller_name": caller_name,
            "caller_phone":caller_phone,
            "resolve_fn":  _queue_resolve_callback,
        })
        dispatch_status = "queued"

    # ── 3. Hospital
    hospital = get_best_hospital(incident_lat, incident_lng, description, risk, risk)

    # ── 4. Build response
    q_size = queue_size()
    response = {
        "success":    True,
        "case_id":    case_id,
        "timestamp":  timestamp,
        "caller":     {"name": caller_name, "phone": caller_phone},
        "incident":   {"description": description, "lat": incident_lat, "lng": incident_lng},
        "triage": {
            "risk_level":          risk,
            "confidence":          triage["confidence"],
            "probabilities":       triage["probabilities"],
            "color":               triage["color"],
            "response_time_target":triage["response_time"],
            "recommended_action":  triage["action"],
            "priority":            triage["priority"],
        },
        "dispatch": {
            "status":       dispatch_status,
            "ambulance":    ambulance,
            "queue_position": q_size if dispatch_status == "queued" else None,
            "queue_message": (
                f"All units busy. Your {risk} case is #{q_size} in queue. "
                f"A unit will be auto-assigned when available."
                if dispatch_status == "queued" else None
            ),
        },
        "hospital": hospital,
        "timeline": [
            {"step":"Emergency received",  "status":"done",   "time":timestamp},
            {"step":"AI triage completed", "status":"done",   "time":timestamp},
            {"step":(
                f"Ambulance {ambulance['id']} dispatched"
                if ambulance else f"Queued — position #{q_size}"
             ),
             "status":"active" if ambulance else "queued","time":timestamp},
            {"step":f"{hospital['name'] if hospital else 'N/A'} notified",
             "status":"pending","time":None},
            {"step":"Unit arrived at scene","status":"pending","time":None},
            {"step":"Patient transferred",  "status":"pending","time":None},
        ],
    }

    # ── 5. Persist
    try:
        save_case(response)
    except Exception:
        pass

    return response


def get_case_history() -> list:
    try:
        rows = get_recent_cases(20)
        return [
            {
                "case_id":    r["case_id"],
                "timestamp":  r["timestamp"],
                "risk":       r["risk_level"],
                "description":r["description"],
                "ambulance":  r["ambulance_id"],
                "hospital":   r["hospital_name"],
            }
            for r in rows
        ]
    except Exception:
        return []
