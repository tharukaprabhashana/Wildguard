"""
Streamlit UI for WildGuard — Wild Animal Rescue & Response
Lightweight dashboard to start/stop the wildlife MAS and observe messages.
"""

import os
import time
import json
import asyncio
from threading import Thread, Event
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
import queue

import streamlit as st
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium

from broker import Broker
from agents.base_agent import BaseAgent
from agents.field_reporter_agent import FieldReporterAgent
from agents.coordinator_agent import CoordinatorAgent
from agents.proximity_dispatcher_agent import ProximityDispatcherAgent
from agents.triage_agent import TriageAgent
from agents.vet_agent import VetAgent
from agents.communication_agent import CommunicationAgent
from agents.blackboard_agent import BlackboardAgent
from config.yala_sanctuary import RANGER_STATIONS, WILDLIFE_HOTSPOTS, YALA_BOUNDARY, get_location_name

# -------------------------
# Session State
# -------------------------
st.set_page_config(page_title="WildGuard Dashboard", page_icon="🐾", layout="wide")

if "system_running" not in st.session_state:
    st.session_state.system_running = False
if "message_queue" not in st.session_state:
    st.session_state.message_queue = []  # UI-owned store
if "tap_queue" not in st.session_state:
    st.session_state.tap_queue = queue.Queue()  # background → UI tap
if "agent_activities" not in st.session_state:
    st.session_state.agent_activities = defaultdict(list)
if "broker" not in st.session_state:
    st.session_state.broker = None
if "bg_thread" not in st.session_state:
    st.session_state.bg_thread = None
if "stats" not in st.session_state:
    st.session_state.stats = {"incidents": 0, "bids": 0, "awards": 0, "triage": 0, "vet_responses": 0}

# -------------------------
# Monitored Broker (taps messages)
# -------------------------
class MonitoredBroker(Broker):
    def __init__(self, message_queue: queue.Queue | None = None):
        super().__init__()
        self._tap = message_queue

    async def publish(self, msg):
        # tap into thread-safe queue (avoid accessing st.session_state inside worker thread)
        if self._tap is not None:
            packet = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "from": msg.get("from"),
                "to": msg.get("to"),
                "performative": msg.get("performative"),
                "content": msg.get("content", {}),
            }
            try:
                self._tap.put_nowait(packet)
            except Exception:
                pass
        await super().publish(msg)

# -------------------------
# Background MAS runner
# -------------------------

def run_wildguard(broker: Broker, config: dict, run_event: Event):
    async def runner():
        # Apply runtime env flags (LLM always enabled)
        os.environ["WILDGUARD_VET_TRIGGER"] = "1" if config.get("vet_trigger") else "0"

        # Instantiate agents
        manual_mode = config.get("manual_mode", False)
        field = FieldReporterAgent("FieldReporterAgent", broker, manual_mode=manual_mode, event_interval=config.get("event_interval", 10))
        
        # Create proximity dispatcher stations (real Yala stations)
        station_names = list(RANGER_STATIONS.keys())
        coordinator = CoordinatorAgent("CoordinatorAgent", broker, station_names=station_names)
        stations = [ProximityDispatcherAgent(name, broker, name, RANGER_STATIONS[name]) for name in station_names]
        
        triage = TriageAgent("TriageAgent", broker)
        vet = VetAgent("VetAgent", broker)
        comm = CommunicationAgent("CommunicationAgent", broker)
        board = BlackboardAgent("BlackboardAgent", broker)

        tasks = [asyncio.create_task(a.run()) for a in [field, coordinator, *stations, triage, vet, comm, board]]
        await asyncio.sleep(2.0)  # Give agents time to register
        
        print(f"\n{'='*60}")
        print(f"[WildGuard] All agents started. Registered agents:")
        for agent_name in [field.name, coordinator.name] + [s.name for s in stations] + [triage.name, vet.name, comm.name, board.name]:
            print(f"  ✓ {agent_name}")
        print(f"[WildGuard] Yala National Park Ranger Stations:")
        for station in stations:
            print(f"  📍 {station.station_name}: {station.lat:.4f}, {station.lon:.4f}")
        print(f"[WildGuard] System ready. Waiting for incidents...")
        print(f"{'='*60}\n")

        # Poll pending_reports queue and inject into FieldReporter
        pending_queue = config.get("pending_reports")
        
        async def poll_reports():
            while run_event.is_set():
                try:
                    # Non-blocking check for queued reports
                    if pending_queue and not pending_queue.empty():
                        raw_report = pending_queue.get_nowait()
                        print(f"[poll_reports] Injecting report into FieldReporter inbox...")
                        await field.inbox.put({
                            "from": "UI",
                            "to": "FieldReporterAgent",
                            "performative": "inform",
                            "content": {"report": raw_report}
                        })
                        print(f"[poll_reports] ✓ Report injected successfully")
                except Exception as e:
                    print(f"[poll_reports] Error: {e}")
                await asyncio.sleep(0.3)
        
        poll_task = asyncio.create_task(poll_reports())

        # Run until UI flips the switch
        while run_event.is_set():
            await asyncio.sleep(0.5)
        
        poll_task.cancel()
        for t in tasks:
            t.cancel()

    try:
        asyncio.run(runner())
    except Exception as e:
        print(f"[WildGuard UI] runner error: {e}")

# -------------------------
# UI
# -------------------------
st.title("🐾 WildGuard — Wildlife Rescue MAS")
st.caption("LLM-assisted, schema-validated multi-agent coordination")

