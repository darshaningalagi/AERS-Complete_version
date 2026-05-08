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
from backend.ambulance import get_fleet_status, mark_ambulance_busy, mark_ambulance_available
from backend.hospital import get_hospital_list
from backend.decision import run_decision_engine, get_case_history, set_decision_broadcast
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
    lat:          Optional[float]= Field(14.4673)
    lng:          Optional[float]= Field(75.9238)
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

# ── System ─────────────────────────────────────────────────────────────
@app.get("/test", tags=["System"])
def health_check():
    return {"status":"online","message":"AERS API is working",
            "model_loaded":MODEL_LOADED,"version":"3.0.0","ws_clients":manager.count()}

@app.get("/status", tags=["System"])
def system_status():
    fleet = get_fleet_status()
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
def update_ambulance_status(req: AmbulanceStatusRequest):
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
    return {"cases": get_recent_cases(limit)}
