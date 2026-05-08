"""
AERS Simulation Engine — v3 (SQLite + WebSocket broadcast)
"""
import asyncio
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from simulator.scenarios import get_random_scenario
from backend.decision import run_decision_engine
from backend.database import save_sim_run

router = APIRouter(prefix="/sim", tags=["Simulator"])

SIM_STATE = {
    "running": False, "speed": 8,
    "total_generated": 0, "total_critical": 0,
    "total_urgent": 0,   "total_low": 0,
    "started_at": None,  "incidents": [], "next_in": 0,
}
_incident_counter = 0
_sim_task = None

# WebSocket broadcast hook — set by app.py after ws_manager is created
_broadcast_fn = None

def set_broadcast(fn):
    global _broadcast_fn
    _broadcast_fn = fn


@router.post("/start")
async def start_simulation(speed: int = 8):
    global _sim_task
    if SIM_STATE["running"]:
        return {"message": "Simulator already running"}
    SIM_STATE["running"] = True
    SIM_STATE["speed"] = max(3, min(speed, 60))
    SIM_STATE["started_at"] = datetime.now().strftime("%H:%M:%S")
    SIM_STATE["next_in"] = SIM_STATE["speed"]
    _sim_task = asyncio.create_task(_auto_generate())
    return {"message": f"Simulator started — incident every {SIM_STATE['speed']}s"}


@router.post("/stop")
async def stop_simulation():
    global _sim_task
    SIM_STATE["running"] = False
    if _sim_task:
        _sim_task.cancel()
        _sim_task = None
    return {"message": "Simulator stopped"}


@router.post("/speed")
async def set_speed(seconds: int = 8):
    SIM_STATE["speed"] = max(3, min(seconds, 60))
    return {"message": f"Speed set to {SIM_STATE['speed']}s per incident"}


@router.post("/fire")
async def fire_one(risk: str = None):
    return await _dispatch_incident(risk)


@router.get("/state")
async def get_state():
    return JSONResponse(SIM_STATE)


@router.get("/incidents")
async def get_incidents():
    return {"incidents": list(reversed(SIM_STATE["incidents"][-30:]))}


@router.post("/reset")
async def reset_simulation():
    global _sim_task, _incident_counter
    SIM_STATE["running"] = False
    if _sim_task:
        _sim_task.cancel()
        _sim_task = None
    _incident_counter = 0
    SIM_STATE.update({
        "running": False, "total_generated": 0,
        "total_critical": 0, "total_urgent": 0, "total_low": 0,
        "started_at": None, "incidents": [], "next_in": 0,
    })
    return {"message": "Simulation reset"}


async def _auto_generate():
    while SIM_STATE["running"]:
        speed = SIM_STATE["speed"]
        for remaining in range(speed, 0, -1):
            if not SIM_STATE["running"]:
                return
            SIM_STATE["next_in"] = remaining
            await asyncio.sleep(1)
        if SIM_STATE["running"]:
            await _dispatch_incident()


async def _dispatch_incident(risk_filter: str = None) -> dict:
    global _incident_counter
    _incident_counter += 1
    scenario = get_random_scenario(risk_filter)
    timestamp = datetime.now().strftime("%H:%M:%S")

    record = {
        "id": f"SIM-{_incident_counter:04d}",
        "timestamp": timestamp,
        "description": scenario["description"],
        "caller": scenario["caller_name"],
        "location": scenario["location_name"],
        "expected_risk": scenario["expected_risk"],
        "actual_risk": None, "confidence": None,
        "ambulance": None, "hospital": None,
        "case_id": None, "status": "sending", "error": None,
    }

    try:
        result = run_decision_engine(
            description=scenario["description"],
            incident_lat=scenario["lat"],
            incident_lng=scenario["lng"],
            caller_name=scenario["caller_name"],
            caller_phone=scenario["caller_phone"],
        )
        if result.get("success"):
            risk = result["triage"]["risk_level"]
            record.update({
                "actual_risk": risk,
                "confidence": result["triage"]["confidence"],
                "ambulance": result["dispatch"]["ambulance"]["id"] if result["dispatch"]["ambulance"] else "none",
                "hospital": result["hospital"]["name"] if result["hospital"] else "none",
                "case_id": result["case_id"],
                "status": "success",
            })
            SIM_STATE["total_generated"] += 1
            if risk == "Critical":  SIM_STATE["total_critical"] += 1
            elif risk == "Urgent":  SIM_STATE["total_urgent"] += 1
            else:                   SIM_STATE["total_low"] += 1
        else:
            record["status"] = "api_error"
            record["error"] = result.get("error", "Unknown")[:60]
    except Exception as e:
        record["status"] = "error"
        record["error"] = str(e)[:60]

    SIM_STATE["incidents"].append(record)
    if len(SIM_STATE["incidents"]) > 50:
        SIM_STATE["incidents"] = SIM_STATE["incidents"][-50:]

    # Save to database
    try:
        save_sim_run(record)
    except Exception:
        pass

    # Broadcast to WebSocket clients
    if _broadcast_fn and record["status"] == "success":
        try:
            await _broadcast_fn({"type": "new_case", "data": record})
        except Exception:
            pass

    return record
