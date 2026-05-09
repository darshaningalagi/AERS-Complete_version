"""
AERS — AI-Based Enhanced Emergency Response System
FastAPI Backend  |  v3.0
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
import os

from backend.predictor import predict_risk, MODEL_LOADED
from backend.ambulance import (
    get_fleet_status, mark_ambulance_busy, mark_ambulance_available,
    get_ambulance_by_id, update_ambulance_status
)
from backend.hospital import (
    get_hospital_list, get_hospital_status, get_incoming_patients,
    get_all_hospitals_status
)
from backend.decision import (
    run_decision_engine, get_case_history, set_decision_broadcast,
    create_emergency_call, get_case_status, get_patient_notification,
    patient_picked_up, patient_delivered
)
from backend.ambulance import get_queue, queue_size, remove_from_queue
from backend.database import init_db, get_analytics, get_case_by_id, get_recent_cases
from backend.ws_manager import manager
from simulator.engine import router as sim_router, set_broadcast

init_db()
set_broadcast(manager.broadcast)
set_decision_broadcast(manager.broadcast)

app = FastAPI(title="AERS", description="AI Emergency Response System", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(sim_router)

frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

class EmergencyRequest(BaseModel):
    description:  str            = Field(..., min_length=1)
    lat:          Optional[float]= Field(14.4673, ge=-90, le=90)
    lng:          Optional[float]= Field(75.9238, ge=-180, le=180)
    caller_name:  Optional[str]  = Field("Anonymous")
    caller_phone: Optional[str]  = Field("Unknown")

class TriageOnlyRequest(BaseModel):
    description: str = Field(..., min_length=1)

class AmbulanceStatusRequest(BaseModel):
    amb_id: str
    status: str

# ── WebSocket ──────────────────────────────────────────────────────────
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)

# ── Pages ──────────────────────────────────────────────────────────────
@app.get("/")
def serve_frontend():
    p = os.path.join(frontend_path, "index.html")
    return FileResponse(p) if os.path.exists(p) else {"msg": "Frontend not found"}

@app.get("/simulator")
def serve_simulator():
    p = os.path.join(os.path.dirname(__file__), "simulator", "dashboard.html")
    return FileResponse(p) if os.path.exists(p) else {"msg": "Simulator not found"}

@app.get("/analytics")
def serve_analytics():
    p = os.path.join(frontend_path, "analytics.html")
    return FileResponse(p) if os.path.exists(p) else {"msg": "Analytics not found"}

@app.get("/patient")
def serve_patient():
    """Serve patient portal."""
    p = os.path.join(frontend_path, "patient.html")
    return FileResponse(p) if os.path.exists(p) else {"msg": "Patient portal not found"}


@app.get("/hospital")
def serve_hospital():
    """Serve hospital admin panel."""
    p = os.path.join(frontend_path, "hospital.html")
    return FileResponse(p) if os.path.exists(p) else {"msg": "Hospital panel not found"}


@app.get("/driver")
def serve_driver():
    """Serve ambulance driver dashboard."""
    p = os.path.join(frontend_path, "driver.html")
    return FileResponse(p) if os.path.exists(p) else {"msg": "Driver dashboard not found"}

# ── System ─────────────────────────────────────────────────────────────
@app.get("/test", tags=["System"])
def health_check():
    return {"status":"online","message":"AERS API is working",
            "model_loaded":MODEL_LOADED,"version":"3.0.0","ws_clients":manager.count()}

@app.get("/status", tags=["System"])
def system_status():
    from backend.ambulance import get_all_ambulances_status
    fleet = get_all_ambulances_status()  # Includes tracking info
    return {
        "model_loaded": MODEL_LOADED,
        "ambulances_total": len(fleet),
        "ambulances_available": sum(1 for a in fleet if a["status"]=="available"),
        "hospitals_total": len(get_hospital_list()),
        "cases_today": len(get_case_history()),
        "ws_clients": manager.count(),
        "fleet": fleet,
        "hospitals": get_hospital_list(),
    }

@app.post("/triage", tags=["Triage"])
def triage_only(req: TriageOnlyRequest):
    if not req.description.strip():
        raise HTTPException(400, "Empty description")
    r = predict_risk(req.description)
    if not r["success"]: raise HTTPException(500, r["error"])
    return r

@app.post("/analyze", tags=["Emergency"])
async def analyze_emergency(req: EmergencyRequest):
    if not req.description.strip():
        raise HTTPException(400, "Empty description")
    result = run_decision_engine(
        description=req.description, incident_lat=req.lat, incident_lng=req.lng,
        caller_name=req.caller_name, caller_phone=req.caller_phone,
    )
    if not result["success"]: raise HTTPException(500, result.get("error","Error"))
    await manager.broadcast({"type":"new_case","data":{
        "case_id":result["case_id"],"timestamp":result["timestamp"],
        "risk":result["triage"]["risk_level"],"confidence":result["triage"]["confidence"],
        "ambulance":result["dispatch"]["ambulance"]["id"] if result["dispatch"]["ambulance"] else None,
        "hospital":result["hospital"]["name"] if result["hospital"] else None,
        "description":req.description[:80],
    }})
    return result

@app.get("/ambulances", tags=["Fleet"])
def list_ambulances():
    return {"ambulances": get_fleet_status()}

@app.post("/ambulances/status", tags=["Fleet"])
def set_ambulance_status(req: AmbulanceStatusRequest):
    if req.status=="available": ok = mark_ambulance_available(req.amb_id)
    elif req.status=="busy":    ok = mark_ambulance_busy(req.amb_id)
    else: raise HTTPException(400,"Status must be available or busy")
    if not ok: raise HTTPException(404,f"{req.amb_id} not found")
    return {"message":f"{req.amb_id} updated to {req.status}"}

@app.get("/hospitals", tags=["Hospitals"])
def list_hospitals():
    return {"hospitals": get_hospital_list()}

@app.get("/cases", tags=["Cases"])
def case_history():
    return {"cases": get_case_history()}

@app.get("/cases/{case_id}", tags=["Cases"])
def get_case(case_id: str):
    c = get_case_by_id(case_id)
    if not c: raise HTTPException(404,f"Case {case_id} not found")
    return c

@app.get("/queue", tags=["Queue"])
def get_waiting_queue():
    """Return the current priority waiting queue."""
    return {
        "queue": get_queue(),
        "size":  queue_size(),
    }

@app.delete("/queue/{case_id}", tags=["Queue"])
def cancel_from_queue(case_id: str):
    """Remove a case from the waiting queue (admin)."""
    removed = remove_from_queue(case_id)
    if not removed:
        raise HTTPException(404, f"Case {case_id} not in queue")
    return {"message": f"{case_id} removed from queue"}

@app.get("/api/analytics", tags=["Analytics"])
def analytics():
    return get_analytics()

@app.get("/api/cases/recent", tags=["Analytics"])
def recent_cases(limit: int = 100):
    from backend.database import get_recent_cases
    rows = get_recent_cases(limit)
    # Map to include patient_status (convert database values to display values)
    def map_patient_status(status):
        if status == "delivered":
            return "patient arrived at hospital"
        elif status == "picked_up":
            return "patient picked up"
        return "ongoing"

    cases = [
        {
            "case_id": r["case_id"],
            "timestamp": r["timestamp"],
            "risk_level": r["risk_level"],
            "confidence": r["confidence"],
            "description": r["description"],
            "ambulance_id": r["ambulance_id"],
            "hospital_name": r["hospital_name"],
            "specialty": r["specialty"],
            "patient_status": map_patient_status(r.get("delivery_status", "ongoing")),
        }
        for r in rows
    ]
    return {"cases": cases}


# ── Patient Interface ──────────────────────────────────────────────────
class PatientCallRequest(BaseModel):
    description: str = Field(..., min_length=1)
    lat: Optional[float] = Field(14.4673, ge=-90, le=90)
    lng: Optional[float] = Field(75.9238, ge=-180, le=180)
    caller_name: Optional[str] = Field("Anonymous")
    caller_phone: Optional[str] = Field("Unknown")


@app.post("/patient/call", tags=["Patient"])
async def patient_make_call(req: PatientCallRequest):
    """Patient makes emergency call."""
    if not req.description.strip():
        raise HTTPException(400, "Description required")
    result = create_emergency_call(
        description=req.description,
        incident_lat=req.lat,
        incident_lng=req.lng,
        caller_name=req.caller_name,
        caller_phone=req.caller_phone,
    )
    if not result["success"]:
        raise HTTPException(500, result.get("error", "Error creating call"))

    # Broadcast new case
    await manager.broadcast({"type": "new_case", "data": {
        "case_id": result["case_id"],
        "timestamp": result["timestamp"],
        "risk": result["triage"]["risk_level"],
        "confidence": result["triage"]["confidence"],
        "ambulance": result["dispatch"]["ambulance"]["id"] if result["dispatch"]["ambulance"] else None,
        "hospital": result["hospital"]["name"] if result["hospital"] else None,
    }})

    return result


@app.get("/patient/case/{case_id}", tags=["Patient"])
def patient_get_case(case_id: str):
    """Patient checks case status."""
    case = get_case_status(case_id)
    if not case:
        raise HTTPException(404, f"Case {case_id} not found")
    return case


@app.get("/patient/notification/{case_id}", tags=["Patient"])
def patient_get_notification(case_id: str):
    """Patient gets notification details."""
    notification = get_patient_notification(case_id)
    if not notification:
        raise HTTPException(404, f"Case {case_id} not found")
    return notification


# ── Driver Interface ───────────────────────────────────────────────────
class DriverStatusRequest(BaseModel):
    amb_id: str
    status: str
    case_id: Optional[str] = None


@app.post("/driver/status", tags=["Driver"])
async def driver_update_status(req: DriverStatusRequest):
    """Driver updates ambulance status."""
    valid_statuses = ["dispatched", "enroute", "arrived", "patient_picked", "hospital_enroute", "delivered"]
    if req.status not in valid_statuses:
        raise HTTPException(400, f"Invalid status. Must be one of: {valid_statuses}")

    from backend.ambulance import update_ambulance_status
    ok = update_ambulance_status(req.amb_id, req.status, req.case_id)
    if not ok:
        raise HTTPException(404, f"Ambulance {req.amb_id} not found")

    await manager.broadcast({"type": "ambulance_status_update", "data": {
        "ambulance": req.amb_id,
        "status": req.status,
        "case_id": req.case_id,
    }})

    return {"message": f"Status updated to {req.status}", "ambulance": req.amb_id}


# ── Hospital Interface ──────────────────────────────────────────────────
@app.get("/hospital/dashboard/{hospital_id}", tags=["Hospital"])
def hospital_dashboard(hospital_id: str):
    """Hospital sees incoming patients."""
    status = get_hospital_status(hospital_id)
    if not status:
        raise HTTPException(404, f"Hospital {hospital_id} not found")
    incoming = get_incoming_patients(hospital_id)
    return {
        "hospital": status,
        "incoming_patients": incoming,
    }


@app.get("/hospitals/status", tags=["Hospitals"])
def hospitals_status():
    """Get status of all hospitals."""
    return {"hospitals": get_all_hospitals_status()}


# ── Hospital Bed Management (CRUD) ───────────────────────────────────────
class HospitalBedUpdate(BaseModel):
    icu_beds: Optional[int] = None
    capacity_pct: Optional[int] = None


@app.put("/hospital/{hospital_id}/beds", tags=["Hospitals"])
def update_hospital_beds(hospital_id: str, req: HospitalBedUpdate):
    """Update hospital ICU beds or capacity."""
    from backend.hospital import update_hospital_info
    result = update_hospital_info(hospital_id, req.icu_beds, req.capacity_pct)
    if not result:
        raise HTTPException(404, f"Hospital {hospital_id} not found")
    return {"message": "Hospital updated", "hospital_id": hospital_id}


@app.post("/hospital/{hospital_id}/beds/add", tags=["Hospitals"])
def add_hospital_beds(hospital_id: str, beds: int = 1):
    """Add ICU beds to hospital."""
    from backend.hospital import add_icu_beds
    result = add_icu_beds(hospital_id, beds)
    if not result:
        raise HTTPException(404, f"Hospital {hospital_id} not found")
    return {"message": f"Added {beds} ICU bed(s)", "hospital_id": hospital_id}


@app.post("/hospital/{hospital_id}/beds/remove", tags=["Hospitals"])
def remove_hospital_beds(hospital_id: str, beds: int = 1):
    """Remove ICU beds from hospital."""
    from backend.hospital import remove_icu_beds
    result = remove_icu_beds(hospital_id, beds)
    if not result:
        raise HTTPException(404, f"Hospital {hospital_id} not found")
    return {"message": f"Removed {beds} ICU bed(s)", "hospital_id": hospital_id}


# ── Tracking Endpoints ─────────────────────────────────────────────────
@app.get("/tracking/ambulances", tags=["Tracking"])
def get_ambulance_tracking():
    """Get all ambulances with tracking info - shows which hospital each is going to."""
    from backend.ambulance import get_all_ambulances_status
    return {"ambulances": get_all_ambulances_status()}


@app.get("/tracking/ambulance/{amb_id}", tags=["Tracking"])
def get_ambulance_tracking_detail(amb_id: str):
    """Get detailed tracking for a specific ambulance."""
    from backend.ambulance import get_ambulance_by_id
    amb = get_ambulance_by_id(amb_id)
    if not amb:
        raise HTTPException(404, f"Ambulance {amb_id} not found")

    # Build tracking info
    tracking_info = {
        "ambulance_id": amb["id"],
        "driver": amb["driver"],
        "status": amb["status"],
        "current_phase": amb.get("current_phase", "available"),
        "case_id": amb.get("case_id"),
        "patient": {
            "description": amb.get("patient_description"),
            "location_lat": amb.get("patient_location_lat"),
            "location_lng": amb.get("patient_location_lng"),
        },
        "destination_hospital": {
            "id": amb.get("destination_hospital_id"),
            "name": amb.get("destination_hospital_name"),
            "lat": amb.get("destination_hospital_lat"),
            "lng": amb.get("destination_hospital_lng"),
        },
        "is_tracking_active": amb.get("case_id") is not None,
    }

    # Verify if going to correct hospital (if tracking is active)
    if tracking_info["is_tracking_active"]:
        tracking_info["verification"] = {
            "status": "active",
            "message": f"Ambulance {amb_id} is heading to {amb.get('destination_hospital_name')}",
        }
    else:
        tracking_info["verification"] = {
            "status": "idle",
            "message": "No active case",
        }

    return tracking_info


# ── Case Status Updates ─────────────────────────────────────────────────
@app.post("/case/{case_id}/picked-up", tags=["Case"])
async def case_picked_up(case_id: str):
    """Mark patient as picked up."""
    result = await patient_picked_up(case_id)
    if not result["success"]:
        raise HTTPException(500, result.get("error", "Error"))
    return result


@app.post("/case/{case_id}/delivered", tags=["Case"])
async def case_delivered(case_id: str):
    """Mark patient as delivered."""
    result = await patient_delivered(case_id)
    if not result["success"]:
        raise HTTPException(500, result.get("error", "Error"))
    return result
