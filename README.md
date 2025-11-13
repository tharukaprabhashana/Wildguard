# 🐾 WildGuard — Wildlife Rescue Coordination System for Yala National Park

> A real-world LLM-powered multi-agent system for wildlife rescue coordination at Sri Lanka's Yala National Park, featuring proximity-based ranger dispatch, interactive mapping, and comprehensive rescue analytics.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CrewAI](https://img.shields.io/badge/powered%20by-CrewAI-orange.svg)](https://www.crewai.com/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 🎯 Overview

WildGuard is an intelligent wildlife rescue coordination system designed for **Yala National Park (Block 1)**, Sri Lanka's most visited and biodiverse national park. The system coordinates real-time responses to wildlife incidents using:

- **5 Real Ranger Stations**: Palatupana, Katagamuwa, Yala HQ, Galge, and Buttawa with actual GPS coordinates
- **Proximity-Based Dispatch**: Selects the nearest available station using Haversine distance calculations with terrain-aware ETA
- **Interactive Folium Map**: Click-to-select incident locations with wildlife hotspots and station markers
- **LLM-Powered Analysis**: AI-driven incident assessment, triage, treatment planning, and public communication
- **Real-Time Coordination**: Asynchronous agent communication with complete rescue flow visualization
- **Comprehensive Analytics**: Timeline tracking, negotiation analysis, and dispatch reasoning

---

## 🖥️ Streamlit Dashboard

Launch the interactive dashboard for real-time wildlife rescue coordination:

```bash
streamlit run streamlit_wildguard.py
```

### Dashboard Features

#### 📝 Manual Incident Reporting
- **Interactive Yala Map**: Click anywhere on the map to set incident location
- **Detailed Forms**: Species, behavior, injury severity, reporter type
- **Wildlife Hotspots**: Visual overlays for Elephant Gathering, Leopard Ridge, Patanangala Beach, Kumana Lagoon, Yala Wetlands
- **Station Markers**: All 5 ranger stations with vehicle and equipment details
- **GPS Validation**: Ensures incidents are reported within Yala National Park boundaries

#### 📊 Four Comprehensive Tabs

1. **Overview Tab**
   - Live metrics: Messages, incidents, dispatches, triage assessments, vet responses
   - Agent communication timeline with expandable message details
   - Dispatch decision visualization with selected station and reasoning
   - Live operations map showing dispatched station routes to incident locations
   - Recent communications feed with performative tracking

2. **Communication Graph Tab**
   - Dynamic network visualization of agent interactions
   - Node sizing based on message activity
   - Color-coded agents (reporters, coordinators, stations, specialists)
   - Real-time edge updates showing communication flow
   - Interactive hover details

3. **Rescue Flow Timeline Tab**
   - 8-stage coordination progress tracking (0-100%)
   - Incident selector for multi-incident scenarios
   - Species, severity, and location metadata
   - Chronological message flow with expandable details:
     - 🚨 Incident Reported
     - 📡 Availability Check
     - 📞 Station Responses
     - 🚀 Dispatch Decision
     - ✅ En Route Acknowledgment
     - 🏥 Triage Assessment
     - 🩺 Treatment Plan
     - 📢 Public Alert Broadcast
   - Summary statistics: Response time, total messages, current stage

4. **Negotiation Analysis Tab**
   - Station proposal comparison table (distance, ETA, availability, capability, terrain, vehicle, staff)
   - Visual ETA and distance charts for all responding stations
   - Coordinator's dispatch reasoning
   - Decision factors breakdown
   - Rejection reasons for non-selected stations

#### 🎛️ System Controls
- **Start/Stop Buttons**: Conditional rendering based on system state
- **Status Indicators**: Real-time system running/stopped status
- **Message Feed**: Live updates as agents communicate
- **Auto-Refresh**: Dashboard updates automatically while system is running

---

## 🚀 Quick Start

