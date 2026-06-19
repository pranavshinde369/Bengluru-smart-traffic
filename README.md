# BTP-Niyantran 🚦
> AI-powered Smart City Traffic Management & Analytics Platform for Bengaluru Traffic Police

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-blue)](https://github.com/ultralytics/ultralytics)

## 1. Project Title and Description
**BTP-Niyantran (v2.0)** is an advanced, AI-driven traffic intelligence and parking analytics platform tailored for the Bengaluru Traffic Police (BTP). Building upon real-time edge computing, the v2.0 update introduces **ParkIQ**—a comprehensive suite for urban mobility analytics—along with Dwell-Timer state machines, hazard-light heuristics, and Shapely-based polygon geofencing. 

The system utilizes existing CCTV infrastructure to reduce congestion, automatically detect unauthorized parking, and offer deep analytics on deterrence decay, BPR congestion impact, and spatial clusters at major Bengaluru junctions (e.g., Silk Board, KR Market, MG Road).

## 2. Key Features (v2.0)
- **ParkIQ Analytics (Phase 3):** HDBSCAN-based clustering of violations, BPR (Bureau of Public Roads) congestion impact scoring, Deterrence Decay curve analysis, and spatio-temporal heatmaps.
- **Dwell-Timer State Machine (Phase 1):** Differentiates between moving traffic, temporary stops (grace period), and strict violations using real-time object tracking.
- **Hazard-Light Exception Heuristic:** Automatically detects flickering hazard lights to exempt broken-down vehicles from unauthorized parking E-Challans.
- **Shapely Polygon Geofencing:** Replaced basic rectangular bounding boxes with precise, junction-specific polygon geofences to reduce false positives.
- **Priority Corridor Mode:** A one-click fail-safe to prioritize VIP corridors, ambulances, or massive crowds (overrides standard RL signal).
- **Dynamic RL Optimizer:** Adaptive signal control based on real-time vehicle density to reduce commute times and emissions.
- **Auto E-Challan Generation:** Generates real-time infraction logs with unique challan IDs (e.g., `BTP-YYYYMMDD-XXXX`).

## 3. Tech Stack
- **AI / Computer Vision:** YOLOv8n, OpenCV 4.9, NumPy, PyTorch 2.0, Shapely (Geofencing)
- **Backend:** Python, FastAPI, Uvicorn
- **Frontend:** React 18, Vite, TypeScript, Tailwind CSS, shadcn/ui, Recharts
- **LLM / Generative AI:** Google Gemini 1.5 Flash (Context-grounded)

## 4. Installation Instructions

### Prerequisites
- Python 3.9+
- Node.js 18+ & npm

### Backend Setup
```bash
# 1. Navigate to the backend directory
cd backend

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Provide a video feed
# Place your CCTV feed as 'traffic_feed.mp4' in the backend/ directory
# (If missing, the system will automatically run a synthetic demo feed)
```

### Frontend Setup
```bash
# 1. Navigate to the frontend directory
cd frontend2

# 2. Install dependencies
npm install
```

## 5. Usage

### Running the Backend
```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
*The API will be live at `http://localhost:8000`. Auto-generated Swagger docs available at `http://localhost:8000/docs`.*

### Running the Frontend
```bash
cd frontend2
npm run dev
```
*The React Dashboard will be accessible at `http://localhost:8080` (or the port specified by Vite, typically `5173`).*

## 6. Project Structure
```text
Bengluru-smart-traffic/
├── backend/                  # FastAPI Backend & AI Engine (v2.0)
│   ├── main.py               # Core application, Dwell-timers, ParkIQ
│   ├── requirements.txt      # Python dependencies
│   ├── traffic_feed.mp4      # Live CCTV or demo footage
│   └── yolov8n.pt            # Pre-trained YOLOv8 Nano weights
│
├── frontend2/                # React Vite Application
│   ├── src/                  # React components, pages, and hooks
│   ├── public/               # Static assets
│   ├── package.json          # Node dependencies
│   ├── tailwind.config.ts    # Tailwind UI configurations
│   └── components.json       # shadcn/ui component definitions
│
└── README.md                 # Project Documentation
```

## 7. API Documentation (FastAPI)
The backend serves both core operational endpoints and the new ParkIQ analytics:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/video-feed` | Streams live processed MJPEG video frames with YOLO bounding boxes and Geofences. |
| `GET`  | `/api/traffic-data` | Real-time metrics (vehicle counts, Dwell-states, alerts, green times, FPS). |
| `GET`  | `/api/alert-log` | History of encroachment violations and auto-generated BTP E-Challans. |
| `GET`  | `/api/carbon-log` | 30-day rolling array of CO2 metrics and RL learning efficiency. |
| `POST` | `/api/settings` | Hot-reloads configuration (Priority Corridor Mode, confidence thresholds). |
| `GET`  | `/api/geofence-zones` | Retrieves coordinates for Shapely polygon geofences. |
| `GET`  | `/api/parkiq/clusters` | **ParkIQ:** HDBSCAN-based cluster data for parking violations. |
| `GET`  | `/api/parkiq/congestion-scores` | **ParkIQ:** BPR congestion impact scores per zone. |
| `GET`  | `/api/parkiq/deterrence-decay` | **ParkIQ:** Historical deterrence decay curve data. |
| `GET`  | `/api/parkiq/heatmap` | **ParkIQ:** Spatio-temporal heatmap intensity matrix. |
| `GET`  | `/api/parkiq/repeat-offenders` | **ParkIQ:** Repeat offenders and violation share statistics. |

## 8. Screenshots

*(Ensure your `screenshots` folder contains updated dashboard images showing the BTP-Niyantran HUD and ParkIQ Analytics)*

- **Dashboard:** Live CCTV feed with Shapely polygon overlays and Dwell-timers.
- **Alert Logs:** Auto E-Challan Generation (`BTP-YYYYMMDD-XXXX`).
- **ParkIQ Analytics:** Heatmaps, Deterrence Decay charts, and Congestion Scores.

## 9. Configuration
- **Backend Configuration:** The application supports hot-reloading via `/api/settings`. Hardcoded defaults for polygons and zones (Silk Board, KR Market, MG Road, etc.) are at the top of `backend/main.py`.
- **Frontend Configuration:** The frontend targets `http://localhost:8000`. Adjust API base URLs in your React `.env` if deploying remotely.

## 10. Contributing Guidelines
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/ParkIQUpdate`).
3. Commit your changes (`git commit -m 'Add ParkIQ analytics'`).
4. Push to the branch (`git push origin feature/ParkIQUpdate`).
5. Open a Pull Request.

## 11. License
This project is open-source and distributed under the **MIT License**.

## 12. Author / Credits
**Team Name:** VYOMAN
