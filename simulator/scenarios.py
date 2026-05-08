"""
Fake incident scenario bank for AERS Simulator.
Each scenario has: description, caller, phone, lat/lng offset, expected_risk
"""
import random

# Haveri, Karnataka base coordinates
BASE_LAT = 14.4673
BASE_LNG = 75.9238

SCENARIOS = [
    # ── CRITICAL ─────────────────────────────────────────────────────
    {
        "description": "65 year old male, severe crushing chest pain, radiating to left arm, sweating profusely, cannot breathe properly",
        "caller": "Priya Sharma", "phone": "9845001234",
        "lat_off": 0.008, "lng_off": 0.012, "expected": "Critical",
        "location_name": "MG Road junction",
    },
    {
        "description": "Unconscious man on road, motorcycle accident, heavy bleeding from head, no response to voice",
        "caller": "Ramesh Nayak", "phone": "9741002345",
        "lat_off": -0.012, "lng_off": 0.018, "expected": "Critical",
        "location_name": "NH-48 bypass",
    },
    {
        "description": "Child 4 years old fell into open water tank, pulled out not breathing, lips turning blue",
        "caller": "Sunita Patil", "phone": "9632003456",
        "lat_off": 0.005, "lng_off": -0.009, "expected": "Critical",
        "location_name": "Shivaji Nagar",
    },
    {
        "description": "Cardiac arrest, person collapsed in market, bystanders doing CPR, needs defibrillator urgently",
        "caller": "Arjun Kulkarni", "phone": "9513004567",
        "lat_off": 0.015, "lng_off": 0.007, "expected": "Critical",
        "location_name": "Main Bazaar",
    },
    {
        "description": "Stroke suspected, sudden slurred speech, facial drooping on left side, arm weakness, severe headache",
        "caller": "Meena Desai", "phone": "9404005678",
        "lat_off": -0.006, "lng_off": -0.014, "expected": "Critical",
        "location_name": "Bank Colony",
    },
    {
        "description": "Severe allergic reaction after bee sting, throat swelling rapidly, cannot breathe, turning pale",
        "caller": "Vikram Rao", "phone": "9295006789",
        "lat_off": 0.022, "lng_off": 0.003, "expected": "Critical",
        "location_name": "Agriculture fields near Haveri",
    },
    {
        "description": "Fire accident, worker trapped, severe burns on chest and arms, 30 percent body affected, screaming in pain",
        "caller": "Suresh Hegde", "phone": "9186007890",
        "lat_off": 0.018, "lng_off": -0.020, "expected": "Critical",
        "location_name": "Industrial area",
    },
    {
        "description": "Pregnant woman, seizures, blood pressure very high, 8 months pregnant, eclampsia suspected",
        "caller": "Dr. Anita Joshi", "phone": "9077008901",
        "lat_off": -0.009, "lng_off": 0.016, "expected": "Critical",
        "location_name": "Residential colony",
    },
    {
        "description": "Overdose, young male found unconscious, empty medicine strip nearby, breathing very slow and shallow",
        "caller": "Anonymous", "phone": "Unknown",
        "lat_off": 0.001, "lng_off": -0.003, "expected": "Critical",
        "location_name": "Near railway station",
    },
    {
        "description": "Multiple vehicle collision, three people injured, one ejected from vehicle, unconscious and not moving",
        "caller": "Traffic Police", "phone": "9800009012",
        "lat_off": -0.025, "lng_off": 0.011, "expected": "Critical",
        "location_name": "Savanur crossroads",
    },
    # ── URGENT ───────────────────────────────────────────────────────
    {
        "description": "Deep cut on forearm from glass, moderate to heavy bleeding, needs stitches, patient conscious",
        "caller": "Rakesh Kumar", "phone": "9721010123",
        "lat_off": 0.004, "lng_off": 0.008, "expected": "Urgent",
        "location_name": "Glass factory",
    },
    {
        "description": "Elderly woman, 70 years, fell down stairs, severe hip pain, cannot stand, possible fracture",
        "caller": "Kavitha Rao", "phone": "9612011234",
        "lat_off": -0.011, "lng_off": -0.006, "expected": "Urgent",
        "location_name": "Old town area",
    },
    {
        "description": "Child 8 years, high fever 103 F, history of febrile seizures, parents very worried, one seizure already",
        "caller": "Naveen Patil", "phone": "9503012345",
        "lat_off": 0.013, "lng_off": 0.019, "expected": "Urgent",
        "location_name": "Vijayanagar layout",
    },
    {
        "description": "Dog bite on hand, very deep wound, bleeding, the dog was stray and possibly rabid",
        "caller": "Shobha Iyer", "phone": "9394013456",
        "lat_off": -0.007, "lng_off": 0.014, "expected": "Urgent",
        "location_name": "Near primary school",
    },
    {
        "description": "Moderate asthma attack, patient using inhaler but not getting relief, struggling to breathe",
        "caller": "Harish Gowda", "phone": "9285014567",
        "lat_off": 0.016, "lng_off": -0.008, "expected": "Urgent",
        "location_name": "Apartment complex",
    },
    {
        "description": "Broken collarbone, fall from bicycle, severe pain, arm cannot be moved, needs X-ray and splint",
        "caller": "Anjali Singh", "phone": "9176015678",
        "lat_off": -0.014, "lng_off": -0.019, "expected": "Urgent",
        "location_name": "Sports ground",
    },
    {
        "description": "Kitchen burn, cooking oil spilled, moderate burns on hand and forearm, patient in severe pain",
        "caller": "Rekha Naidu", "phone": "9067016789",
        "lat_off": 0.006, "lng_off": 0.021, "expected": "Urgent",
        "location_name": "Residential house",
    },
    {
        "description": "Severe dehydration, infant 18 months, vomiting and diarrhea for 2 days, sunken eyes, very weak",
        "caller": "Young Father", "phone": "9958017890",
        "lat_off": -0.003, "lng_off": 0.005, "expected": "Urgent",
        "location_name": "Government quarters",
    },
    {
        "description": "Industrial accident, hand caught in machinery, crush injury, bleeding moderate, extreme pain",
        "caller": "Factory Supervisor", "phone": "9849018901",
        "lat_off": 0.020, "lng_off": -0.015, "expected": "Urgent",
        "location_name": "Textile mill",
    },
    {
        "description": "Suspected appendicitis, severe pain right lower abdomen, fever 101, nausea and vomiting",
        "caller": "Geeta Murthy", "phone": "9740019012",
        "lat_off": -0.017, "lng_off": 0.009, "expected": "Urgent",
        "location_name": "Teachers colony",
    },
    # ── LOW ──────────────────────────────────────────────────────────
    {
        "description": "Minor sprained ankle from walking on uneven road, swelling mild, can walk slowly with support",
        "caller": "Mahesh Shetty", "phone": "9631020123",
        "lat_off": 0.002, "lng_off": -0.011, "expected": "Low",
        "location_name": "Park road",
    },
    {
        "description": "Mild fever since morning, body ache, runny nose, standard cold symptoms, no breathing difficulty",
        "caller": "Pooja Verma", "phone": "9522021234",
        "lat_off": -0.005, "lng_off": 0.017, "expected": "Low",
        "location_name": "Housing board",
    },
    {
        "description": "Small cut on finger from knife while cooking, minor bleeding, already cleaned the wound at home",
        "caller": "Radha Bai", "phone": "9413022345",
        "lat_off": 0.009, "lng_off": 0.004, "expected": "Low",
        "location_name": "Residential street",
    },
    {
        "description": "Backache, chronic issue, slightly worse today after lifting, no trauma, can walk normally",
        "caller": "Sunil Joshi", "phone": "9304023456",
        "lat_off": -0.013, "lng_off": -0.007, "expected": "Low",
        "location_name": "Office area",
    },
    {
        "description": "Minor headache, been sitting in front of computer all day, mild pain, no vomiting or neck stiffness",
        "caller": "IT Employee", "phone": "9195024567",
        "lat_off": 0.017, "lng_off": -0.012, "expected": "Low",
        "location_name": "Tech park",
    },
    {
        "description": "Toothache, pain started yesterday, swelling on gum, taking painkillers, needs dental referral",
        "caller": "Basappa Kamble", "phone": "9086025678",
        "lat_off": -0.008, "lng_off": 0.023, "expected": "Low",
        "location_name": "Market area",
    },
    {
        "description": "Insect sting on arm, mild local swelling and itching, no throat swelling, breathing completely fine",
        "caller": "Farmer", "phone": "9977026789",
        "lat_off": 0.023, "lng_off": 0.001, "expected": "Low",
        "location_name": "Farming area",
    },
    {
        "description": "Period cramps, severe pain today, took medication, pain reducing, no other symptoms",
        "caller": "College Student", "phone": "9868027890",
        "lat_off": -0.021, "lng_off": -0.010, "expected": "Low",
        "location_name": "College hostel",
    },
    {
        "description": "Mild nausea after eating street food, one episode of vomiting, feeling better now, no fever",
        "caller": "Girish Naik", "phone": "9759028901",
        "lat_off": 0.011, "lng_off": 0.015, "expected": "Low",
        "location_name": "Food street",
    },
    {
        "description": "Elderly patient, minor nose bleed, stopped after 10 minutes of pressure, slightly anxious now",
        "caller": "Son of patient", "phone": "9650029012",
        "lat_off": -0.016, "lng_off": -0.004, "expected": "Low",
        "location_name": "Senior citizen home",
    },
]


def get_random_scenario(risk_filter: str = None) -> dict:
    """Return a random scenario, optionally filtered by expected risk level."""
    pool = SCENARIOS
    if risk_filter:
        pool = [s for s in SCENARIOS if s["expected"] == risk_filter]
    if not pool:
        pool = SCENARIOS

    s = random.choice(pool)
    return {
        "description": s["description"],
        "caller_name": s["caller"],
        "caller_phone": s["phone"],
        "lat": round(BASE_LAT + s["lat_off"] + random.uniform(-0.002, 0.002), 4),
        "lng": round(BASE_LNG + s["lng_off"] + random.uniform(-0.002, 0.002), 4),
        "location_name": s["location_name"],
        "expected_risk": s["expected"],
    }


def get_all_scenarios() -> list:
    return SCENARIOS