```bash
# 1) Clone the repository
git clone https://github.com/tharukaprabhashana/smart-disaster-mas.git
cd smart-disaster-mas

# 2) Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3) Install dependencies
pip install -r requirements.txt

# 4) Set up environment variables
cp .env.example .env
# Edit .env with your OpenAI API key

# 5) Launch the dashboard
streamlit run streamlit_wildguard.py
```

### Environment Configuration

```env
# Required for LLM functionality
OPENAI_API_KEY=your_openai_key_here

# Optional overrides
LLM_MODEL=gpt-4o-mini                              # Default model
CREWAI_ENDPOINT=http://localhost:8001/run_agent    # LLM Gateway endpoint
CREWAI_USE_REAL=1                                  # 1: real LLM, 0: stub mode
WILDGUARD_VET_TRIGGER=1                            # Always request vet treatment
```

---

## 🤖 Multi-Agent Architecture

### Core Agents

| Agent | Role | Responsibilities |
|-------|------|-----------------|
| 🎤 **FieldReporterAgent** | Incident Observer | Normalizes field reports, validates against incident schema, broadcasts to coordinator |
| 🧭 **CoordinatorAgent** | Dispatch Coordinator | Queries all stations, collects proximity responses, selects nearest available, dispatches team |
| 🚨 **ProximityDispatcherAgent** (×5) | Ranger Station | Calculates distance/ETA with terrain factors, assesses equipment capability, responds with availability |
| 🩺 **TriageAgent** | Medical Assessor | Evaluates injury severity, recommends action (monitor/capture/treat), determines urgency level |
| 🏥 **VetAgent** | Treatment Planner | Develops treatment protocols, prescribes medications, plans follow-up care |
| 📢 **CommunicationAgent** | Public Relations | Crafts DWC-aligned alerts for SMS/social media with safety instructions |
| 📋 **BlackboardAgent** | Event Logger | Centralized logging of all incidents, dispatches, triage, treatments for analytics |

### Ranger Stations (Real Yala Locations)

```python
Palatupana:  6.2815°N, 81.4126°E  |  Vehicles: 4x4 Ambulance, Patrol Jeep
Katagamuwa:  6.3954°N, 81.3357°E  |  Vehicles: 4x4 Patrol, Motorcycle
Yala HQ:     6.3700°N, 81.5200°E  |  Vehicles: Command, Vet Mobile, Rescue Truck
Galge:       6.4426°N, 81.5725°E  |  Vehicles: 4x4 Patrol, Rescue Jeep
Buttawa:     6.3880°N, 81.5050°E  |  Vehicles: Patrol Jeep
```

### Communication Flow

```
User/Reporter → FieldReporter → Coordinator
                                    ↓
                      [Broadcast to all stations]
                                    ↓
                    ┌────────┬──────┴──────┬────────┐
                    ↓        ↓             ↓        ↓
              Palatupana  Katagamuwa   Yala_HQ   Galge  Buttawa
                    ↓        ↓             ↓        ↓        ↓
              [Calculate distance, ETA, check equipment]
                    ↓        ↓             ↓        ↓        ↓
                    └────────┴──────┬──────┴────────┘
                                    ↓
                          [Select nearest available]
                                    ↓
                            Dispatch Order
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
              TriageAgent      VetAgent    CommunicationAgent
                    ↓               ↓               ↓
                    └───────────────┴───────────────┘
                                    ↓
                            BlackboardAgent
```

---

## 📍 Proximity-Based Dispatch Algorithm

### Distance Calculation
Uses **Haversine formula** for accurate great-circle distance between GPS coordinates:

```python
distance_km = 2 * R * arcsin(√(sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)))
```

### Terrain-Aware ETA

Different terrain types affect travel speed:

| Terrain | Speed Multiplier | Example |
|---------|-----------------|---------|
| Forest | 0.3 | Dense jungle, slow progress |
| Scrubland | 0.7 | Rocky outcrops, vegetation |
| Grassland | 1.0 | Open plains, normal speed |
| Wetland | 0.2 | Marsh areas, very slow |
| Road | 1.5 | Paved/dirt roads, faster |

