# AI-BASED ENHANCED EMERGENCY RESPONSE SYSTEM (AERS)

## A Project Report Submitted in Partial Fulfilment of Requirements for the Award of the Degree of

### BACHELOR OF COMPUTER APPLICATIONS

---

**Submitted by:** Darshan

**Under the Guidance of:** Claude AI Assistant

---

## Certificate

This is to certify that the project work entitled "AI-Based Enhanced Emergency Response System (AERS)" is a bonafied work carried out by the student for the partial fulfilment of the requirements for the award of the degree of Bachelor of Computer Application.

This project has been designed and implemented as a web-based emergency response system with ML-powered triage, ambulance dispatch, and hospital selection capabilities.

**Project Guide:** ____________________

**HOD:** ____________________

---

## Abstract

The AI-Based Enhanced Emergency Response System (AERS) is a sophisticated web-based emergency response system that integrates artificial intelligence with emergency medical services. The system utilizes machine learning (Logistic Regression with TF-IDF vectorization) for automated risk assessment and triage of emergency cases.

AERS provides real-time ambulance dispatch based on proximity and availability, with intelligent hospital selection considering specialty matching, capacity, and distance. The system features a priority queue mechanism with preemption capabilities for critical cases, ensuring optimal resource allocation during high-demand situations.

Key features include:
- ML-powered triage for automated risk assessment (Critical/Urgent/Low)
- Real-time ambulance fleet tracking with movement simulation
- Intelligent hospital selection based on multiple weighted criteria
- Priority queue with preemption for emergency cases
- WebSocket-based real-time updates for all stakeholders
- Admin panel for managing hospitals and ambulances
- Multiple dashboards for patients, drivers, and hospital administrators

---

## Acknowledgement

We take this opportunity to express our sincere gratitude to all those who have contributed to the successful completion of this project.

We express our gratitude to the developers and maintainers of the open-source technologies used in this project, including FastAPI, scikit-learn, Leaflet, and Bootstrap.

We acknowledge the support of the open-source community for providing excellent documentation and resources that made this project possible.

A special thanks to all the users and testers who provided valuable feedback during the development phase.

---

## Declaration

I hereby declare that the project entitled "AI-Based Enhanced Emergency Response System (AERS)" has not been duplicated from any other source. This project is done in partial fulfilment of the requirements for the award of degree of Bachelor of Computer Application.

---

## Table of Contents

1. Introduction
   - 1.1 Overview
   - 1.2 Objectives
   - 1.3 Benefits
   - 1.4 Identification of Needs

2. Survey of Technologies
   - 2.1 Programming Languages
   - 2.2 Frameworks and Libraries
   - 2.3 Database
   - 2.4 External Services

3. Requirement Analysis
   - 3.1 Feasibility Study
   - 3.2 Hardware and Software Requirements
   - 3.3 System Architecture
   - 3.4 Data Flow Design

4. System Design
   - 4.1 Module Description
   - 4.2 Database Design
   - 4.3 API Design

5. Implementation
   - 5.1 Backend Implementation
   - 5.2 Frontend Implementation
   - 5.3 Testing

6. Screenshots and User Interface

7. Conclusion
   - 7.1 Limitations
   - 7.2 Future Scope
   - 7.3 Conclusion
   - 7.4 References

---

## Chapter 1: Introduction

### 1.1 Overview

The AI-Based Enhanced Emergency Response System (AERS) is a comprehensive emergency response management system that leverages artificial intelligence to streamline the emergency medical services workflow. Traditional emergency response systems often rely on manual dispatching and hospital selection, which can lead to delays and suboptimal resource allocation during emergencies.

AERS automates the entire emergency response pipeline:
1. **Triage**: ML-powered risk assessment using Logistic Regression and TF-IDF vectorization
2. **Ambulance Dispatch**: Intelligent dispatch based on proximity, availability, and priority
3. **Hospital Selection**: Weighted scoring algorithm considering specialty match, capacity, and distance
4. **Real-time Tracking**: Live ambulance movement visualization on interactive maps

### 1.2 Objectives

The primary objectives of the AERS project are:

