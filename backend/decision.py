import uuid
import asyncio
from datetime import datetime
from typing import Optional
from backend.predictor import predict_risk
from backend.ambulance import (
    get_nearest_ambulance, mark_ambulance_dispatched,
    mark_ambulance_busy, schedule_release,
    _enqueue, get_queue, queue_size, set_dispatch_details
)
from backend.hospital import get_best_hospital, occupy_bed, release_bed, get_hospital_list
from backend.database import save_case, get_recent_cases, log_ambulance_event

# Broadcast hook — set by app.py
_broadcast_fn = None

def set_decision_broadcast(fn):
    global _broadcast_fn
    _broadcast_fn = fn


async def _queue_resolve_callback(amb_id: str, queued_entry: dict):
    """Called when a unit is released and a queued case is next."""
    from backend.ambulance import mark_ambulance_dispatched, schedule_release, haversine, estimate_eta, AMBULANCES
    from backend.hospital import get_best_hospital, occupy_bed

    # Find the unit that just became free
    amb_obj = next((a for a in AMBULANCES if a["id"] == amb_id), None)
    if not amb_obj:
        return

    risk = queued_entry["risk"]
    desc = queued_entry.get("description", "Emergency case")
    lat = queued_entry.get("lat", 14.4673)
    lng = queued_entry.get("lng", 75.9238)

    dist = haversine(lat, lng, amb_obj["lat"], amb_obj["lng"])
    eta  = estimate_eta(dist, risk)

    # Get hospital and occupy bed
    hospital = get_best_hospital(lat, lng, desc, "emergency", risk)
    hospital_id = None
    if hospital:
        hospital_id = hospital["id"]
        occupy_bed(hospital_id)

    mark_ambulance_dispatched(amb_id, queued_entry["case_id"], risk)
    schedule_release(amb_id, risk, eta, on_release_callback=_queue_resolve_callback,
                      hospital_id=hospital_id)

    # Build a status update and broadcast it
    if _broadcast_fn:
        await _broadcast_fn({
            "type": "queue_resolved",
            "data": {
                "case_id":   queued_entry["case_id"],
                "risk":      risk,
                "amb_id": amb_id,
                "eta":       eta,
                "hospital":  hospital["name"] if hospital else None,
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

    # ── Hospital selection and ICU bed management
    hospital = get_best_hospital(incident_lat, incident_lng, description, "emergency", risk)

    if ambulance:
        # Occupy ICU bed when ambulance is dispatched
        hospital_id = None
        hospital_lat = None
        hospital_lng = None
        if hospital:
            hospital_id = hospital["id"]
            hospital_lat = hospital.get("lat")
            hospital_lng = hospital.get("lng")
            occupy_bed(hospital_id)

        mark_ambulance_dispatched(ambulance["id"], case_id, risk)

        # Set ambulance phase to dispatched
        from backend.ambulance import update_ambulance_status
        update_ambulance_status(ambulance["id"], "dispatched", case_id)

        # Set dispatch details for tracking
        set_dispatch_details(
            ambulance["id"], case_id,
            incident_lat, incident_lng, description,
            hospital["id"] if hospital else None,
            hospital["name"] if hospital else None,
            hospital_lat, hospital_lng
        )

        schedule_release(
            ambulance["id"], risk, ambulance["eta_minutes"],
            on_release_callback=_queue_resolve_callback,
            hospital_id=hospital_id,
            case_id=case_id
        )
        dispatch_status = "dispatched"

        # Send notification to driver
        if _broadcast_fn:
            asyncio.create_task(_broadcast_fn({
                "type": "driver_notification",
                "data": {
                    "amb_id": ambulance["id"],
                    "case_id": case_id,
                    "patient": {
                        "name": caller_name,
                        "phone": caller_phone,
                        "location_lat": incident_lat,
                        "location_lng": incident_lng,
                        "condition": description,
                        "risk_level": risk,
                    },
                    "hospital": {
                        "id": hospital["id"] if hospital else None,
                        "name": hospital["name"] if hospital else None,
                        "address": hospital["address"] if hospital else None,
                        "lat": hospital_lat,
                        "lng": hospital_lng,
                    },
                    "eta_minutes": ambulance["eta_minutes"],
                    "message": f"New emergency case! Patient: {caller_name}, Condition: {risk}",
                }
            }))

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
    # Map database status to display status
    def map_status(status):
        if status == "delivered":
            return "patient arrived at hospital"
        elif status == "picked_up":
            return "patient picked up"
        return "ongoing"

    try:
        rows = get_recent_cases(20)
        return [
            {
                "case_id":     r["case_id"],
                "timestamp":   r["timestamp"],
                "risk":        r["risk_level"],
                "description": r["description"],
                "ambulance":   r["ambulance_id"],
                "hospital":    r["hospital_name"],
                "patient_status": map_status(r.get("delivery_status", "ongoing")),
            }
            for r in rows
        ]
    except Exception:
        return []


# ─── Patient Call Interface Functions ─────────────────────────────────
def create_emergency_call(
    description: str,
    incident_lat: float = 14.4673,
    incident_lng: float = 75.9238,
    caller_name: str = "Anonymous",
    caller_phone: str = "Unknown",
) -> dict:
    """
    Create emergency call from patient interface.
    Returns full case response with all details.
    """
    return run_decision_engine(
        description=description,
        incident_lat=incident_lat,
        incident_lng=incident_lng,
        caller_name=caller_name,
        caller_phone=caller_phone,
    )


def get_case_status(case_id: str) -> Optional[dict]:
    """Get case status for patient tracking."""
    from backend.database import get_case_by_id
    case = get_case_by_id(case_id)
    if not case:
        return None

    # Get ambulance current phase
    amb_id = case.get("ambulance_id")
    phase = "pending"
    if amb_id:
        from backend.ambulance import get_ambulance_by_id
        amb = get_ambulance_by_id(amb_id)
        if amb:
            phase = amb.get("current_phase", "dispatched")

    return {
        "case_id": case["case_id"],
        "timestamp": case["timestamp"],
        "risk_level": case["risk_level"],
        "description": case["description"],
        "status": case.get("dispatch_status", "unknown"),
        "phase": phase,
        "ambulance_id": amb_id,
        "hospital": case["hospital_name"],
        "eta": case.get("ambulance_eta"),
    }


def get_patient_notification(case_id: str) -> Optional[dict]:
    """Get notification data for patient."""
    case = get_case_status(case_id)
    if not case:
        return None

    if case.get("ambulance_id"):
        from backend.ambulance import get_ambulance_by_id
        amb = get_ambulance_by_id(case["ambulance_id"])
        if amb:
            # Get delivery status from case
            delivery_status = case.get("phase", "dispatched")

            # Determine status based on delivery_status
            if delivery_status == "delivered":
                status = "delivered"
            elif delivery_status == "patient_picked":
                status = "picked_up"
            else:
                status = "dispatched"

            return {
                "case_id": case_id,
                "status": status,
                "ambulance": {
                    "id": amb["id"],
                    "driver": amb["driver"],
                    "phone": amb["phone"],
                    "type": amb["type"],
                    "eta": case.get("eta"),
                    "lat": amb.get("lat"),
                    "lng": amb.get("lng"),
                    "location": amb.get("location"),
                },
                "hospital": case.get("hospital"),
                "phase": delivery_status,
            }

    # Check if case is in queue
    from backend.ambulance import get_queue
    queue = get_queue()
    for q in queue:
        if q.get("case_id") == case_id:
            return {
                "case_id": case_id,
                "status": "queued",
                "queue_position": queue.index(q) + 1,
                "message": f"Your case is #{queue.index(q) + 1} in queue. An ambulance will be assigned soon.",
            }

    return {"case_id": case_id, "status": "pending", "message": "Your call is being processed."}


async def patient_picked_up(case_id: str) -> dict:
    """Mark patient as picked up, notify hospital."""
    from backend.database import get_case_by_id, update_delivery_status
    from backend.hospital import notify_hospital, get_hospital_list

    case = get_case_by_id(case_id)
    if not case:
        return {"success": False, "error": "Case not found"}

    amb_id = case.get("ambulance_id")
    if not amb_id:
        return {"success": False, "error": "No ambulance assigned"}

    # Update ambulance status
    from backend.ambulance import update_ambulance_status
    update_ambulance_status(amb_id, "patient_picked", case_id)

    # Update case status
    update_delivery_status(case_id, "picked_up")

    # Get hospital and notify
    hospital_id = case.get("hospital_id")
    hospital_name = case.get("hospital_name")
    if hospital_id:
        notify_hospital(
            hospital_id, case_id,
            case.get("caller_name", "Unknown"),
            1,  # ETA: 1 min to hospital after pickup
            case.get("description", ""),
            case.get("risk_level", "Unknown")
        )

    # Broadcast to all clients
    if _broadcast_fn:
        # General notification
        await _broadcast_fn({
            "type": "patient_picked_up",
            "data": {
                "case_id": case_id,
                "ambulance": amb_id,
                "hospital": hospital_name,
                "message": f"Patient picked up by {amb_id}. Heading to {hospital_name}."
            }
        })
        # Hospital-specific notification
        if hospital_id:
            await _broadcast_fn({
                "type": "hospital_alert",
                "data": {
                    "hospital_id": hospital_id,
                    "case_id": case_id,
                    "patient_name": case.get("caller_name", "Unknown"),
                    "condition": case.get("description", ""),
                    "risk_level": case.get("risk_level", "Unknown"),
                    "eta_minutes": case.get("ambulance_eta", 1),
                    "status": "patient_en_route",
                    "message": f"ALERT: Patient {case.get('caller_name')} is being brought in! Condition: {case.get('risk_level')}. ETA: {case.get('ambulance_eta', 1)} min. Prepare necessary equipment.",
                }
            })

    return {
        "success": True,
        "case_id": case_id,
        "message": "Patient picked up. Hospital has been notified.",
        "hospital_notified": hospital_name
    }


async def patient_delivered(case_id: str) -> dict:
    """Mark patient as delivered at hospital, release ambulance and bed."""
    from backend.database import get_case_by_id, update_delivery_status
    from backend.hospital import remove_incoming_patient
    from backend.ambulance import mark_ambulance_available, update_ambulance_status

    case = get_case_by_id(case_id)
    if not case:
        return {"success": False, "error": "Case not found"}

    amb_id = case.get("ambulance_id")
    hospital_id = case.get("hospital_id")

    # Update ambulance to available
    if amb_id:
        update_ambulance_status(amb_id, "delivered", case_id)
        mark_ambulance_available(amb_id)

    # Update case status
    update_delivery_status(case_id, "delivered")

    # Remove from hospital incoming list
    if hospital_id:
        remove_incoming_patient(hospital_id, case_id)

    # Release hospital bed if occupied
    if hospital_id:
        from backend.hospital import release_bed
        release_bed(hospital_id)

    # Broadcast to all clients
    if _broadcast_fn:
        await _broadcast_fn({
            "type": "patient_delivered",
            "data": {
                "case_id": case_id,
                "ambulance": amb_id,
                "hospital": case.get("hospital_name"),
                "message": f"Patient delivered to {case.get('hospital_name')}. Ambulance {amb_id} is now available."
            }
        })

    return {
        "success": True,
        "case_id": case_id,
        "message": "Patient delivered. Ambulance is now available for next dispatch.",
        "ambulance_available": True
    }
