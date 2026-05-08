"""
AERS — Manual Test Suite
Run: python tests.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from backend.predictor import predict_risk
from backend.ambulance import get_nearest_ambulance, mark_ambulance_busy, mark_ambulance_available, get_fleet_status
from backend.hospital import get_best_hospital, get_hospital_list
from backend.decision import run_decision_engine

INCIDENT_LAT, INCIDENT_LNG = 14.4673, 75.9238

def section(title):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print('='*55)

def test(label, value, expected_key=None):
    status = "PASS" if value else "FAIL"
    if expected_key and isinstance(value, dict):
        status = "PASS" if expected_key in value else "FAIL"
    print(f"  [{status}] {label}: {value if not isinstance(value, dict) else '(dict)'}")
    return status == "PASS"

# ── MODULE 3: Triage prediction ──────────────────────────────────────
section("MODULE 3 — ML Triage Prediction")

cases = [
    ("cardiac arrest not breathing no pulse", "Critical"),
    ("broken leg bone visible moderate pain", "Urgent"),
    ("mild headache no fever", "Low"),
    ("", None),  # edge case: empty
    ("asdfghjkl random gibberish", None),  # edge case: random text
    ("chest pain sweating left arm pain difficulty breathing severe", "Critical"),
    ("child fever seizure unresponsive high temperature", "Critical"),
    ("dog bite deep wound bleeding stitches needed", "Urgent"),
    ("minor bruise knee fall walking okay", "Low"),
    ("multiple trauma accident unconscious bleeding head", "Critical"),
]

print(f"\n  {'Input':<45} {'Expected':<12} {'Got':<12} {'Conf'}")
print(f"  {'-'*45} {'-'*12} {'-'*12} {'-'*6}")
for desc, expected in cases:
    result = predict_risk(desc)
    if not result["success"]:
        got = f"ERROR: {result['error'][:30]}"
        conf = "—"
    else:
        got = result["risk_level"]
        conf = f"{result['confidence']}%"
    match = "✓" if got == expected else ("✓" if expected is None else "✗")
    short = desc[:43] if desc else "(empty)"
    print(f"  {match} {short:<45} {str(expected):<12} {got:<12} {conf}")

# ── MODULE 5: Ambulance dispatch ──────────────────────────────────────
section("MODULE 5 — Ambulance Dispatch")

print("\n  Fleet status before dispatch:")
for a in get_fleet_status():
    print(f"    {a['id']} — {a['status']} — {a['location']}")

amb = get_nearest_ambulance(INCIDENT_LAT, INCIDENT_LNG, "Critical")
if amb:
    print(f"\n  Selected for Critical: {amb['id']} ({amb['type']}) — {amb['distance_km']}km — ETA {amb['eta_minutes']}min")
    mark_ambulance_busy(amb['id'])
    print(f"  Marked {amb['id']} as busy")

amb2 = get_nearest_ambulance(INCIDENT_LAT, INCIDENT_LNG, "Low")
if amb2:
    print(f"  Selected for Low: {amb2['id']} ({amb2['type']}) — {amb2['distance_km']}km")

print("\n  Fleet status after dispatch:")
for a in get_fleet_status():
    print(f"    {a['id']} — {a['status']}")

mark_ambulance_available(amb['id'])
print(f"\n  Reset {amb['id']} to available ✓")

# ── MODULE 6: Hospital selection ──────────────────────────────────────
section("MODULE 6 — Hospital Selection Algorithm")

test_inputs = [
    ("cardiac arrest chest pain heart", "Critical"),
    ("road accident head trauma unconscious", "Critical"),
    ("child fever seizure pediatric", "Urgent"),
    ("burn fire 30 percent body", "Critical"),
    ("broken leg fracture ortho", "Urgent"),
]

for desc, risk in test_inputs:
    h = get_best_hospital(INCIDENT_LAT, INCIDENT_LNG, desc, risk, risk)
    if h:
        print(f"  [{risk:<8}] {desc[:40]:<42} → {h['name']} (spec: {h['specialty_matched']}, score: {h['score']})")

# ── MODULE 7: Full decision engine ────────────────────────────────────
section("MODULE 7 — Full Decision Engine (End-to-End)")

result = run_decision_engine(
    description="65 year old male, chest pain, sweating, left arm pain, history of hypertension",
    incident_lat=INCIDENT_LAT,
    incident_lng=INCIDENT_LNG,
    caller_name="Test User",
    caller_phone="+91-9999999999"
)

if result["success"]:
    print(f"\n  Case ID     : {result['case_id']}")
    print(f"  Timestamp   : {result['timestamp']}")
    print(f"  Risk Level  : {result['triage']['risk_level']} ({result['triage']['confidence']}%)")
    print(f"  Action      : {result['triage']['recommended_action']}")
    if result['dispatch']['ambulance']:
        a = result['dispatch']['ambulance']
        print(f"  Ambulance   : {a['id']} — ETA {a['eta_minutes']}min — Driver: {a['driver']}")
    if result['hospital']:
        h = result['hospital']
        print(f"  Hospital    : {h['name']} — {h['specialty_matched']} — {h['icu_beds']} ICU")
    print(f"\n  Timeline steps:")
    for step in result['timeline']:
        status_icon = "✓" if step['status']=='done' else "→" if step['status']=='active' else "·"
        print(f"    {status_icon} {step['step']}")
else:
    print(f"  FAILED: {result['error']}")

# ── MODULE 9: Edge cases ──────────────────────────────────────────────
section("MODULE 9 — Edge Cases")

edge_cases = [
    ("Empty string", ""),
    ("Only spaces", "   "),
    ("Single word", "pain"),
    ("Numbers only", "123 456 789"),
    ("Mixed language", "patient ko bahut chest pain ho raha hai severe"),
    ("Very long input", "patient has severe chest pain radiating to the left arm with significant diaphoresis and dyspnea at rest for the past 30 minutes accompanied by nausea and dizziness" * 2),
    ("Multiple symptoms", "head injury broken arm internal bleeding unconscious road accident multiple trauma"),
]

for label, txt in edge_cases:
    result = predict_risk(txt)
    if result["success"]:
        print(f"  {label:<25} → {result['risk_level']:<10} ({result['confidence']}%)")
    else:
        print(f"  {label:<25} → ERROR: {result['error']}")

print("\n" + "="*55)
print("  All tests complete!")
print("="*55 + "\n")