1. **Automate Emergency Triage**: Implement machine learning to automatically assess and categorize emergency cases into risk levels (Critical, Urgent, Low)

2. **Optimize Ambulance Dispatch**: Develop an intelligent dispatch system that considers ambulance proximity, availability, and the priority of cases

3. **Improve Hospital Selection**: Create a hospital selection algorithm that matches patient needs with hospital capabilities (specialties, ICU capacity)

4. **Enable Real-time Tracking**: Provide live tracking of ambulance movement and case status through interactive maps

5. **Multi-portal Access**: Provide dedicated interfaces for patients, drivers, hospital administrators, and system administrators

6. **Handle High-demand Scenarios**: Implement priority queue with preemption for critical cases when all ambulances are busy

### 1.3 Benefits

The AERS system provides numerous benefits over traditional emergency response methods:

- **Faster Response Times**: Automated triage and dispatch reduce the time from emergency call to ambulance dispatch
- **Improved Resource Allocation**: ML-based routing ensures optimal use of limited ambulance resources
- **Better Patient Outcomes**: Hospital selection based on specialty matching increases chances of appropriate care
- **Transparency**: Real-time tracking and status updates keep all stakeholders informed
- **Scalability**: The system can handle multiple simultaneous emergency cases with intelligent queue management

### 1.4 Identification of Needs

The development of AERS addresses several critical needs in emergency medical services:

1. **Manual Triage Inefficiency**: Traditional systems rely on human operators to assess emergency severity, leading to inconsistencies and delays

2. **Suboptimal Dispatch**: Without automated systems, ambulance dispatch may not consider the nearest available unit or the most appropriate ambulance type

3. **Hospital Selection Challenges**: Selecting the appropriate hospital requires considering multiple factors (specialties, capacity, distance) that are difficult to process manually

4. **Lack of Transparency**: Patients and administrators often lack visibility into the emergency response progress

5. **Resource Management**: During peak times, all ambulances may be busy, requiring intelligent queue management with priority handling

---

## Chapter 2: Survey of Technologies

### 2.1 Programming Languages

The AERS project utilizes the following programming languages:

| Language | Purpose |
|----------|---------|
| Python | Backend API, ML model training, business logic |
| HTML/CSS/JavaScript | Frontend dashboards and user interfaces |
| SQL | Database queries |

### 2.2 Frameworks and Libraries

| Framework/Library | Version | Purpose |
|-------------------|---------|---------|
| FastAPI | Latest | Web framework for building REST APIs |
| Uvicorn | Latest | ASGI server for FastAPI |
| scikit-learn | Latest | ML model training and prediction |
| Pandas | Latest | Data manipulation |
| NumPy | Latest | Numerical computations |
| Pydantic | Latest | Data validation |
| WebSockets | Latest | Real-time bidirectional communication |
| Bootstrap | 5.3.0 | CSS framework for responsive UI |
| Leaflet | 1.9.4 | Interactive maps |
| Chart.js | 4.4.0 | Data visualization for analytics |

### 2.3 Database

- **SQLite**: Lightweight, file-based database for storing cases, ambulance events, and analytics

### 2.4 External Services

- **OpenStreetMap**: Free, open-source map tiles for Leaflet.js
- **Unpkg CDN**: CDN for serving Leaflet.js and Bootstrap libraries
- **jsDelivr CDN**: CDN for serving Bootstrap Icons

---

## Chapter 3: Requirement Analysis

### 3.1 Feasibility Study

**Technical Feasibility:**
- The project uses proven, stable technologies (FastAPI, scikit-learn, SQLite)
- ML model training is straightforward with scikit-learn
- Real-time updates are handled efficiently with WebSockets

**Operational Feasibility:**
- The system automates manual processes, reducing operator workload
- Multiple dashboards provide intuitive interfaces for different user roles

**Economic Feasibility:**
- Open-source technologies minimize licensing costs
- SQLite requires no database server setup
- Lightweight deployment requirements reduce infrastructure costs

### 3.2 Hardware and Software Requirements

**Hardware Requirements:**
- Server: Minimum 2GB RAM, any modern processor
- Client: Any device with a modern web browser