with st.sidebar:
    st.subheader("📝 Report Wildlife Incident")
    st.caption("Fill in details and submit to create a new incident")
    
    species = st.text_input("Species", "Asian elephant", help="e.g., elephant, deer, monkey, leopard")
    behavior = st.text_area("Observed behavior", "Limping near riverbank, appears disoriented", height=80, help="Describe what you observe")
    injury = st.selectbox("Injury severity", ["unknown", "low", "medium", "high", "critical"], index=2)
    
    st.markdown("**📍 Incident Location**")
    st.caption("Click on the map to set incident location")
    
    # Create interactive Folium map of Yala National Park
    m = folium.Map(
        location=[YALA_BOUNDARY["center"]["lat"], YALA_BOUNDARY["center"]["lon"]],
        zoom_start=12,
        tiles="OpenStreetMap",
        width=280,
        height=300
    )
    
    # Add Yala boundary rectangle
    folium.Rectangle(
        bounds=[
            [YALA_BOUNDARY["min_lat"], YALA_BOUNDARY["min_lon"]],
            [YALA_BOUNDARY["max_lat"], YALA_BOUNDARY["max_lon"]]
        ],
        color="green",
        fill=True,
        fillColor="green",
        fillOpacity=0.1,
        popup="Yala National Park - Block 1",
        tooltip="Yala National Park Boundary"
    ).add_to(m)
    
    # Add ranger station markers (green house icons)
    for station_name, station_data in RANGER_STATIONS.items():
        folium.Marker(
            location=[station_data["lat"], station_data["lon"]],
            popup=folium.Popup(f"<b>{station_name}</b><br>{station_data['description']}<br>Vehicles: {', '.join(station_data['vehicles'])}<br>Staff: {station_data['staff_count']}", max_width=200),
            tooltip=f"🏠 {station_name}",
            icon=folium.Icon(color="green", icon="home", prefix="fa")
        ).add_to(m)
    
    # Add wildlife hotspot circles (semi-transparent)
    for hotspot_name, hotspot_data in WILDLIFE_HOTSPOTS.items():
        folium.Circle(
            location=[hotspot_data["lat"], hotspot_data["lon"]],
            radius=hotspot_data["radius_km"] * 1000,  # Convert km to meters
            color="orange",
            fill=True,
            fillColor="orange",
            fillOpacity=0.15,
            popup=folium.Popup(f"<b>{hotspot_name}</b><br>{hotspot_data['description']}<br>Common species: {', '.join(hotspot_data['common_species'])}", max_width=200),
            tooltip=f"🐾 {hotspot_name}"
        ).add_to(m)
    
    # Initialize incident location in session state
    if "incident_location" not in st.session_state:
        st.session_state.incident_location = {
            "lat": 6.35,
            "lon": 81.52
        }
    
    # Initialize click tracking
    if "last_map_click" not in st.session_state:
        st.session_state.last_map_click = None
    
    # Add current incident marker if set
    if st.session_state.incident_location:
        folium.Marker(
            location=[st.session_state.incident_location["lat"], st.session_state.incident_location["lon"]],
            popup="Incident Location (Click map to change)",
            tooltip="📍 Incident",
            icon=folium.Icon(color="red", icon="exclamation-triangle", prefix="fa")
        ).add_to(m)
    
    # Render map and capture clicks
    map_data = st_folium(
        m, 
        width=280, 
        height=300, 
        key="yala_map"
    )
    
    # Update location when user clicks on map or any object
    clicked_lat, clicked_lng = None, None
    
    if map_data:
        # Check for click on empty map area
        if map_data.get("last_clicked") and map_data["last_clicked"] is not None:
            clicked_lat = map_data["last_clicked"]["lat"]
            clicked_lng = map_data["last_clicked"]["lng"]
        # Check for click on map objects (boundaries, markers, circles)
        elif map_data.get("last_object_clicked") and map_data["last_object_clicked"] is not None:
            clicked_lat = map_data["last_object_clicked"]["lat"]
            clicked_lng = map_data["last_object_clicked"]["lng"]
    
    # Process the click if we got coordinates
    if clicked_lat is not None and clicked_lng is not None:
        click_coords = (clicked_lat, clicked_lng)
        
        # Only process if this is a new click (different from last one)
        if st.session_state.last_map_click != click_coords:
            st.session_state.last_map_click = click_coords
            
            # Check if within Yala boundaries
            if (YALA_BOUNDARY["min_lat"] <= clicked_lat <= YALA_BOUNDARY["max_lat"] and
                YALA_BOUNDARY["min_lon"] <= clicked_lng <= YALA_BOUNDARY["max_lon"]):
                st.session_state.incident_location = {"lat": clicked_lat, "lon": clicked_lng}
                st.success(f"✓ Location set: {clicked_lat:.4f}, {clicked_lng:.4f}")
            else:
                st.warning("⚠️ Please click within Yala National Park boundary")
    
    # Display current coordinates (read-only)
    st.caption(f"📍 Selected: {st.session_state.incident_location['lat']:.6f}, {st.session_state.incident_location['lon']:.6f}")
    
    reporter_type = st.selectbox("Reporter", ["ranger", "citizen", "camera_trap", "drone"], index=0)
    
    # Submit incident button
    if st.button("📤 Submit Incident Report", key="submit_incident", type="primary", use_container_width=True, help="Send this report to the system"):
        if st.session_state.system_running and st.session_state.broker:
            # Get coordinates from map selection
            incident_lat = st.session_state.incident_location["lat"]
            incident_lon = st.session_state.incident_location["lon"]
            
            # Send report directly to FieldReporter via broker
            raw_report = {
                "text": f"{species} observed: {behavior}. Injury severity: {injury}",
                "gps": {"lat": incident_lat, "lon": incident_lon},
                "reporter": {"type": reporter_type, "reliability": 0.9}
            }
            # Queue the report for the background thread
            if "pending_reports" not in st.session_state:
                st.session_state.pending_reports = queue.Queue()
            st.session_state.pending_reports.put(raw_report)
            st.session_state.sidebar_message = ("success", f"✅ Incident submitted: {species} at ({incident_lat:.4f}, {incident_lon:.4f})")
        else:
            st.session_state.sidebar_message = ("warning", "⚠️ Start the system first before submitting reports")

    st.markdown("---")
    
    # Display status messages outside button blocks
    if "sidebar_message" in st.session_state:
        msg_type, msg_text = st.session_state.sidebar_message
        if msg_type == "success":
            st.success(msg_text)
        elif msg_type == "warning":
            st.warning(msg_text)
        elif msg_type == "info":
            st.info(msg_text)
    
    # Control buttons - only render once per session
    col1, col2 = st.columns(2)
    
    # Render Start button only when system is not running
    with col1:
        if not st.session_state.system_running:
            if st.button("🚀 Start", key="start_btn", use_container_width=True):
                st.session_state.system_running = True
                st.session_state.message_queue.clear()
                st.session_state.agent_activities.clear()
                # Clear graph positions for fresh start
                if "graph_positions" in st.session_state:
                    st.session_state.graph_positions = {}
                
                # Initialize pending reports queue
                if "pending_reports" not in st.session_state:
                    st.session_state.pending_reports = queue.Queue()

                # create run event and monitored broker tapping a thread-safe queue
                run_event = Event()
                run_event.set()
                st.session_state.run_event = run_event

                broker = MonitoredBroker(st.session_state.tap_queue)
                st.session_state.broker = broker
                cfg = {
                    "use_real_llm": True,  # Always use real LLM
                    "vet_trigger": True,  # Fixed: VetAgent always triggered after dispatch
                    "manual_mode": True,  # Disable auto synthetic reports
                    "pending_reports": st.session_state.pending_reports
                }
                th = Thread(target=run_wildguard, args=(broker, cfg, run_event), daemon=True)
                st.session_state.bg_thread = th
                th.start()
                st.session_state.sidebar_message = ("success", "WildGuard Yala started - Real ranger stations active")
                st.rerun()
        else:
            st.write("🟢 Running")
    
    # Render Stop button only when system is running
    with col2:
        if st.session_state.system_running:
            if st.button("🛑 Stop", key="stop_btn", use_container_width=True):
                st.session_state.system_running = False
                if st.session_state.get("run_event"):
                    st.session_state.run_event.clear()
                st.session_state.sidebar_message = ("warning", "Stopping…")
                st.rerun()
        else:
            st.write("⚫ Stopped")

