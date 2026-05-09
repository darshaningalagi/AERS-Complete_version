"""
AERS Database Layer — SQLite
Replaces the in-memory CASE_LOG list.
Cases, ambulance events, and simulator runs all persist across restarts.
"""

import sqlite3
import os
import json
from datetime import datetime
from contextlib import contextmanager
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'aers.db')


# ─── Connection helper ────────────────────────────────────────────────
@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row   # rows as dicts
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── Schema creation ──────────────────────────────────────────────────
def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS cases (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id       TEXT NOT NULL UNIQUE,
            timestamp     TEXT NOT NULL,
            risk_level    TEXT NOT NULL,
            confidence    REAL,
            description   TEXT,
            caller_name   TEXT,
            caller_phone  TEXT,
            incident_lat  REAL,
            incident_lng  REAL,
            ambulance_id  TEXT,
            ambulance_eta INTEGER,
            hospital_id   TEXT,
            hospital_name TEXT,
            specialty     TEXT,
            dispatch_status TEXT,
            delivery_status TEXT DEFAULT 'ongoing',
            delivery_time TEXT,
            full_response TEXT
        );

        CREATE TABLE IF NOT EXISTS ambulance_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            amb_id      TEXT NOT NULL,
            event       TEXT NOT NULL,
            case_id     TEXT
        );

        CREATE TABLE IF NOT EXISTS sim_runs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT NOT NULL,
            sim_id        TEXT NOT NULL,
            expected_risk TEXT,
            actual_risk   TEXT,
            confidence    REAL,
            description   TEXT,
            ambulance_id  TEXT,
            hospital_name TEXT,
            status        TEXT,
            error         TEXT
        );
        """)
        # Add missing columns if they don't exist (migration)
        try:
            conn.execute("ALTER TABLE cases ADD COLUMN delivery_status TEXT DEFAULT 'ongoing'")
        except:
            pass
        try:
            conn.execute("ALTER TABLE cases ADD COLUMN delivery_time TEXT")
        except:
            pass
    print(f"[DB] Initialized at {DB_PATH}")


# ─── Case operations ──────────────────────────────────────────────────
def save_case(response: dict):
    """Persist a full /analyze response to the database."""
    triage   = response.get("triage", {})
    dispatch = response.get("dispatch", {})
    amb      = dispatch.get("ambulance") or {}
    hosp     = response.get("hospital") or {}
    incident = response.get("incident", {})
    caller   = response.get("caller", {})

    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO cases (
                case_id, timestamp, risk_level, confidence,
                description, caller_name, caller_phone,
                incident_lat, incident_lng,
                ambulance_id, ambulance_eta,
                hospital_id, hospital_name, specialty,
                dispatch_status, delivery_status, full_response
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            response.get("case_id"),
            response.get("timestamp"),
            triage.get("risk_level"),
            triage.get("confidence"),
            incident.get("description", "")[:200],
            caller.get("name"),
            caller.get("phone"),
            incident.get("lat"),
            incident.get("lng"),
            amb.get("id"),
            amb.get("eta_minutes"),
            hosp.get("id"),
            hosp.get("name"),
            hosp.get("specialty_matched"),
            dispatch.get("status"),
            "ongoing",
            json.dumps(response),
        ))


def get_recent_cases(limit: int = 50) -> list:
    """Return the most recent N cases as dicts."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cases ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_case_by_id(case_id: str) -> Optional[dict]:
    """Return a single case including full JSON response."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    if d.get("full_response"):
        d["full_response"] = json.loads(d["full_response"])
    return d


# ─── Analytics queries ────────────────────────────────────────────────
def get_analytics() -> dict:
    """Return aggregated stats for the analytics dashboard."""
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]

        by_risk = {
            row["risk_level"]: row["cnt"]
            for row in conn.execute(
                "SELECT risk_level, COUNT(*) as cnt FROM cases GROUP BY risk_level"
            ).fetchall()
        }

        avg_eta = conn.execute(
            "SELECT AVG(ambulance_eta) FROM cases WHERE ambulance_eta IS NOT NULL"
        ).fetchone()[0]

        avg_conf = conn.execute(
            "SELECT AVG(confidence) FROM cases WHERE confidence IS NOT NULL"
        ).fetchone()[0]

        top_hospitals = [
            dict(r) for r in conn.execute(
                """SELECT hospital_name, COUNT(*) as cnt
                   FROM cases WHERE hospital_name IS NOT NULL
                   GROUP BY hospital_name ORDER BY cnt DESC LIMIT 5"""
            ).fetchall()
        ]

        top_specialties = [
            dict(r) for r in conn.execute(
                """SELECT specialty, COUNT(*) as cnt
                   FROM cases WHERE specialty IS NOT NULL
                   GROUP BY specialty ORDER BY cnt DESC"""
            ).fetchall()
        ]

        # Cases per hour (last 24 hours)
        hourly = [
            dict(r) for r in conn.execute(
                """SELECT strftime('%H:00', timestamp) as hour, COUNT(*) as cnt
                   FROM cases
                   WHERE timestamp >= datetime('now','-24 hours')
                   GROUP BY hour ORDER BY hour"""
            ).fetchall()
        ]

        # Daily totals last 7 days (with risk breakdown for stacked chart)
        daily_raw = conn.execute(
            """SELECT strftime('%Y-%m-%d', timestamp) as day, risk_level, COUNT(*) as cnt
               FROM cases
               WHERE timestamp >= datetime('now','-7 days')
               GROUP BY day, risk_level
               ORDER BY day""").fetchall()

        # Group by day and pivot risk levels into separate columns
        by_day = {}
        for r in daily_raw:
            d = r["day"]
            if d not in by_day:
                by_day[d] = {"day": d, "Critical": 0, "Urgent": 0, "Low": 0}
            by_day[d][r["risk_level"]] = r["cnt"]
        daily = list(by_day.values())

        # Sim accuracy
        sim_total = conn.execute("SELECT COUNT(*) FROM sim_runs WHERE status='success'").fetchone()[0]
        sim_correct = conn.execute(
            "SELECT COUNT(*) FROM sim_runs WHERE expected_risk=actual_risk AND status='success'"
        ).fetchone()[0]

    return {
        "total_cases": total,
        "by_risk": by_risk,
        "critical": by_risk.get("Critical", 0),
        "urgent": by_risk.get("Urgent", 0),
        "low": by_risk.get("Low", 0),
        "avg_eta_minutes": round(avg_eta, 1) if avg_eta else None,
        "avg_confidence": round(avg_conf, 1) if avg_conf else None,
        "top_hospitals": top_hospitals,
        "top_specialties": top_specialties,
        "hourly_last_24h": hourly,
        "daily_last_7d": daily,
        "sim_total": sim_total,
        "sim_accuracy": round((sim_correct / sim_total * 100), 1) if sim_total > 0 else None,
    }


# ─── Ambulance event log ──────────────────────────────────────────────
def log_ambulance_event(amb_id: str, event: str, case_id: str = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ambulance_events (timestamp, amb_id, event, case_id) VALUES (?,?,?,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), amb_id, event, case_id)
        )


# ─── Simulator run log ────────────────────────────────────────────────
def save_sim_run(record: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO sim_runs
            (timestamp, sim_id, expected_risk, actual_risk, confidence,
             description, ambulance_id, hospital_name, status, error)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            record.get("id"),
            record.get("expected_risk"),
            record.get("actual_risk"),
            record.get("confidence"),
            record.get("description", "")[:200],
            record.get("ambulance"),
            record.get("hospital"),
            record.get("status"),
            record.get("error"),
        ))


# ─── Delivery status operations ────────────────────────────────────────
def update_delivery_status(case_id: str, status: str) -> bool:
    """Update delivery status for a case (ongoing/delivered)."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "delivered" else None
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cases SET delivery_status = ?, delivery_time = ? WHERE case_id = ?",
            (status, timestamp, case_id)
        )
        return cursor.rowcount > 0


def get_case_delivery_status(case_id: str) -> str:
    """Get delivery status for a case."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT delivery_status FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        return row["delivery_status"] if row else None