**ETA Formula:**
```python
terrain_factor = TERRAIN_MULTIPLIERS[terrain_type]
vehicle_speed = VEHICLE_SPEEDS[vehicle_type]  # km/h
travel_time = (distance_km / vehicle_speed) / terrain_factor
eta_minutes = travel_time * 60 + 5  # +5 min prep time
```

### Selection Criteria
1. **Station must be available** (not on another mission)
2. **Station must have required equipment** (tranquilizer kit for capture operations)
3. **Nearest station wins** (shortest distance/ETA)

---

## 🧪 Example Rescue Scenarios

### 1. Injured Elephant at Menik River
```yaml
Species: Asian elephant
Location: Menik River Corridor (6.2725°N, 81.5869°E)
Behavior: Limping, appears disoriented
Injury: High severity
Reporter: Ranger patrol

Expected Flow:
- Palatupana responds: 25.3 km, 59 min ETA
- Yala HQ responds: 10.1 km, 27 min ETA ← SELECTED
- Dispatch: Rescue Truck with full medical equipment
- Triage: Capture and transport recommended
- Vet: Antibiotics, pain management, 3-day observation
- Communication: "INJURED ELEPHANT ALERT - DWC team en route"
```

### 2. Leopard Sighting at Leopard Ridge
```yaml
Species: Sri Lankan leopard
Location: Leopard Ridge (6.4272°N, 81.5394°E)
Behavior: Hunting, territorial display
Injury: None
Reporter: Tourist group

Expected Flow:
- Galge responds: 13.0 km, 33 min ETA ← SELECTED
- Dispatch: 4x4 Patrol for monitoring
- Triage: Monitor only, maintain safe distance
- Communication: "LEOPARD SIGHTING - Keep distance, do not approach"
```

### 3. Deer Hit by Vehicle
```yaml
Species: Sambar deer
Location: Patanangala Beach Road (6.2680°N, 81.5308°E)
Behavior: Down, shallow breathing
Injury: Critical
Reporter: Vehicle driver

Expected Flow:
- Palatupana responds: 14.5 km, 36 min ETA ← SELECTED
- Dispatch: 4x4 Ambulance with emergency equipment
- Triage: Immediate veterinary intervention required
- Vet: Stabilization, IV fluids, transfer to wildlife hospital
- Communication: "INJURED DEER - Road temporarily closed for rescue"
```

---

## 🗂️ Project Structure

```
smart-disaster-mas/
├── streamlit_wildguard.py          # Main Streamlit dashboard
├── broker.py                       # Async message broker
├── crewai_client.py               # LLM client with schema validation
├── llm_gateway.py                 # FastAPI LLM gateway (optional)
├── agents/
│   ├── base_agent.py              # Abstract base agent class
│   ├── field_reporter_agent.py    # Incident normalization
│   ├── coordinator_agent.py       # Proximity dispatch coordinator
│   ├── proximity_dispatcher_agent.py  # Ranger station agent
│   ├── triage_agent.py            # Medical assessment
│   ├── vet_agent.py               # Treatment planning
│   ├── communication_agent.py     # Public alerts
│   └── blackboard_agent.py        # Event logging
├── config/
│   └── yala_sanctuary.py          # Station locations, hotspots, terrain
├── prompts/
│   ├── field_reporter.txt         # Incident analysis prompt
│   ├── coordinator.txt            # Dispatch reasoning prompt
│   ├── triage_agent.txt           # Medical assessment prompt
│   ├── vet_agent.txt              # Treatment planning prompt
│   └── communication_writer.txt   # Public alert prompt
├── schemas/
│   ├── incident.schema.json       # Incident validation
│   ├── dispatch.schema.json       # Dispatch validation
│   ├── bid.schema.json            # Station bid validation
│   ├── triage_agent.schema.json   # Triage validation
│   ├── vet_response.schema.json   # Treatment validation
│   └── communication_writer.schema.json  # Alert validation
├── requirements.txt               # Python dependencies
├── .env                          # Environment variables
└── README.md                     # This file
```