# Main Dashboard
st.markdown("---")

# Live status metrics
status_col1, status_col2, status_col3, status_col4 = st.columns(4)
status_col1.metric("Messages", len(st.session_state.message_queue))
inc = sum(1 for m in st.session_state.message_queue if m.get("performative") == "advertise_incident")
dispatches = sum(1 for m in st.session_state.message_queue if m.get("performative") == "dispatch_order")
responses = sum(1 for m in st.session_state.message_queue if m.get("performative") == "availability_response")
status_col2.metric("Incidents", inc)
status_col3.metric("Dispatched", dispatches)
status_col4.metric("Station Responses", responses)

st.markdown("---")

# Create tabs for different views
tab_overview, tab_graph, tab_timeline, tab_negotiation = st.tabs([
    "📊 Overview", 
    "🔄 Communication Graph",
    "🧭 Rescue Flow Timeline",
    "⚖️ Negotiation Analysis"
])

with tab_overview:
    if st.session_state.message_queue:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📨 Agent Communication Timeline")
            recent_msgs = st.session_state.message_queue[-20:][::-1]
            
            for idx, msg in enumerate(recent_msgs):
                perf = msg.get('performative', 'unknown')
                content = msg.get('content', {})
                from_agent = msg.get('from', 'Unknown')
                to_agent = msg.get('to', 'Unknown')
                timestamp = msg.get('timestamp', '')
                
                # Agent emoji mapping
                agent_emojis = {
                    "FieldReporterAgent": "📡",
                    "CoordinatorAgent": "🎯",
                    "TriageAgent": "🏥",
                    "VetAgent": "⚕️",
                    "CommunicationAgent": "📢",
                    "BlackboardAgent": "📋",
                }
                
                # Performative emoji and color mapping
                perf_config = {
                    'advertise_incident': ('🚨', 'error', 'Incident Alert'),
                    'request_availability': ('�', 'info', 'Availability Check'),
                    'availability_response': ('✅', 'success', 'Station Available'),
                    'dispatch_order': ('🚀', 'warning', 'Unit Dispatched'),
                    'dispatch_acknowledged': ('👍', 'success', 'En Route'),
                    'request_treatment': ('💉', 'info', 'Treatment Request'),
                    'inform': ('ℹ️', 'info', 'Information'),
                    'log': ('📝', 'secondary', 'Log Entry'),
                }
                
                perf_emoji, perf_color, perf_label = perf_config.get(perf, ('📤', 'secondary', perf.replace('_', ' ').title()))
                
                # Extract meaningful information based on message type
                if perf == 'advertise_incident':
                    incident = content.get('incident', {})
                    gps = incident.get('gps', {})
                    species = incident.get('species', 'unknown')
                    severity = incident.get('injury_severity', 'unknown')
                    location = get_location_name(gps.get('lat', 0), gps.get('lon', 0))
                    
                    with st.expander(f"{perf_emoji} **{perf_label}** | {from_agent.replace('Agent', '')} → {to_agent.replace('Agent', '')}", expanded=(idx < 3)):
                        st.markdown(f"**🐾 Species:** {species}")
                        st.markdown(f"**⚠️ Severity:** `{severity.upper()}`")
                        st.markdown(f"**📍 Location:** {location}")
                        st.markdown(f"**🗺️ Coordinates:** {gps.get('lat', 0):.6f}, {gps.get('lon', 0):.6f}")
                        if incident.get('description'):
                            st.markdown(f"**📝 Description:** {incident.get('description')}")
                        st.caption(f"🕐 {timestamp[:19] if len(timestamp) > 19 else timestamp}")
                
                elif perf == 'request_availability':
                    incident = content.get('incident', {})
                    gps = incident.get('gps', {})
                    location = get_location_name(gps.get('lat', 0), gps.get('lon', 0))
                    with st.expander(f"{perf_emoji} **{perf_label}** | {from_agent.replace('Agent', '')} → All Stations"):
                        st.markdown(f"**📋 Incident ID:** `{incident.get('id', 'N/A')}`")
                        st.markdown(f"**🐾 Species:** {incident.get('species', 'unknown')}")
                        st.markdown(f"**📍 Location:** {location}")
                        st.markdown("**💭 Coordinator Thinking:** *Querying all Yala ranger stations for availability and calculating response times...*")
                        st.caption(f"🕐 {timestamp[:19] if len(timestamp) > 19 else timestamp}")
                
                elif perf == 'availability_response':
                    response = content.get('response', {})
                    with st.expander(f"{perf_emoji} **{perf_label}** | {from_agent} → {to_agent.replace('Agent', '')}"):
                        st.markdown(f"**� Station:** {response.get('station_name', 'unknown')}")
                        st.markdown(f"**� Distance:** {response.get('distance_km', 0):.2f} km")
                        st.markdown(f"**⏱️ ETA:** {response.get('eta_minutes', 0):.1f} minutes")
                        st.markdown(f"**� Vehicle:** {response.get('vehicle', 'N/A')}")
                        st.markdown(f"**� Terrain:** {response.get('terrain', 'unknown')}")
                        st.markdown(f"**� Staff:** {response.get('staff_available', 0)} rangers")
                        st.markdown(f"**🎒 Equipment:** {', '.join(response.get('equipment', []))}")
                        available = "✅ Available" if response.get('available') else "⏸️ Busy"
                        capable = "✅ Capable" if response.get('capable') else "❌ Not equipped"
                        st.markdown(f"**Status:** {available} | {capable}")
                        st.markdown(f"**💭 Station Assessment:** *{response.get('reasoning', 'N/A')}*")
                        st.caption(f"🕐 {timestamp[:19] if len(timestamp) > 19 else timestamp}")
                
                elif perf == 'dispatch_order':
                    with st.expander(f"{perf_emoji} **{perf_label}** | {from_agent.replace('Agent', '')} → {content.get('station_name', 'N/A')}", expanded=True):
                        st.markdown(f"**🚨 DISPATCH CONFIRMED**")
                        st.markdown(f"**� Station:** {content.get('station_name', 'unknown')}")
                        st.markdown(f"**� Distance:** {content.get('distance_km', 0):.2f} km")
                        st.markdown(f"**⏱️ ETA:** {content.get('eta_minutes', 0):.1f} minutes")
                        st.markdown(f"**� Vehicle Deployed:** {content.get('vehicle', 'N/A')}")
                        st.markdown(f"**🌲 Terrain Type:** {content.get('terrain', 'unknown')}")
                        st.markdown(f"**💭 Dispatch Reasoning:** *{content.get('reasoning', 'Nearest available station selected')}*")
                        
                        # Show all evaluated options for transparency
                        if 'all_options' in content and len(content['all_options']) > 1:
                            st.markdown("---")
                            st.markdown("**📊 All Station Options Evaluated**")
                            options_df = pd.DataFrame([
                                {
                                    "Station": opt.get('station_name', 'N/A'),
                                    "Distance (km)": opt.get('distance_km', 0),
                                    "ETA (min)": opt.get('eta_minutes', 0),
                                    "Available": "✅" if opt.get('available') else "❌",
                                    "Capable": "✅" if opt.get('capable') else "❌"
                                }
                                for opt in content['all_options']
                            ])
                            st.dataframe(options_df, use_container_width=True)
                        st.caption(f"🕐 {timestamp[:19] if len(timestamp) > 19 else timestamp}")
                
                elif perf == 'dispatch_acknowledged':
                    with st.expander(f"{perf_emoji} **{perf_label}** | {from_agent} → {to_agent.replace('Agent', '')}"):
                        st.markdown(f"**🏠 Station:** {content.get('station_name', 'unknown')}")
                        st.markdown(f"**✅ Status:** En route to incident")
                        st.markdown(f"**💬 Message:** *{content.get('message', 'Team deployed')}*")
                        st.caption(f"🕐 {timestamp[:19] if len(timestamp) > 19 else timestamp}")
                
                elif perf == 'request_treatment':
                    with st.expander(f"{perf_emoji} **{perf_label}** | {from_agent.replace('Agent', '')} → {to_agent.replace('Agent', '')}"):
                        st.markdown(f"**🐾 Species:** {content.get('species', 'unknown')}")
                        st.markdown(f"**⚠️ Injury Severity:** `{content.get('injury_severity', 'unknown').upper()}`")
                        st.markdown(f"**📍 Location:** {content.get('location', 'unknown')}")
                        if content.get('eta_minutes'):
                            st.markdown(f"**⏱️ Responder ETA:** {content.get('eta_minutes')} minutes")
                        if content.get('triage'):
                            triage = content.get('triage', {})
                            st.markdown(f"**🏥 Triage Priority:** {triage.get('priority', 'N/A')}")
                            st.markdown(f"**🩺 Recommended Action:** {triage.get('recommended_action', 'N/A')}")
                        st.markdown(f"**💭 System Thinking:** *Requesting veterinary expertise to determine optimal treatment protocol...*")
                        st.caption(f"🕐 {timestamp[:19] if len(timestamp) > 19 else timestamp}")
                
                elif perf == 'inform':
                    # Check if this is a triage summary or vet response
                    if 'triage' in content:
                        triage = content.get('triage', {})
                        with st.expander(f"🏥 **Triage Assessment** | {from_agent.replace('Agent', '')} → {to_agent.replace('Agent', '')}"):
                            st.markdown(f"**🎯 Priority:** `{triage.get('priority', 'N/A').upper()}`")
                            st.markdown(f"**⏱️ Response Time:** {triage.get('recommended_response_time', 'N/A')}")
                            st.markdown(f"**🩺 Recommended Action:** {triage.get('recommended_action', 'N/A')}")
                            if triage.get('severity_score'):
                                st.markdown(f"**📊 Severity Score:** {triage.get('severity_score')}/10")
                            st.markdown(f"**💭 Triage Thinking:** *Assessed injury severity, species vulnerability, and environmental factors to prioritize response...*")
                            st.caption(f"🕐 {timestamp[:19] if len(timestamp) > 19 else timestamp}")
                    
                    elif 'treatment' in content or 'vet_response' in content:
                        treatment = content.get('treatment', content.get('vet_response', {}))
                        with st.expander(f"⚕️ **Veterinary Decision** | {from_agent.replace('Agent', '')} → {to_agent.replace('Agent', '')}"):
                            st.markdown(f"**💊 Treatment Plan:** {treatment.get('treatment_plan', 'N/A')}")
                            st.markdown(f"**🏥 Facility Needed:** {treatment.get('facility_needed', 'N/A')}")
                            if treatment.get('medications'):
                                st.markdown(f"**� Medications:** {', '.join(treatment.get('medications', []))}")
                            if treatment.get('prognosis'):
                                st.markdown(f"**📈 Prognosis:** {treatment.get('prognosis', 'N/A')}")
                            st.markdown(f"**💭 Vet Thinking:** *Analyzed injury type, species physiology, and available resources to prescribe optimal treatment...*")
                            st.caption(f"🕐 {timestamp[:19] if len(timestamp) > 19 else timestamp}")
                    
                    else:
                        # Generic inform message
                        with st.expander(f"{perf_emoji} **{perf_label}** | {from_agent.replace('Agent', '')} → {to_agent.replace('Agent', '')}"):
                            st.json(content, expanded=False)
                            st.caption(f"🕐 {timestamp[:19] if len(timestamp) > 19 else timestamp}")
                
                else:
                    # Generic message display
                    with st.expander(f"{perf_emoji} **{perf_label}** | {from_agent.replace('Agent', '')} → {to_agent.replace('Agent', '')}"):
                        if content:
                            st.json(content, expanded=False)
                        st.caption(f"🕐 {timestamp[:19] if len(timestamp) > 19 else timestamp}")
        
        with col2:
            st.subheader("📍 Incident Locations")
            # Extract incident coordinates
            coords = []
            for m in st.session_state.message_queue:
                if m.get("performative") == "advertise_incident":
                    inc = m.get("content", {}).get("incident", {})
                    gps = inc.get("gps", {})
                    lat, lon = gps.get("lat"), gps.get("lon")
                    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                        coords.append({
                            "Species": inc.get("species", "unknown"),
                            "Lat": f"{lat:.6f}",
                            "Lon": f"{lon:.6f}",
                            "Severity": inc.get("injury_severity", "unknown")
                        })
            
            if coords:
                st.dataframe(pd.DataFrame(coords[-10:][::-1]), use_container_width=True, height=400)
                
                # Show live Yala map with incident and dispatch routes
                st.markdown("---")
                st.subheader("🗺️ Live Yala Operations Map")
                
                # Create map centered on Yala
                live_map = folium.Map(
                    location=[YALA_BOUNDARY["center"]["lat"], YALA_BOUNDARY["center"]["lon"]],
                    zoom_start=12,
                    tiles="OpenStreetMap"
                )
                
                # Add Yala boundary
                folium.Rectangle(
                    bounds=[
                        [YALA_BOUNDARY["min_lat"], YALA_BOUNDARY["min_lon"]],
                        [YALA_BOUNDARY["max_lat"], YALA_BOUNDARY["max_lon"]]
                    ],
                    color="green",
                    fill=True,
                    fillColor="green",
                    fillOpacity=0.05,
                    tooltip="Yala National Park"
                ).add_to(live_map)
                
                # Add all ranger stations
                for station_name, station_data in RANGER_STATIONS.items():
                    folium.Marker(
                        location=[station_data["lat"], station_data["lon"]],
                        popup=f"<b>{station_name}</b><br>Vehicles: {', '.join(station_data['vehicles'])}",
                        tooltip=f"🏠 {station_name}",
                        icon=folium.Icon(color="green", icon="home", prefix="fa")
                    ).add_to(live_map)
                
                # Add wildlife hotspots
                for hotspot_name, hotspot_data in WILDLIFE_HOTSPOTS.items():
                    folium.Circle(
                        location=[hotspot_data["lat"], hotspot_data["lon"]],
                        radius=hotspot_data["radius_km"] * 1000,
                        color="orange",
                        fill=True,
                        fillOpacity=0.1,
                        tooltip=f"🐾 {hotspot_name}"
                    ).add_to(live_map)
                
                # Add incident markers
                for m in st.session_state.message_queue:
                    if m.get("performative") == "advertise_incident":
                        inc = m.get("content", {}).get("incident", {})
                        gps = inc.get("gps", {})
                        lat, lon = gps.get("lat"), gps.get("lon")
                        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                            folium.Marker(
                                location=[lat, lon],
                                popup=f"<b>Incident</b><br>Species: {inc.get('species', 'unknown')}<br>Severity: {inc.get('injury_severity', 'unknown')}",
                                tooltip=f"🚨 {inc.get('species', 'unknown')}",
                                icon=folium.Icon(color="red", icon="exclamation-triangle", prefix="fa")
                            ).add_to(live_map)
                
                # Add dispatch routes (lines from station to incident)
                dispatched_incidents = {}
                for m in st.session_state.message_queue:
                    if m.get("performative") == "dispatch_order":
                        content = m.get("content", {})
                        incident_id = content.get("incident_id")
                        station_name = content.get("station_name")
                        dispatched_incidents[incident_id] = station_name
                
                # Draw routes for dispatched incidents
                for incident_id, station_name in dispatched_incidents.items():
                    # Find incident location
                    incident_loc = None
                    for m in st.session_state.message_queue:
                        if m.get("performative") == "advertise_incident":
                            inc = m.get("content", {}).get("incident", {})
                            if inc.get("id") == incident_id:
                                gps = inc.get("gps", {})
                                incident_loc = [gps.get("lat"), gps.get("lon")]
                                break
                    
                    # Find station location
                    if incident_loc and station_name in RANGER_STATIONS:
                        station_data = RANGER_STATIONS[station_name]
                        station_loc = [station_data["lat"], station_data["lon"]]
                        
                        # Draw route line
                        folium.PolyLine(
                            locations=[station_loc, incident_loc],
                            color="blue",
                            weight=3,
                            opacity=0.7,
                            popup=f"<b>Dispatch Route</b><br>{station_name} → Incident",
                            tooltip=f"🚙 {station_name} en route"
                        ).add_to(live_map)
                        
                        # Add arrow marker at incident end
                        folium.CircleMarker(
                            location=incident_loc,
                            radius=8,
                            color="blue",
                            fill=True,
                            fillColor="blue",
                            fillOpacity=0.5,
                            tooltip=f"Target: {station_name} responding"
                        ).add_to(live_map)
                
                # Render the live map
                st_folium(live_map, width=700, height=500, key="live_operations_map")
            else:
                st.info("No incidents yet")
    else:
        st.info("No messages yet. Start the system and submit an incident to see agent communications.")

