"""
BTP-Niyantran Backend v2.0
Bengaluru Traffic Police Niyantran
FastAPI + YOLOv8 + OpenCV Traffic Intelligence Engine

New in v2.0:
  - Phase 1: Dwell-timer state machine & hazard-light exception heuristic
  - Phase 1: Shapely Geofence polygons
  - Phase 3: ParkIQ analytics endpoints (Clusters, BPR, Deterrence Decay, Heatmap)
  - Alert log with auto E-Challan numbers  → GET /api/alert-log
  - 30-day carbon history array            → GET /api/carbon-log
  - Live-configurable settings             → POST /api/settings
  - System stats (FPS, uptime, frames)     → GET /api/system-stats
  - Priority Corridor Mode signal override → via POST /api/settings
  - Hot-reload: ZONE + confidence from settings (no restart needed)
"""

import cv2
import time
import uuid
import threading
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from collections import deque

import torch
_original_load = torch.load
def _patched_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_load(*args, **kwargs)
torch.load = _patched_load

from ultralytics import YOLO
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import math
import random
import json

try:
    from shapely.geometry import Point, Polygon
except ImportError:
    class Point:
        def __init__(self, x, y):
            self.x, self.y = x, y
    class Polygon:
        def __init__(self, coords):
            self.coords = coords
            self.contour = np.array(coords, dtype=np.int32)
        def contains(self, point):
            return cv2.pointPolygonTest(self.contour, (point.x, point.y), False) >= 0