**Software Requirements:**
- Python 3.9+
- Web browser (Chrome, Firefox, Edge, Safari)
- Internet connection for map tiles

### 3.3 System Architecture

The AERS system follows a client-server architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENTS                             │
├─────────────┬─────────────┬──────────┬─────────┬────────────┤
│   Patient   │    Driver   │ Hospital │  Admin  │ Analytics │
│  Dashboard  │  Dashboard  │  Portal  │  Panel  │   View    │
└──────┬──────┴──────┬───────┴────┬─────┴────┬────┴─────┬──────┘
       │            │           │          │          │
       └────────────┴───────────┴──────────┴──────────┘
                            │
                     WebSocket + HTTP
                            │
       ┌────────────────────┴────────────────────┐
       │              AERS BACKEND                │
       ├─────────────────────────────────────────┤
       │  FastAPI Server + WebSocket Manager     │
       ├─────────────────────────────────────────┤
       │  ┌─────────┐ ┌─────────┐ ┌────────────┐  │
       │  │Predictor│ │Decision │ │  Database │  │
       │  │  (ML)   │ │ Engine  │ │  (SQLite) │  │
       │  └────┬────┘ └────┬────┘ └─────┬──────┘  │
       │       │          │            │         │
       │  ┌────┴────┐ ┌────┴────┐       │         │
       │  │Ambulance│ │Hospital │       │         │
       │  │ Module │ │ Module  │───────┘         │
       │  └────────┘ └─────────┘                  │
       └──────────────────────────────────────────┘
```

### 3.4 Data Flow Design

**Emergency Case Flow:**

1. User submits emergency description via Patient Dashboard
2. Predictor module processes description through ML model
3. Risk level is determined (Critical/Urgent/Low)
4. Ambulance module finds nearest available ambulance
5. Hospital module selects best hospital based on specialty match
6. Dispatch details are set and case is persisted to database
7. WebSocket broadcasts update to all connected clients
8. Timeline auto-progresses (pickup → delivery → available)

---

## Chapter 4: System Design

### 4.1 Module Description

#### 4.1.1 Backend Modules

| Module | File | Description |
|--------|------|-------------|
| Predictor | `backend/predictor.py` | ML triage engine using Logistic Regression + TF-IDF |
| Ambulance | `backend/ambulance.py` | Fleet management, dispatch, movement tracking |
| Hospital | `backend/hospital.py` | Hospital registry and selection algorithm |
| Decision | `backend/decision.py` | Orchestrates the full emergency response pipeline |
| Database | `backend/database.py` | SQLite persistence for cases and analytics |
| WS Manager | `backend/ws_manager.py` | WebSocket broadcast for real-time updates |

#### 4.1.2 Frontend Dashboards

| Dashboard | Route | Purpose |
|-----------|-------|---------|
| Main | `/` | Emergency request submission and case tracking |
| Tracking | `/tracking` | Live fleet tracking with map visualization |
| Analytics | `/analytics` | Charts and statistics |
| Admin | `/admin` | Manage hospitals and ambulances |
| Patient | `/patient` | Patient portal for case status |
| Driver | `/driver` | Driver dashboard with navigation |
| Hospital | `/hospital` | Hospital incoming patient dashboard |

### 4.2 Database Design

**Tables:**

1. **cases**: Stores emergency case records
   - case_id, timestamp, risk_level, confidence
   - description, caller_name, caller_phone
   - incident_lat, incident_lng
   - ambulance_id, ambulance_eta
   - hospital_id, hospital_name, specialty
   - dispatch_status, delivery_status, delivery_time

2. **ambulance_events**: Log of ambulance status changes
   - timestamp, amb_id, event, case_id

3. **sim_runs**: Simulator test results
   - sim_id, expected_risk, actual_risk, confidence, status

### 4.3 API Design

**Key Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/analyze` | Full pipeline: triage + dispatch + hospital |
| POST | `/triage` | ML triage only |
| GET | `/status` | System status |
| GET | `/ambulances` | Fleet list |
| GET | `/hospitals` | Hospital list |
| GET | `/cases` | Recent cases |
| GET | `/ws` | WebSocket for real-time updates |

---

