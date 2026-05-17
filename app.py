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
    get_ambulance_by_id, update_ambulance_status, get_fleet_maintenance
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
    description:  str            = Field(..., min_length=3, max_length=500)
    lat:          Optional[float]= Field(default=14.4673, ge=-90, le=90)
    lng:          Optional[float]= Field(default=75.9238, ge=-180, le=180)
    caller_name:  Optional[str]  = Field(default="Anonymous", max_length=100)
    caller_phone: Optional[str]  = Field(default="Unknown", max_length=20)

    model_config = {
        "json_schema_extra": {
            "example": {
                "description": "severe chest pain with difficulty breathing",
                "lat": 14.4673,
                "lng": 75.9238,
                "caller_name": "John Doe",
                "caller_phone": "+91-9876543210"
            }
        }
    }

class TriageOnlyRequest(BaseModel):
    description: str = Field(..., min_length=3, max_length=500)

    model_config = {
        "json_schema_extra": {
            "example": {
                "description": "broken leg with visible bone"
            }
        }
    }

class AmbulanceStatusRequest(BaseModel):
    amb_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)

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


@app.get("/tracking")
def serve_tracking():
    """Serve live tracking map."""
    p = os.path.join(frontend_path, "tracking.html")
    return FileResponse(p) if os.path.exists(p) else {"msg": "Tracking page not found"}

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


@app.get("/ambulances/maintenance", tags=["Fleet"])
def list_ambulances_maintenance():
    """Get fleet maintenance status."""
    return {"fleet": get_fleet_maintenance()}


@app.get("/ambulance/{amb_id}/maintenance", tags=["Fleet"])
def get_ambulance_maintenance_detail(amb_id: str):
    """Get maintenance details for a specific ambulance."""
    from backend.ambulance import get_ambulance_maintenance
    maint = get_ambulance_maintenance(amb_id)
    if not maint:
        raise HTTPException(404, f"Ambulance {amb_id} not found")
    return maint


class MaintenanceUpdate(BaseModel):
    status: str = None
    fuel_pct: int = None
    notes: str = None


@app.put("/ambulance/{amb_id}/maintenance", tags=["Fleet"])
def update_ambulance_maintenance(amb_id: str, req: MaintenanceUpdate):
    """Update ambulance maintenance status."""
    from backend.ambulance import update_maintenance_status

    result = update_maintenance_status(amb_id, req.status, req.fuel_pct, req.notes)
    if not result:
        raise HTTPException(404, f"Ambulance {amb_id} not found")
    return {"message": f"Ambulance {amb_id} maintenance updated"}


@app.post("/ambulance/{amb_id}/maintenance/complete", tags=["Fleet"])
def complete_maintenance(amb_id: str):
    """Mark maintenance as completed."""
    from backend.ambulance import record_maintenance

    result = record_maintenance(amb_id)
    if not result:
        raise HTTPException(404, f"Ambulance {amb_id} not found")
    return {"message": f"Maintenance completed for {amb_id}"}

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


@app.get("/api/analytics/export", tags=["Analytics"])
def export_analytics_csv():
    """Export analytics data as CSV for reports."""
    import csv
    import io
    from fastapi.responses import StreamingResponse

    from backend.database import get_recent_cases

    # Get cases
    rows = get_recent_cases(1000)

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Case ID", "Timestamp", "Risk Level", "Confidence",
        "Description", "Ambulance", "Hospital", "Specialty", "Status"
    ])

    # Data rows
    for r in rows:
        writer.writerow([
            r.get("case_id", ""),
            r.get("timestamp", ""),
            r.get("risk_level", ""),
            r.get("confidence", ""),
            r.get("description", "")[:100],
            r.get("ambulance_id", ""),
            r.get("hospital_name", ""),
            r.get("specialty", ""),
            r.get("delivery_status", "ongoing"),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=aers_analytics.csv"}
    )

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
    description: str = Field(..., min_length=3, max_length=500)
    lat: Optional[float] = Field(default=14.4673, ge=-90, le=90)
    lng: Optional[float] = Field(default=75.9238, ge=-180, le=180)
    caller_name: Optional[str] = Field(default="Anonymous", max_length=100)
    caller_phone: Optional[str] = Field(default="Unknown", max_length=20)

    model_config = {
        "json_schema_extra": {
            "example": {
                "description": "severe chest pain",
                "lat": 14.4673,
                "lng": 75.9238,
                "caller_name": "Patient Name",
                "caller_phone": "+91-9876543210"
            }
        }
    }


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


@app.get("/patient/cases", tags=["Patient"])
def get_cases_by_phone(phone: str):
    """Get all cases for a phone number."""
    from backend.database import get_cases_by_phone as db_get_cases_by_phone
    cases = db_get_cases_by_phone(phone)
    if not cases:
        raise HTTPException(404, f"No cases found for phone {phone}")
    return {"phone": phone, "cases": cases, "count": len(cases)}


# ── Driver Interface ───────────────────────────────────────────────────
class DriverStatusRequest(BaseModel):
    amb_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    case_id: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "amb_id": "AMB-01",
                "status": "enroute",
                "case_id": "EM-12345678"
            }
        }
    }


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