with tab_graph:
    st.subheader("🔄 Agent Communication Network")
    
    if st.session_state.message_queue:
        # Build communication graph
        G = nx.DiGraph()
        edge_counts = defaultdict(int)
        node_message_counts = defaultdict(int)
        
        for msg in st.session_state.message_queue:
            from_agent = msg.get("from", "Unknown")
            to_agent = msg.get("to", "Unknown")
            
            # Count messages per agent
            node_message_counts[from_agent] += 1
            node_message_counts[to_agent] += 1
            
            # Count edges (communications between agents)
            edge_key = (from_agent, to_agent)
            edge_counts[edge_key] += 1
            
            # Add to graph
            if not G.has_edge(from_agent, to_agent):
                G.add_edge(from_agent, to_agent, weight=0)
            G[from_agent][to_agent]['weight'] += 1
        
        # Initialize or update stable layout positions in session state
        if "graph_positions" not in st.session_state:
            st.session_state.graph_positions = {}
        
        # Calculate positions for new nodes only, keep existing positions stable
        existing_nodes = set(st.session_state.graph_positions.keys())
        new_nodes = set(G.nodes()) - existing_nodes
        
        if new_nodes or not st.session_state.graph_positions:
            # Use fixed seed for consistent layout + keep existing positions
            pos = nx.spring_layout(
                G, 
                k=2, 
                iterations=50, 
                seed=42,  # Fixed seed for reproducible layout
                pos=st.session_state.graph_positions if st.session_state.graph_positions else None,
                fixed=list(existing_nodes) if existing_nodes else None
            )
            st.session_state.graph_positions = pos
        else:
            pos = st.session_state.graph_positions
        
        # Create edge traces
        edge_traces = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            weight = G[edge[0]][edge[1]]['weight']
            
            edge_trace = go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(width=min(weight * 0.5, 10), color='#888'),
                hoverinfo='text',
                text=f"{edge[0]} → {edge[1]}: {weight} messages",
                showlegend=False
            )
            edge_traces.append(edge_trace)
        
        # Create node trace
        node_x = []
        node_y = []
        node_text = []
        node_sizes = []
        node_colors = []
        
        # Color mapping for different agent types
        color_map = {
            "FieldReporterAgent": "#FF6B6B",
            "CoordinatorAgent": "#4ECDC4",
            "TriageAgent": "#45B7D1",
            "VetAgent": "#96CEB4",
            "CommunicationAgent": "#FFEAA7",
            "BlackboardAgent": "#DFE6E9",
        }
        
        # Yala ranger stations get special color
        station_color = "#FFA07A"  # Coral color for ranger stations
        
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            
            msg_count = node_message_counts[node]
            node_sizes.append(max(20 + msg_count * 2, 30))  # Size based on message count
            node_text.append(f"{node}<br>Messages: {msg_count}")
            
            # Assign color based on agent type or station
            if node in RANGER_STATIONS:
                # This is a Yala ranger station
                node_colors.append(station_color)
            else:
                node_colors.append(color_map.get(node, "#B8B8B8"))
        
        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode='markers+text',
            text=[node.replace("Agent", "") for node in G.nodes()],
            textposition="top center",
            hovertext=node_text,
            hoverinfo='text',
            marker=dict(
                size=node_sizes,
                color=node_colors,
                line=dict(width=2, color='white')
            ),
            showlegend=False
        )
        
        # Create figure
        fig = go.Figure(data=edge_traces + [node_trace])
        fig.update_layout(
            title="Agent Communication Network (Node size = message count)",
            showlegend=False,
            hovermode='closest',
            margin=dict(b=0, l=0, r=0, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=600,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No messages yet. Start the system and submit an incident to see the communication graph.")

# -------------------------
# Rescue Flow Timeline Tab
# -------------------------
with tab_timeline:
    st.subheader("🧭 Rescue Flow Timeline")
    st.caption("Step-by-step coordination process for each incident")
    
    if st.session_state.message_queue:
        # Group messages by incident ID
        incident_groups = defaultdict(list)
        incident_metadata = {}  # Store incident details
        
        for msg in st.session_state.message_queue:
            content = msg.get("content", {})
            inc = content.get("incident", {})
            inc_id = inc.get("id")
            
            if not inc_id and msg.get("performative") in ["availability_response", "dispatch_order", "dispatch_acknowledged"]:
                # Extract incident_id from other message types
                inc_id = content.get("incident_id")
            
            if inc_id:
                incident_groups[inc_id].append(msg)
                
                # Store incident metadata
                if inc.get("species"):
                    gps = inc.get("gps", {})
                    incident_metadata[inc_id] = {
                        "species": inc.get("species", "unknown"),
                        "severity": inc.get("injury_severity", "unknown"),
                        "location": get_location_name(gps.get("lat", 0), gps.get("lon", 0))
                    }
        
        # Select incident to visualize
        inc_list = [i for i in sorted(incident_groups.keys(), reverse=True) if i]
        
        if inc_list:
            selected_inc = st.selectbox(
                "Select Incident to Trace", 
                inc_list, 
                format_func=lambda x: f"{x[:8]}... - {incident_metadata.get(x, {}).get('species', 'unknown')} ({incident_metadata.get(x, {}).get('severity', 'unknown')})"
            )
            
            if selected_inc in incident_metadata:
                meta = incident_metadata[selected_inc]
                col1, col2, col3 = st.columns(3)
                col1.metric("🐾 Species", meta["species"].title())
                col2.metric("⚠️ Severity", meta["severity"].upper())
                col3.metric("📍 Location", meta["location"])
            
            st.markdown("---")
            
            # Get and sort messages for this incident
            msgs = sorted(incident_groups[selected_inc], key=lambda m: m.get("timestamp", ""))
            
            # Create timeline visualization
            st.markdown("### 📊 Coordination Flow")
            
            # Define timeline stages
            stages = {
                "advertise_incident": {"label": "🚨 Incident Reported", "color": "#FF6B6B", "stage": 1},
                "request_availability": {"label": "📡 Availability Check", "color": "#4ECDC4", "stage": 2},
                "availability_response": {"label": "📞 Station Response", "color": "#45B7D1", "stage": 3},
                "dispatch_order": {"label": "🚀 Dispatch Decision", "color": "#FFA07A", "stage": 4},
                "dispatch_acknowledged": {"label": "✅ En Route", "color": "#96CEB4", "stage": 5},
                "triage_summary": {"label": "🏥 Triage Assessment", "color": "#A29BFE", "stage": 6},
                "request_treatment": {"label": "💉 Treatment Request", "color": "#FFEAA7", "stage": 7},
                "vet_response": {"label": "🩺 Treatment Plan", "color": "#DFE6E9", "stage": 7.5},  # Same stage as treatment request
                "broadcast": {"label": "📢 Public Alert", "color": "#74B9FF", "stage": 8}
            }
            
            # Check if communication broadcast happened (log from CommunicationAgent with communication data)
            has_communication = any(
                m.get("from") == "CommunicationAgent" and 
                m.get("performative") == "log" and 
                m.get("content", {}).get("communication") is not None 
                for m in msgs
            )
            
            # Create progress bar
            max_stage = max([stages.get(m.get("performative"), {}).get("stage", 0) for m in msgs])
            
            # If communication happened, treat it as stage 8 (broadcast)
            if has_communication:
                max_stage = max(max_stage, 8)
            
            # Calculate progress
            system_stopped = not st.session_state.system_running
            
            if max_stage >= 8:
                progress = 1.0  # Complete - all stages done
            elif system_stopped and max_stage >= 5:
                # If system stopped and at least dispatched, mark as complete
                progress = 1.0
            else:
                progress = min(max_stage / 8, 1.0)
            
            st.progress(progress, text=f"Rescue Progress: {int(progress * 100)}%")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Render timeline with visual flow
            for idx, msg in enumerate(msgs):
                ts = datetime.fromisoformat(msg.get("timestamp", "")).strftime("%H:%M:%S")
                sender = msg.get("from", "Unknown")
                receiver = msg.get("to", "Unknown")
                perf = msg.get("performative", "")
                content = msg.get("content", {})
                
                # Special handling for CommunicationAgent broadcast (sent as 'log')
                if sender == "CommunicationAgent" and perf == "log" and content.get("communication"):
                    stage_info = stages.get("broadcast", {"label": "📢 Public Alert", "color": "#74B9FF"})
                    comm_data = content.get("communication", {})
                    
                    col1, col2 = st.columns([1, 5])
                    with col1:
                        st.markdown(f"**⏰ {ts}**")
                    with col2:
                        with st.expander(f"{stage_info['label']} — *{sender.replace('Agent', '')} → Public*", expanded=False):
                            st.markdown(f"**Message:** {comm_data.get('message_text', 'N/A')}")
                            st.markdown(f"**Channels:** {', '.join(comm_data.get('channels', []))}")
                            if comm_data.get('explanation'):
                                st.markdown(f"**Explanation:** {comm_data.get('explanation')}")
                            with st.expander("📋 Raw Message Data"):
                                st.json(content)
                    
                    # Add connecting line
                    if idx < len(msgs) - 1:
                        st.markdown(f"<div style='border-left: 3px solid {stage_info['color']}; height: 30px; margin-left: 80px; opacity: 0.3;'></div>", unsafe_allow_html=True)
                    continue
                
                # Skip other log messages (they're just for blackboard tracking)
                if perf == "log":
                    continue
                
                stage_info = stages.get(perf, {"label": perf.replace("_", " ").title(), "color": "#B8B8B8"})
                
                # Create timeline entry with expander for details
                col1, col2 = st.columns([1, 5])
                
                with col1:
                    st.markdown(f"**⏰ {ts}**")
                
                with col2:
                    with st.expander(f"{stage_info['label']} — *{sender.replace('Agent', '')} → {receiver.replace('Agent', '')}*", expanded=False):
                        # Show key content based on message type
                        if perf == "advertise_incident":
                            inc = content.get("incident", {})
                            st.markdown(f"**Species:** {inc.get('species', 'unknown')}")
                            st.markdown(f"**Behavior:** {inc.get('observed_behavior', 'N/A')}")
                            st.markdown(f"**Priority:** {inc.get('priority', 'N/A')}")
                        
                        elif perf == "availability_response":
                            resp = content.get("response", {})
                            st.markdown(f"**Station:** {resp.get('station_name', 'N/A')}")
                            st.markdown(f"**Distance:** {resp.get('distance_km', 0):.2f} km")
                            st.markdown(f"**ETA:** {resp.get('eta_minutes', 0):.1f} minutes")
                            st.markdown(f"**Available:** {'✅ Yes' if resp.get('available') else '❌ No'}")
                        
                        elif perf == "dispatch_order":
                            st.markdown(f"**Station:** {content.get('station_name', 'N/A')}")
                            st.markdown(f"**Vehicle:** {content.get('vehicle', 'N/A')}")
                            st.markdown(f"**ETA:** {content.get('eta_minutes', 0):.1f} minutes")
                            st.markdown(f"**Reasoning:** {content.get('reasoning', 'N/A')}")
                        
                        elif perf == "triage_summary":
                            triage = content.get("triage", {})
                            st.markdown(f"**Recommended Action:** {triage.get('recommended_action', 'N/A')}")
                            st.markdown(f"**Urgency:** {triage.get('urgency_level', 'N/A')}")
                        
                        elif perf == "vet_response":
                            treatment = content.get("treatment", {})
                            st.markdown(f"**Treatment Plan:** {treatment.get('treatment_plan', 'N/A')}")
                            st.markdown(f"**Medications:** {', '.join(treatment.get('medications', []))}")
                            st.markdown(f"**Follow-up:** {treatment.get('follow_up_care', 'N/A')}")
                        
                        # Always show raw content in collapsed section
                        st.markdown("---")
                        st.markdown("**📋 Raw Message Data**")
                        st.json(content)
                
                # Add connecting line between messages
                if idx < len(msgs) - 1:
                    st.markdown(f"<div style='border-left: 3px solid {stage_info['color']}; height: 30px; margin-left: 80px; opacity: 0.3;'></div>", unsafe_allow_html=True)
            
            # Summary statistics
            st.markdown("---")
            st.subheader("📊 Incident Summary")
            
            incident_start = None
            dispatch_time = None
            
            for msg in msgs:
                ts = datetime.fromisoformat(msg.get("timestamp", ""))
                if msg.get("performative") == "advertise_incident" and not incident_start:
                    incident_start = ts
                elif msg.get("performative") == "dispatch_order" and not dispatch_time:
                    dispatch_time = ts
            
            col1, col2, col3, col4 = st.columns(4)
            
            if incident_start and dispatch_time:
                response_delay = (dispatch_time - incident_start).total_seconds()
                col1.metric("⏱️ Response Time", f"{response_delay:.1f}s")
            else:
                col1.metric("⏱️ Response Time", "In Progress...")
            
            col2.metric("📨 Messages Exchanged", len(msgs))
            col3.metric("🏠 Stations Contacted", len([m for m in msgs if m.get("performative") == "availability_response"]))
            col4.metric("📋 Current Stage", f"{max_stage}/8")
        
        else:
            st.info("🔍 No incidents tracked yet. Submit an incident to see the rescue coordination timeline.")
    
    else:
        st.info("🔍 No messages yet. Start the system and submit an incident to see the rescue flow timeline.")

# -------------------------
# Negotiation Analysis Tab
# -------------------------
with tab_negotiation:
    st.subheader("⚖️ Negotiation & Bid Analysis")
    st.caption("Compare all ranger station proposals and understand dispatch decisions")
    
    if st.session_state.message_queue:
        # Find dispatch decisions with bid comparisons
        negotiations = []
        for msg in st.session_state.message_queue:
            if msg.get("performative") == "dispatch_order":
                content = msg.get("content", {})
                if "all_options" in content and len(content["all_options"]) > 1:
                    negotiations.append({
                        "timestamp": msg.get("timestamp"),
                        "incident_id": content.get("incident_id"),
                        "winner": content.get("station_name"),
                        "options": content["all_options"],
                        "reasoning": content.get("reasoning", "N/A"),
                        "eta": content.get("eta_minutes", 0),
                        "distance": content.get("distance_km", 0)
                    })
        
        if negotiations:
            # Select negotiation to analyze
            selected_neg_idx = st.selectbox(
                "Select Dispatch Decision to Analyze",
                range(len(negotiations)),
                format_func=lambda x: f"Dispatch {x+1}: {negotiations[x]['winner']} selected — {negotiations[x]['timestamp'][:19]}"
            )
            
            neg = negotiations[selected_neg_idx]
            
            # Winner announcement
            st.markdown("---")
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"### 📍 Assigned to: **{neg['winner']}**")
            with col2:
                st.metric("🚗 ETA", f"{neg['eta']:.1f} min")
            with col3:
                st.metric("📏 Distance", f"{neg['distance']:.2f} km")
            
            st.info(f"**💭 Coordinator's Reasoning:** {neg['reasoning']}")
            
            # All station proposals comparison
            st.markdown("---")
            st.subheader("📊 All Station Proposals")
            
            # Create comparison table
            options_data = []
            for opt in neg["options"]:
                options_data.append({
                    "🏠 Station": opt.get("station_name", "N/A"),
                    "📏 Distance": f"{opt.get('distance_km', 0):.2f} km",
                    "⏱️ ETA": f"{opt.get('eta_minutes', 0):.1f} min",
                    "✅ Available": "✅ Yes" if opt.get("available") else "❌ No",
                    "🔧 Capable": "✅ Yes" if opt.get("capable") else "❌ No",
                    "🌳 Terrain": opt.get("terrain", "unknown"),
                    "🚙 Vehicle": opt.get("vehicle", "N/A"),
                    "👥 Staff": opt.get("staff_available", 0)
                })
            
            df = pd.DataFrame(options_data)
            
            # Highlight winner row
            def highlight_winner(row):
                if row["🏠 Station"] == neg["winner"]:
                    return ['background-color: #96CEB4; font-weight: bold'] * len(row)
                else:
                    return [''] * len(row)
            
            styled_df = df.style.apply(highlight_winner, axis=1)
            st.dataframe(styled_df, use_container_width=True, height=250)
            
            # Visual comparison charts
            st.markdown("---")
            st.subheader("📈 Visual Comparison")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # ETA comparison bar chart
                fig_eta = go.Figure(data=[
                    go.Bar(
                        x=[opt["🏠 Station"] for opt in options_data],
                        y=[float(opt["⏱️ ETA"].split()[0]) for opt in options_data],
                        marker_color=['#96CEB4' if opt["🏠 Station"] == neg["winner"] else '#DFE6E9' for opt in options_data],
                        text=[opt["⏱️ ETA"] for opt in options_data],
                        textposition='auto',
                        hovertemplate='<b>%{x}</b><br>ETA: %{text}<extra></extra>'
                    )
                ])
                fig_eta.update_layout(
                    title="⏱️ Estimated Time of Arrival (Lower is Better)",
                    xaxis_title="Station",
                    yaxis_title="Minutes",
                    height=350,
                    showlegend=False
                )
                st.plotly_chart(fig_eta, width='stretch')
            
            with col2:
                # Distance comparison bar chart
                fig_dist = go.Figure(data=[
                    go.Bar(
                        x=[opt["🏠 Station"] for opt in options_data],
                        y=[float(opt["📏 Distance"].split()[0]) for opt in options_data],
                        marker_color=['#96CEB4' if opt["🏠 Station"] == neg["winner"] else '#DFE6E9' for opt in options_data],
                        text=[opt["📏 Distance"] for opt in options_data],
                        textposition='auto',
                        hovertemplate='<b>%{x}</b><br>Distance: %{text}<extra></extra>'
                    )
                ])
                fig_dist.update_layout(
                    title="📏 Distance to Incident (Lower is Better)",
                    xaxis_title="Station",
                    yaxis_title="Kilometers",
                    height=350,
                    showlegend=False
                )
                st.plotly_chart(fig_dist, width='stretch')
            
            # Decision factors breakdown
            st.markdown("---")
            st.subheader("🧠 Decision Factors Analysis")
            
            winner_data = next((opt for opt in neg["options"] if opt.get("station_name") == neg["winner"]), None)
            
            if winner_data:
                st.markdown("**Why was this station selected?**")
                
                factors = []
                
                # Compare winner against others
                other_stations = [opt for opt in neg["options"] if opt.get("station_name") != neg["winner"]]
                
                # Factor 1: Speed advantage
                winner_eta = winner_data.get("eta_minutes", 999)
                if other_stations:
                    fastest_other = min([opt.get("eta_minutes", 999) for opt in other_stations])
                    if winner_eta <= fastest_other:
                        time_saved = fastest_other - winner_eta
                        factors.append(f"✅ **Fastest Response:** {winner_eta:.1f} min (saves {time_saved:.1f} min over next best)")
                    
                    # Factor 2: Distance advantage
                    winner_dist = winner_data.get("distance_km", 999)
                    closest_other = min([opt.get("distance_km", 999) for opt in other_stations])
                    if winner_dist <= closest_other:
                        factors.append(f"✅ **Closest Station:** {winner_dist:.2f} km away")
                
                # Factor 3: Availability
                if winner_data.get("available"):
                    factors.append("✅ **Available:** Station ready to deploy immediately")
                
                # Factor 4: Capability
                if winner_data.get("capable"):
                    factors.append("✅ **Equipped:** Has necessary equipment for this incident type")
                
                # Factor 5: Terrain suitability
                terrain = winner_data.get("terrain", "unknown")
                vehicle = winner_data.get("vehicle", "N/A")
                factors.append(f"✅ **Terrain Match:** {terrain} terrain — deploying {vehicle}")
                
                # Factor 6: Staff availability
                staff = winner_data.get("staff_available", 0)
                factors.append(f"✅ **Personnel Ready:** {staff} trained staff members available")
                
                # Display factors
                for idx, factor in enumerate(factors, 1):
                    st.markdown(f"{idx}. {factor}")
                
                # Show stations that were rejected
                st.markdown("---")
                st.markdown("**Why were other stations not selected?**")
                
                for opt in other_stations:
                    station_name = opt.get("station_name", "Unknown")
                    reasons = []
                    
                    if not opt.get("available"):
                        reasons.append("❌ **Not Available** (currently busy)")
                    
                    if not opt.get("capable"):
                        reasons.append("❌ **Not Equipped** (lacks necessary equipment)")
                    
                    opt_eta = opt.get("eta_minutes", 0)
                    if opt_eta > winner_eta:
                        diff = opt_eta - winner_eta
                        reasons.append(f"⚠️ **Slower Response** ({diff:.1f} min slower)")
                    
                    if reasons:
                        with st.expander(f"🏠 {station_name} — Not Selected"):
                            for reason in reasons:
                                st.markdown(f"• {reason}")
                            st.markdown(f"• Distance: {opt.get('distance_km', 0):.2f} km")
                            st.markdown(f"• ETA: {opt_eta:.1f} min")
            
            else:
                st.warning("Winner data not found in options.")
        
        else:
            st.info("🔍 No negotiations with multiple bids yet. Once multiple ranger stations respond to an incident, their proposals will appear here for comparison.")
    
    else:
        st.info("🔍 No messages yet. Start the system and submit an incident to see negotiation analysis.")

# Auto-refresh while running
if st.session_state.system_running:
    # Drain tap queue into UI session messages
    try:
        while not st.session_state.tap_queue.empty():
            st.session_state.message_queue.append(st.session_state.tap_queue.get_nowait())
    except Exception:
        pass
    time.sleep(1)
    st.rerun()