## Chapter 5: Implementation

### 5.1 Backend Implementation

The backend is built with FastAPI and consists of the following key components:

**ML Triage (predictor.py):**
- Loads pre-trained Logistic Regression model
- Uses TF-IDF vectorizer for text transformation
- Returns risk level with confidence scores

**Ambulance Management (ambulance.py):**
- In-memory fleet tracking
- Haversine distance calculation
- Priority queue with preemption logic
- Movement simulation for real-time tracking

**Hospital Selection (hospital.py):**
- Weighted scoring algorithm
- Specialty matching
- Capacity and ICU bed tracking

**Decision Engine (decision.py):**
- Orchestrates triage → dispatch → hospital selection
- Sets up auto-progression timeline
- Persists cases to database
- Broadcasts updates via WebSocket

### 5.2 Frontend Implementation

Frontend uses vanilla HTML/CSS/JS with Bootstrap and Leaflet:

- **Leaflet.js**: Interactive maps with custom markers
- **Bootstrap 5**: Responsive UI components
- **WebSocket Client**: Real-time updates
- **Chart.js**: Analytics visualizations

### 5.3 Testing

The system includes comprehensive testing:

- ML model validation
- Ambulance dispatch logic testing
- Hospital selection algorithm verification
- End-to-end pipeline testing

---

## Chapter 6: Screenshots and User Interface

The AERS system provides multiple user interfaces:

1. **Main Dashboard**: Emergency request form with live case tracking
2. **Tracking Page**: Full fleet overview with movement visualization
3. **Analytics Dashboard**: Charts showing case statistics
4. **Admin Panel**: CRUD operations for hospitals and ambulances
5. **Patient Portal**: Case status tracking with map
6. **Driver Dashboard**: Navigation map for patient pickup and hospital delivery

---

## Chapter 7: Conclusion

### 7.1 Limitations

- ML model requires training data for accuracy
- In-memory ambulance tracking resets on server restart
- No authentication/authorization implemented
- Limited to geographic area around Haveri, Karnataka, India
- No mobile application (web-based only)

### 7.2 Future Scope

- Add mobile applications (iOS/Android)
- Implement user authentication
- Integrate with real GPS tracking systems
- Add payment gateway for hospital services
- Implement SMS/email notifications
- Expand to multiple geographic regions
- Add AI improvements with deep learning models

### 7.3 Conclusion

The AI-Based Enhanced Emergency Response System successfully demonstrates the integration of machine learning with emergency medical services. The system automates triage, optimizes ambulance dispatch, and provides intelligent hospital selection, significantly improving the efficiency of emergency response.

The modular architecture allows easy scaling and maintenance. Real-time updates via WebSocket ensure all stakeholders have visibility into the emergency response progress.

### 7.4 References

1. FastAPI Documentation - https://fastapi.tiangolo.com/
2. scikit-learn Documentation - https://scikit-learn.org/
3. Leaflet.js Documentation - https://leafletjs.com/
4. Bootstrap Documentation - https://getbootstrap.com/
5. Python Documentation - https://docs.python.org/

---

## Appendix: Project Structure

```
AERS-Complete_version/
├── app.py              # FastAPI server
├── requirements.txt    # Dependencies
├── tests.py           # Test suite
├── README.md           # Documentation
├── CLAUDE.md          # Development guidance
├── backend/           # Backend modules
│   ├── predictor.py   # ML triage
│   ├── ambulance.py   # Fleet management
│   ├── hospital.py    # Hospital selection
│   ├── decision.py   # Pipeline orchestration
│   ├── database.py   # SQLite persistence
│   └── ws_manager.py  # WebSocket
├── frontend/           # Web dashboards
│   ├── index.html
│   ├── tracking.html
│   ├── analytics.html
│   ├── admin.html
│   ├── patient.html
│   ├── driver.html
│   └── hospital.html
├── model/             # ML model
│   ├── model.pkl
│   ├── vectorizer.pkl
│   └── train.py
├── simulator/         # Load testing
│   ├── engine.py
│   ├── dashboard.html
│   └── scenarios.py
└── data/             # Runtime data
    └── aers.db
```

---

**End of Report**