---

## 🔧 Development

### Running Tests
```bash
# Basic system test (deprecated, use dashboard instead)
# python test_harness_wildguard.py

# Recommended: Use Streamlit dashboard for interactive testing
streamlit run streamlit_wildguard.py
```

### Adding New Features

1. **New Agent Type**
   - Create agent file in `agents/`
   - Extend `BaseAgent` class
   - Add prompt in `prompts/`
   - Add schema in `schemas/`
   - Register in `streamlit_wildguard.py`

2. **New Ranger Station**
   - Add station to `config/yala_sanctuary.py` RANGER_STATIONS dict
   - Include: name, lat, lon, vehicles, equipment, staff, description
   - Station will automatically appear in dashboard map and dispatch

3. **New Wildlife Hotspot**
   - Add to `config/yala_sanctuary.py` WILDLIFE_HOTSPOTS dict
   - Include: name, lat, lon, radius_km, common_species, description
   - Hotspot will appear on map with semi-transparent overlay

### LLM Gateway (Optional)

For development without API calls, use stub mode (default):
```bash
export CREWAI_USE_REAL=0
```

For production with real LLM:
```bash
# Terminal 1: Start gateway
python llm_gateway.py

# Terminal 2: Enable real LLM
export CREWAI_USE_REAL=1
streamlit run streamlit_wildguard.py
```

---

## 📊 Key Technologies

- **Streamlit**: Interactive web dashboard
- **Folium**: Interactive map visualization
- **NetworkX**: Agent communication graph
- **Plotly**: Analytics charts
- **CrewAI**: LLM agent framework
- **OpenAI GPT-4**: Natural language processing
- **AsyncIO**: Concurrent agent communication
- **JSON Schema**: Response validation
- **FastAPI**: Optional LLM gateway

---

## 🐛 Common Issues

| Issue | Solution |
|-------|----------|
| Start/Stop buttons appear twice | Fixed with conditional rendering based on `system_running` state |
| Progress bar stuck at 62% | Fixed by detecting CommunicationAgent broadcast as final stage |
| Location shows "unknown" | Fixed with `get_location_name()` using proximity to hotspots/stations |
| Stations not responding | Fixed by adding `broker.register()` in ProximityDispatcherAgent.run() |
| Map clicks not registering | Validate clicks are within Yala boundary (6.25-6.45°N, 81.33-81.63°E) |

---

## 🎓 Research & Citations

This system demonstrates practical applications of:
- Multi-agent systems for emergency response coordination
- LLM-powered decision making in time-critical scenarios
- Proximity-based resource allocation algorithms
- Real-time visualization of agent communication networks
- Schema-validated AI outputs for reliability

**Use Cases:**
- Wildlife conservation organizations
- National park management
- Emergency response training
- Multi-agent system research
- Human-AI collaboration studies

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 👥 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

---

## 📧 Contact

**Project Maintainer**: Tharuka Prabhashana  
**Repository**: [github.com/tharukaprabhashana/Wildguard](https://github.com/tharukaprabhashana/Wildguard)  
**Issues**: [Submit an issue](https://github.com/tharukaprabhashana/Wildguard/issues)
   
---

## 🙏 Acknowledgments

- **Department of Wildlife Conservation (DWC), Sri Lanka**: For wildlife management protocols
- **Yala National Park**: For inspiring this real-world simulation
- **OpenAI**: For GPT-4 language model
- **CrewAI**: For agent framework
- **Streamlit**: For rapid dashboard development

---

**Built with care to make wildlife rescue coordination safer, faster, and more intelligent.** 🐾