# ── Route Details Endpoint ───────────────────────────────────────────────
@app.get("/tracking/routes", tags=["Tracking"])
def get_all_routes():
    """Get all active ambulance routes with details."""
    from backend.ambulance import get_all_ambulances_status
    from backend.hospital import get_hospital_list

    fleet = get_all_ambulances_status()
    hospitals = get_hospital_list()

    routes = []
    for amb in fleet:
        tracking = amb.get("tracking", {})
        if tracking.get("case_id") and tracking.get("patient_location_lat"):
            # Calculate distances
            from backend.ambulance import haversine

            patient_lat = tracking["patient_location_lat"]
            patient_lng = tracking["patient_location_lng"]
            amb_lat = amb["lat"]
            amb_lng = amb["lng"]

            if tracking.get("destination_hospital_lat") and tracking.get("destination_hospital_lng"):
                hosp_lat = tracking["destination_hospital_lat"]
                hosp_lng = tracking["destination_hospital_lng"]

                dist_to_patient = haversine(amb_lat, amb_lng, patient_lat, patient_lng)
                dist_to_hospital = haversine(patient_lat, patient_lng, hosp_lat, hosp_lng)

                routes.append({
                    "ambulance_id": amb["id"],
                    "case_id": tracking["case_id"],
                    "status": amb["status"],
                    "current_phase": amb.get("current_phase"),
                    "driver": amb["driver"],
                    "patient": {
                        "location": {"lat": patient_lat, "lng": patient_lng},
                        "description": tracking.get("patient_description"),
                    },
                    "destination_hospital": {
                        "id": tracking.get("destination_hospital_id"),
                        "name": tracking.get("destination_hospital_name"),
                        "location": {
                            "lat": tracking.get("destination_hospital_lat"),
                            "lng": tracking.get("destination_hospital_lng"),
                        },
                    },
                    "distances": {
                        "ambulance_to_patient_km": round(dist_to_patient, 2),
                        "patient_to_hospital_km": round(dist_to_hospital, 2),
                    },
                    "route_summary": f"Ambulance {amb['id']} en-route: {dist_to_patient:.1f} km to patient → {dist_to_hospital:.1f} km to hospital",
                })

    return {"active_routes": routes, "total_active": len(routes)}


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
    """Mark patient as delivered (bed gets occupied)."""
    result = await patient_delivered(case_id)
    if not result["success"]:
        raise HTTPException(500, result.get("error", "Error"))
    return result


@app.post("/case/{case_id}/discharged", tags=["Case"])
async def case_discharged(case_id: str):
    """Mark patient as discharged (bed becomes available)."""
    from backend.decision import patient_discharged
    result = await patient_discharged(case_id)
    if not result["success"]:
        raise HTTPException(500, result.get("error", "Error"))
    return result


class CasePriorityUpdate(BaseModel):
    priority: str


@app.patch("/case/{case_id}/priority", tags=["Case"])
def update_case_priority(case_id: str, req: CasePriorityUpdate):
    """Override case priority (admin only)."""
    from backend.database import update_case_priority as db_update_priority

    valid = ["Critical", "Urgent", "Low"]
    if req.priority not in valid:
        raise HTTPException(400, f"Priority must be one of: {valid}")

    result = db_update_priority(case_id, req.priority)
    if not result:
        raise HTTPException(404, f"Case {case_id} not found")

    return {"message": f"Case {case_id} priority updated to {req.priority}"}


# ═══════════════════════════════════════════════════════════════════════
# ADMIN PANEL
# ═══════════════════════════════════════════════════════════════════════
@app.get("/admin")
def serve_admin():
    """Serve admin panel."""
    p = os.path.join(frontend_path, "admin.html")
    return FileResponse(p) if os.path.exists(p) else {"msg": "Admin panel not found"}


# ─── Admin: Hospital Management ─────────────────────────────────────────
class NewHospital(BaseModel):
    id: Optional[str] = None
    name: str
    lat: float
    lng: float
    specialties: list[str]
    capacity_pct: int = 50
    icu_beds: int = 10
    contact: str
    address: str