# ─────────────────────────────────────────────
# App Initialization
# ─────────────────────────────────────────────
app = FastAPI(
    title="BTP-Niyantran API",
    description="Bengaluru Traffic Police AI-Powered Traffic Management System",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

VEHICLE_CLASSES   = [2, 3, 5, 7]           # car, motorcycle, bus, truck
VIDEO_PATH        = Path(__file__).parent / "traffic_feed.mp4"
MODEL_PATH        = "yolov8n.pt"
GEOFENCE_FILE     = Path(__file__).parent / "geofence_zones.json"   # persisted drawn zones
CARBON_PER_VEH_SEC = 0.0028                # kg CO2 per vehicle per idle-second saved
BASELINE_GREEN    = 60                     # legacy fixed signal (seconds)
CLASS_NAMES       = {2: "CAR", 3: "BIKE", 5: "BUS", 7: "TRUCK"}

# Bengaluru Zones
ZONE_NAMES        = {
    "silk_board":   "Silk Board Junction",
    "kr_market":    "KR Market",
    "mg_road":      "MG Road",
    "hebbal":       "Hebbal",
    "whitefield":   "Whitefield"
}

# Geofence Polygons for Demo (Phase 1)
# Coordinates on 640x480 frame
GEOFENCE_ZONES = {
    "Silk Board Junction": Polygon([(80, 120), (400, 120), (380, 360), (60, 360)]),
    "KR Market": Polygon([(50, 90), (350, 90), (330, 310), (30, 310)]),
    "MG Road": Polygon([(100, 100), (450, 100), (430, 380), (80, 380)]),
    # Recalibrated against real YOLOv8 detections on the actual demo video
    # (traffic.mp4, 624x352 native -> 640x480 after this app's resize) --
    # lands on the right-lane auto-rickshaw cluster + roadside stall,
    # matching the "right-side shoulder beyond the divider" zone used in
    # the original SMC-Niyantran build.
    "Right Side Shoulder": Polygon([(502, 34), (640, 34), (640, 436), (472, 436)])
}
# Phase 1: Dwell Timers
DWELL_GRACE_SECONDS = 120
STRICT_THRESHOLD_SECONDS = 180

# ─────────────────────────────────────────────
# Live-Configurable Settings
# ─────────────────────────────────────────────
settings = {
    # Rectangular fallback removed – zones are now polygon‑based only
    # YOLO confidence threshold
    "confidence":      0.35,
    # Priority Corridor Mode – overrides RL signal
    "yatra_mode":      False,
    "yatra_green_time": 45,     # seconds
    # Active junction label shown in HUD
    "active_junction": "Right Side Shoulder",
}
settings_lock = threading.Lock()

# ─────────────────────────────────────────────
# Shared Runtime State
# ─────────────────────────────────────────────
state = {
    "vehicle_count":      0,
    "encroachment_alert": False,
    "dynamic_green_time": 20,
    "carbon_saved_kg":    0.0,
    "frame":              None,     # Latest JPEG bytes
    "running":            False,
    "fps":                0.0,
    "frame_count":        0,
    "start_time":         None,
    "uptime_seconds":     0,
    "dwell_states":       [],       # Phase 1: list of dicts for UI
}
state_lock = threading.Lock()

# Dwell tracking dict: { vehicle_hash: { 'enter_time': float, 'last_seen': float, 'status': str, 'hazard': bool } }
dwell_timers = {}
dwell_lock = threading.Lock()

hazard_vehicles = set()

# ─────────────────────────────────────────────
# Alert Log
# ─────────────────────────────────────────────
alert_log   = deque(maxlen=100)
alert_lock  = threading.Lock()
_challan_counter = 0
_challan_lock    = threading.Lock()

def generate_challan_number() -> str:
    """Generate unique E-Challan ID: BTP-YYYYMMDD-XXXX"""
    global _challan_counter
    with _challan_lock:
        _challan_counter += 1
        date_str = datetime.now().strftime("%Y%m%d")
        return f"BTP-{date_str}-{_challan_counter:04d}"

def log_alert(zone: str, vehicle_count: int, status: str = "VIOLATION"):
    """Append an alert entry to the alert log."""
    entry = {
        "id":            str(uuid.uuid4())[:8],
        "challan_no":    generate_challan_number() if status == "VIOLATION" else None,
        "timestamp":     datetime.now().isoformat(),
        "timestamp_fmt": datetime.now().strftime("%d/%m/%Y, %I:%M:%S %p"),
        "zone":          zone,
        "status":        status,
        "vehicle_count": vehicle_count,
        "fine_inr":      500 if status == "VIOLATION" else 0,
        "details":       "Encroachment detected in No-Parking Zone" if status == "VIOLATION"
                         else "Zone cleared — no violations",
    }
    with alert_lock:
        alert_log.appendleft(entry)

# ─────────────────────────────────────────────
# Carbon History
# ─────────────────────────────────────────────
carbon_history = deque(maxlen=30)
carbon_lock    = threading.Lock()
_last_carbon_update = 0.0

parkiq_cache = {}

def _load_parkiq_data():
    data_dir = Path(__file__).parent / "parkiq_data"
    files = [
        "clusters.json",
        "congestion_scores.json",
        "deterrence_decay.json",
        "heatmap.json",
        "repeat_offender_stats.json"
    ]
    for f in files:
        path = data_dir / f
        if path.exists():
            with open(path, "r", encoding="utf-8") as file:
                parkiq_cache[f] = json.load(file)
        else:
            parkiq_cache[f] = {}

def _seed_carbon_history():
    np.random.seed(42)
    with carbon_lock:
        carbon_history.clear()
        for i in range(30):
            wait = int(80 * np.exp(-0.055 * i) + 25 + np.random.uniform(-3, 3))
            wait = max(25, min(85, wait))
            efficiency = (80 - wait) / 55
            carbon = round(4.2 * efficiency + np.random.uniform(0, 0.4), 2)
            carbon_history.append({
                "day":        f"Day {i + 1}",
                "wait_time":  wait,
                "carbon_kg":  carbon,
            })

# ─────────────────────────────────────────────
# Helper: RL Optimizer
# ─────────────────────────────────────────────

def compute_green_time(count: int) -> int:
    return min(120, max(20, count * 3))

def compute_carbon_saved(count: int, green_time: int) -> float:
    time_saved = max(0, BASELINE_GREEN - green_time)
    return round(count * time_saved * CARBON_PER_VEH_SEC, 4)

# ─────────────────────────────────────────────
# Helper: Frame Drawing
# ─────────────────────────────────────────────

def get_active_polygon() -> Polygon:
    """Return the polygon for the currently active junction."""
    with settings_lock:
        junction = settings["active_junction"]
    return GEOFENCE_ZONES.get(junction)

def _polygon_points(poly) -> list:
    """Convert a Polygon (real shapely or the no-shapely fallback) into a
    plain [{"x":.., "y":..}, ...] list -- same shape /api/geofence-zones
    already returns, so the saved file and the API stay in sync."""
    if hasattr(poly, "exterior"):
        coords = list(poly.exterior.coords)[:-1]   # drop shapely's closing duplicate point
    else:
        coords = poly.coords
    return [{"x": int(round(p[0])), "y": int(round(p[1]))} for p in coords]

def _save_geofence_zones():
    """Persist every zone in GEOFENCE_ZONES to disk so a freshly drawn
    polygon survives a server restart instead of reverting to the
    hardcoded defaults above."""
    try:
        data = {name: _polygon_points(poly) for name, poly in GEOFENCE_ZONES.items()}
        with open(GEOFENCE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[geofence] failed to save {GEOFENCE_FILE.name}: {e}")

def _load_geofence_zones():
    """Load any previously saved zones at startup, overriding the
    hardcoded defaults for whichever junction names were saved. Safe to
    call even if the file doesn't exist yet (first run)."""
    if not GEOFENCE_FILE.exists():
        return
    try:
        with open(GEOFENCE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for name, points in data.items():
            if len(points) >= 3:
                coords = [(p["x"], p["y"]) for p in points]
                GEOFENCE_ZONES[name] = Polygon(coords)
        print(f"[geofence] loaded {len(data)} saved zone(s) from {GEOFENCE_FILE.name}")
    except Exception as e:
        print(f"[geofence] failed to load {GEOFENCE_FILE.name}: {e}")

def is_in_zone(cx: int, cy: int, zone: tuple, junction_name: str) -> bool:
    if junction_name in GEOFENCE_ZONES:
        poly = GEOFENCE_ZONES[junction_name]
        return poly.contains(Point(cx, cy))
    
    return False

def draw_zone(frame: np.ndarray, zone: tuple, junction_name: str) -> np.ndarray:
    overlay = frame.copy()
    if junction_name in GEOFENCE_ZONES:
        poly = GEOFENCE_ZONES[junction_name]
        if hasattr(poly, 'exterior'):
            coords = np.array(poly.exterior.coords, dtype=np.int32)
        else:
            coords = poly.contour
        cv2.fillPoly(overlay, [coords], (0, 100, 255))
        cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)
        cv2.polylines(frame, [coords], True, (0, 200, 255), 3)
        label_x, label_y = coords[0]
        label_y = label_y + 18
    else:
        # No polygon defined for this junction; skip drawing
        label_x, label_y = 0, 0

    cv2.putText(frame, "NO PARKING ZONE",
                (label_x + 6, label_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 230, 255), 1, cv2.LINE_AA)
    return frame

def draw_hud(frame: np.ndarray, count: int, green_time: int,
             carbon: float, alert: bool, yatra: bool, fps: float, junction_name: str) -> np.ndarray:
    h, w = frame.shape[:2]

    bar_color = (20, 100, 200) if yatra else (10, 10, 30)
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 52), bar_color, -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    title = "PRIORITY CORRIDOR ACTIVE" if yatra else "BTP-NIYANTRAN"
    title_color = (0, 200, 255) if yatra else (0, 220, 180)
    cv2.putText(frame, f"{title} | {junction_name.upper()}",
                (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.52, title_color, 1, cv2.LINE_AA)

    stats = f"Vehicles: {count}  |  Green: {green_time}s  |  CO2 Saved: {carbon}kg  |  FPS: {fps:.1f}"
    cv2.putText(frame, stats,
                (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (200, 200, 200), 1, cv2.LINE_AA)

    if yatra:
        cv2.rectangle(frame, (w - 150, 5), (w - 5, 30), (0, 140, 255), -1)
        cv2.putText(frame, "PRIORITY CORRIDOR",
                    (w - 146, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1, cv2.LINE_AA)

    if alert:
        tick = int(time.time() * 2) % 2
        if tick == 0:
            cv2.rectangle(frame, (0, h - 32), (w, h), (0, 0, 180), -1)
            cv2.putText(frame, "!! ENCROACHMENT ALERT – E-CHALLAN DRAFTED !!",
                        (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)

    return frame

# ─────────────────────────────────────────────
# Synthetic Frame Generator
# ─────────────────────────────────────────────

def generate_synthetic_frame(frame_idx: int) -> np.ndarray:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(frame, (0, 0),   (640, 480), (22, 22, 32), -1)
    cv2.rectangle(frame, (80, 90), (560, 420), (42, 42, 52), -1)
    for x in range(160, 520, 55):
        cv2.line(frame, (x, 255), (x + 28, 255), (180, 180, 80), 2)
    np.random.seed(frame_idx % 400)
    n = np.random.randint(4, 9)
    colors = [(80, 180, 80), (80, 120, 200), (200, 120, 60), (160, 80, 200)]
    for i in range(n):
        vx = (frame_idx * (4 + i * 2) + i * 85) % 570
        vy = 110 + (i % 5) * 55
        vw, vh = (70 if i % 3 == 0 else 55), (34 if i % 3 == 0 else 28)
        c = colors[i % len(colors)]
        cv2.rectangle(frame, (vx, vy), (vx + vw, vy + vh), c, -1)
        cv2.rectangle(frame, (vx, vy), (vx + vw, vy + vh), (255, 255, 255), 1)
    return frame

# ─────────────────────────────────────────────
# Background Video Processing Thread
# ─────────────────────────────────────────────

_frame_history = deque(maxlen=5)

def detect_hazard_flicker(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> bool:
    if len(_frame_history) < 5:
        return False
    ty1 = y2 - max(10, int((y2 - y1) * 0.25))
    if ty1 < y1: ty1 = y1
    
    if ty1 >= y2 or x1 >= x2:
        return False
        
    current_roi = frame[ty1:y2, x1:x2]
    if current_roi.size == 0:
        return False
        
    current_bright = np.mean(cv2.cvtColor(current_roi, cv2.COLOR_BGR2GRAY))
    
    past_brights = []
    for hist_frame in _frame_history:
        h_roi = hist_frame[ty1:y2, x1:x2]
        if h_roi.size > 0:
            past_brights.append(np.mean(cv2.cvtColor(h_roi, cv2.COLOR_BGR2GRAY)))
            
    if not past_brights:
        return False
        
    avg_past = np.mean(past_brights)
    
    if avg_past > 0 and abs(current_bright - avg_past) / avg_past > 0.20:
        return True
    return False

def video_processing_loop():
    global _last_carbon_update, _frame_history

    model = YOLO(MODEL_PATH)

    use_synthetic = not VIDEO_PATH.exists()
    cap = None
    if not use_synthetic:
        cap = cv2.VideoCapture(str(VIDEO_PATH))
        if not cap.isOpened():
            use_synthetic = True

    with state_lock:
        state["running"]    = True
        state["start_time"] = time.time()

    accumulated_carbon = 0.0
    frame_idx          = 0
    fps_counter        = 0
    fps_timer          = time.time()
    _prev_alert        = False

    while True:
        if use_synthetic:
            frame = generate_synthetic_frame(frame_idx)
            frame_idx += 1
            time.sleep(0.05)
        else:
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            frame = cv2.resize(frame, (640, 480))
            
        _frame_history.append(frame.copy())

        with settings_lock:
            conf_thresh = settings["confidence"]
            yatra_mode  = settings["yatra_mode"]
            yatra_gt    = settings["yatra_green_time"]
            junction    = settings["active_junction"]
        zone = get_active_polygon()

        results = model(frame, classes=VEHICLE_CLASSES,
                        conf=conf_thresh, verbose=False)

        vehicle_count = 0
        encroachment  = False
        
        current_time = time.time()
        seen_hashes = set()
        current_dwell_states = []

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                cx      = (x1 + x2) // 2
                cy      = (y1 + y2) // 2
                cls_id  = int(box.cls[0])
                conf_v  = float(box.conf[0])
                in_zone = is_in_zone(cx, cy, zone, junction)

                if in_zone:
                    v_hash = f"{cx//20}_{cy//20}"
                    seen_hashes.add(v_hash)
                    
                    with dwell_lock:
                        if v_hash not in dwell_timers:
                            dwell_timers[v_hash] = {
                                'enter_time': current_time,
                                'last_seen': current_time,
                                'status': 'ENTERED_ZONE',
                                'hazard': False
                            }
                        
                        timer_info = dwell_timers[v_hash]
                        timer_info['last_seen'] = current_time
                        
                        if not timer_info['hazard'] and detect_hazard_flicker(frame, x1, y1, x2, y2):
                            timer_info['hazard'] = True
                            
                        dwell_time = current_time - timer_info['enter_time']
                        
                        if timer_info['hazard']:
                            timer_info['status'] = 'EXEMPT (HAZARD)'
                        elif dwell_time > STRICT_THRESHOLD_SECONDS:
                            timer_info['status'] = 'VIOLATION'
                        elif dwell_time > DWELL_GRACE_SECONDS:
                            timer_info['status'] = 'WATCH'
                        else:
                            timer_info['status'] = 'ENTERED_ZONE'
                            
                        if timer_info['status'] == 'VIOLATION':
                            encroachment = True
                            color = (0, 0, 255)
                        elif timer_info['status'] == 'WATCH':
                            color = (0, 165, 255)
                        elif timer_info['status'] == 'EXEMPT (HAZARD)':
                            color = (255, 255, 0)
                        else:
                            color = (0, 255, 255)
                            
                        current_dwell_states.append({
                            'id': v_hash,
                            'seconds': int(dwell_time),
                            'status': timer_info['status']
                        })

                else:
                    color = (0, 255, 100)

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.circle(frame, (cx, cy), 4, color, -1)
                lbl = f"{CLASS_NAMES.get(cls_id, 'VEH')} {conf_v:.2f}"
                cv2.putText(frame, lbl, (x1, y1 - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)
                vehicle_count += 1
                
        with dwell_lock:
            to_remove = [k for k, v in dwell_timers.items() if current_time - v['last_seen'] > 5.0]
            for k in to_remove:
                del dwell_timers[k]

        if encroachment and not _prev_alert:
            log_alert(junction, vehicle_count, status="VIOLATION")
        elif not encroachment and _prev_alert:
            log_alert(junction, vehicle_count, status="CLEAR")
        _prev_alert = encroachment

        if yatra_mode:
            green_time = yatra_gt
        else:
            green_time = compute_green_time(vehicle_count)

        carbon_delta    = compute_carbon_saved(vehicle_count, green_time)
        accumulated_carbon = round(accumulated_carbon + carbon_delta * 0.001, 4)

        now = time.time()
        if now - _last_carbon_update >= 60:
            _last_carbon_update = now
            day_label = f"Day {len(carbon_history) + 1}"
            rl_wait   = max(25, green_time - vehicle_count)
            with carbon_lock:
                carbon_history.append({
                    "day":       day_label,
                    "wait_time": rl_wait,
                    "carbon_kg": round(accumulated_carbon, 3),
                })

        fps_counter += 1
        if time.time() - fps_timer >= 1.0:
            current_fps = fps_counter / (time.time() - fps_timer)
            fps_counter = 0
            fps_timer   = time.time()
            with state_lock:
                state["fps"] = round(current_fps, 1)

        frame = draw_zone(frame, zone, junction)
        with state_lock:
            current_fps = state["fps"]
        frame = draw_hud(frame, vehicle_count, green_time,
                         accumulated_carbon, encroachment, yatra_mode, current_fps, junction)

        _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])

        with state_lock:
            state["vehicle_count"]      = vehicle_count
            state["encroachment_alert"] = encroachment
            state["dynamic_green_time"] = green_time
            state["carbon_saved_kg"]    = accumulated_carbon
            state["frame"]              = jpeg.tobytes()
            state["frame_count"]       += 1
            state["uptime_seconds"]     = int(time.time() - state["start_time"])
            state["dwell_states"]       = current_dwell_states

    if cap:
        cap.release()

# ─────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    _seed_carbon_history()
    _load_parkiq_data()
    _load_geofence_zones()
    thread = threading.Thread(target=video_processing_loop, daemon=True)
    thread.start()

# ─────────────────────────────────────────────
# MJPEG Frame Generator
# ─────────────────────────────────────────────

def frame_generator():
    while True:
        with state_lock:
            frame_bytes = state.get("frame")
        if frame_bytes is None:
            time.sleep(0.05)
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes +
            b"\r\n"
        )
        time.sleep(0.04)

# ─────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────

@app.get("/", summary="Health Check")
def root():
    return {"status": "BTP-Niyantran API v2.0 running", "version": "2.0.0"}


@app.get("/api/video-feed", summary="MJPEG Live CCTV Stream")
def video_feed():
    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/traffic-data", summary="Real-Time Traffic Metrics")
def traffic_data():
    with state_lock:
        sv = dict(state)
    with settings_lock:
        ym = settings["yatra_mode"]
        ygt = settings["yatra_green_time"]
    return JSONResponse({
        "vehicle_count":      sv["vehicle_count"],
        "encroachment_alert": sv["encroachment_alert"],
        "dynamic_green_time": sv["dynamic_green_time"],
        "carbon_saved_kg":    sv["carbon_saved_kg"],
        "yatra_mode":         ym,
        "yatra_green_time":   ygt,
        "fps":                sv["fps"],
        "backend_status":     "live" if sv["running"] else "initializing",
        "dwell_states":       sv.get("dwell_states", [])
    })


@app.get("/api/alert-log", summary="Encroachment Alert History")
def get_alert_log():
    with alert_lock:
        logs = list(alert_log)
    return JSONResponse({"alerts": logs, "total": len(logs)})


@app.get("/api/carbon-log", summary="30-Day Carbon & RL History")
def get_carbon_log():
    with carbon_lock:
        history = list(carbon_history)
    return JSONResponse({"history": history, "days": len(history)})


@app.get("/api/system-stats", summary="System Performance Stats")
def system_stats():
    with state_lock:
        return JSONResponse({
            "fps":             state["fps"],
            "frame_count":     state["frame_count"],
            "uptime_seconds":  state["uptime_seconds"],
            "resolution":      "640x480",
            "model":           "YOLOv8n",
            "vehicle_classes": ["car", "motorcycle", "bus", "truck"],
        })


@app.post("/api/settings", summary="Update Live Settings")
def update_settings(body: dict = Body(...)):
    allowed = {
        "confidence",
        "yatra_mode",
        "yatra_green_time",
        "active_junction",
        "geofence_polygon"
    }
    updated = {}
    with settings_lock:
        for key, val in body.items():
            if key in allowed:
                settings[key] = val
                updated[key]  = val
                
        # Update polygon logic
        if "geofence_polygon" in body and "active_junction" in settings:
            poly_points = body["geofence_polygon"]
            junction = settings["active_junction"]
            if len(poly_points) >= 3:
                coords = [(int(p["x"]), int(p["y"])) for p in poly_points]
                GEOFENCE_ZONES[junction] = Polygon(coords)
                _save_geofence_zones()
                
    return JSONResponse({
        "status":  "ok",
        "updated": updated,
        "current": dict(settings),
    })


@app.get("/api/settings", summary="Get Current Settings")
def get_settings():
    with settings_lock:
        return JSONResponse(dict(settings))

# ─────────────────────────────────────────────
# Phase 1 & 3: New Endpoints
# ─────────────────────────────────────────────

@app.get("/api/geofence-zones", summary="Get Geofence Polygons")
def get_geofence_zones():
    zones_json = {}
    for name, poly in GEOFENCE_ZONES.items():
        if hasattr(poly, 'exterior'):
            coords = list(poly.exterior.coords)
        else:
            coords = poly.coords
        zones_json[name] = [{"x": p[0], "y": p[1]} for p in coords]
    return JSONResponse({"zones": zones_json})


@app.get("/api/parkiq/clusters", summary="Phase 3: HDBSCAN Clusters")
def get_parkiq_clusters():
    return JSONResponse(parkiq_cache.get("clusters.json", {}))


@app.get("/api/parkiq/congestion-scores", summary="Phase 3: BPR Congestion Impact Score")
def get_parkiq_congestion_scores():
    return JSONResponse(parkiq_cache.get("congestion_scores.json", {}))


@app.get("/api/parkiq/deterrence-decay", summary="Phase 3: Deterrence Decay Curve")
def get_parkiq_deterrence_decay():
    return JSONResponse(parkiq_cache.get("deterrence_decay.json", {}))


@app.get("/api/parkiq/heatmap", summary="Phase 3: Heatmap Matrix")
def get_parkiq_heatmap():
    return JSONResponse(parkiq_cache.get("heatmap.json", {}))


@app.get("/api/parkiq/repeat-offenders", summary="Phase 3: Repeat Offenders Stats")
def get_parkiq_repeat_offenders():
    return JSONResponse(parkiq_cache.get("repeat_offender_stats.json", {}))