@app.post("/admin/hospitals", tags=["Admin"])
def admin_add_hospital(req: NewHospital):
    """Add a new hospital (admin)."""
    from backend.hospital import add_hospital
    hospital = add_hospital(req.model_dump(exclude_none=True))
    return {"message": "Hospital added", "hospital": hospital}


@app.put("/admin/hospitals/{hospital_id}", tags=["Admin"])
def admin_update_hospital(hospital_id: str, req: NewHospital):
    """Update hospital details (admin)."""
    from backend.hospital import update_hospital_details
    hospital = update_hospital_details(hospital_id, req.model_dump(exclude_none=True))
    if not hospital:
        raise HTTPException(404, f"Hospital {hospital_id} not found")
    return {"message": "Hospital updated", "hospital": hospital}


@app.delete("/admin/hospitals/{hospital_id}", tags=["Admin"])
def admin_delete_hospital(hospital_id: str):
    """Delete a hospital (admin)."""
    from backend.hospital import delete_hospital
    result = delete_hospital(hospital_id)
    if not result:
        raise HTTPException(404, f"Hospital {hospital_id} not found")
    return {"message": f"Hospital {hospital_id} deleted"}


# ─── Admin: Ambulance Management ────────────────────────────────────────
class NewAmbulance(BaseModel):
    id: Optional[str] = None
    driver: str
    phone: str
    type: str = "BLS"
    location: str = "HQ"
    lat: float = 14.4700
    lng: float = 75.9300
    equipment: Optional[list[str]] = None
    maintenance_status: str = "good"
    fuel_pct: int = 80
    notes: str = ""


@app.post("/admin/ambulances", tags=["Admin"])
def admin_add_ambulance(req: NewAmbulance):
    """Add a new ambulance (admin)."""
    from backend.ambulance import add_ambulance
    ambulance = add_ambulance(req.model_dump(exclude_none=True))
    return {"message": "Ambulance added", "ambulance": ambulance}


@app.put("/admin/ambulances/{amb_id}", tags=["Admin"])
def admin_update_ambulance(amb_id: str, req: NewAmbulance):
    """Update ambulance details (admin)."""
    from backend.ambulance import update_ambulance_details
    ambulance = update_ambulance_details(amb_id, req.model_dump(exclude_none=True))
    if not ambulance:
        raise HTTPException(404, f"Ambulance {amb_id} not found")
    return {"message": "Ambulance updated", "ambulance": ambulance}


@app.delete("/admin/ambulances/{amb_id}", tags=["Admin"])
def admin_delete_ambulance(amb_id: str):
    """Delete an ambulance (admin)."""
    from backend.ambulance import delete_ambulance
    result = delete_ambulance(amb_id)
    if not result:
        raise HTTPException(404, f"Ambulance {amb_id} not found")
    return {"message": f"Ambulance {amb_id} deleted"}


# ─── Admin: System Overview ─────────────────────────────────────────────
@app.get("/admin/overview", tags=["Admin"])
def admin_overview():
    """Get system overview for admin dashboard."""
    from backend.ambulance import get_fleet_status, get_fleet_maintenance
    from backend.hospital import get_hospital_list, get_all_hospitals_status
    from backend.database import get_analytics
    from backend.decision import get_case_history

    fleet = get_fleet_status()
    maintenance = get_fleet_maintenance()
    hospitals = get_hospital_list()
    hospital_status = get_all_hospitals_status()
    analytics = get_analytics()
    cases = get_case_history()

    return {
        "fleet": {
            "total": len(fleet),
            "available": sum(1 for a in fleet if a["status"] == "available"),
            "dispatched": sum(1 for a in fleet if a["status"] == "dispatched"),
            "maintenance": sum(1 for a in fleet if a["maintenance_status"] != "good"),
        },
        "hospitals": {
            "total": len(hospitals),
            "total_icu_beds": sum(h.get("icu_beds", 0) for h in hospital_status),
            "avg_capacity": sum(h.get("capacity_pct", 0) for h in hospital_status) / max(len(hospital_status), 1),
        },
        "cases": {
            "today": len(cases),
            "critical": sum(1 for c in cases if c.get("risk") == "Critical"),
            "urgent": sum(1 for c in cases if c.get("risk") == "Urgent"),
            "low": sum(1 for c in cases if c.get("risk") == "Low"),
        },
        "analytics": analytics,
        "maintenance_alerts": [m for m in maintenance if m.get("maintenance_status") != "good"],
    }
