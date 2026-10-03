# FSOC (Free Space Optical Communication) Tracking System - SIH

![Project Status](https://img.shields.io/badge/status-active-success.svg)
![React](https://img.shields.io/badge/React-19.2-blue.svg)
![Node.js](https://img.shields.io/badge/Node.js-Backend-green.svg)
![Python](https://img.shields.io/badge/Python-Engine-yellow.svg)

## 📌 Project Overview
This project is developed for the **Smart India Hackathon (SIH)**. It is a comprehensive **Free Space Optical Communication (FSOC)** simulation and tracking system. The solution effectively bridges a heavy-duty Python AI/tracking engine with a dynamic React-based frontend dashboard via a Node.js WebSocket bridge, allowing real-time visualization and manipulation of telemetry data.

The system features real-time object tracking utilizing Kalman Filters, simulated PTZ motor physics, and advanced AI-based predictors (CNN/LSTM/GRU).

---

## ✨ Key Features
- **Real-Time Simulation Engine**: Simulate complex target tracking scenarios involving varying speeds, paths, and obstacles.
- **Live Video Benchmarking**: Upload pre-recorded video sequences to benchmark the tracking system's accuracy and performance.
- **Live Webcam Mode**: Utilize real-time webcam feeds for live target acquisition and tracking.
- **Dynamic Environmental Controls**: Real-time manipulation of environmental noise, camera jitter, atmospheric conditions, and platform motion.
- **Live Telemetry Dashboard**: A Vite+React frontend visualizes real-time metrics including target coordinates, PTZ camera position, estimation errors, and network latency.
- **AI-Driven Prediction Models**: Support for LSTM, GRU, and CNN-based trajectory prediction modules.
- **Containerized Environment**: Seamless setup using Docker and Docker Compose.

---

## 🛠️ Technology Stack
### Frontend (Dashboard)
- **Framework**: React 19, Vite
- **Networking**: Socket.IO Client for real-time telemetry streaming
- **Styling/Linting**: Custom UI, Oxlint

### Backend (Bridge Server)
- **Runtime**: Node.js
- **Framework**: Express.js
- **Real-Time Communication**: Socket.IO Server
- **File Uploads**: Multer (for video benchmarks)

### Engine (AI & Tracking Core)
- **Language**: Python 3.x
- **Computer Vision**: OpenCV (cv2)
- **Data & Math**: NumPy, SciPy
- **Machine Learning/AI**: PyTorch (Torch)
- **Tracking Algorithms**: Kalman Filters (`kalman_tracker.py`), PTZ Physics simulation

---

## 📂 Project Structure
```text
FSOC---SIH/
├── node-backend/           # Node.js WebSocket bridge and process manager
│   ├── server.js           # Main Express/Socket server
│   ├── package.json        # Node dependencies
│   └── uploads/            # Directory for benchmark video uploads
├── python-engine/          # Python AI & Tracking Engine
│   ├── simulation_engine.py# Core simulated PTZ and physics engine
│   ├── video_benchmark.py  # Video analysis script
│   ├── webcam_engine.py    # Live webcam tracking script
│   ├── kalman_tracker.py   # Kalman Filter implementation
│   ├── cnn_detector/       # CNN Models
│   ├── gru_predictor/      # GRU Models
│   ├── lstm_predictor/     # LSTM Models
│   └── requirements.txt    # Python dependencies
├── react-frontend/         # Vite + React Dashboard
│   ├── src/                # UI Components and views
│   ├── package.json        # Frontend dependencies
│   └── vite.config.js      # Vite configuration
└── docker-compose.yml      # Orchestration file for Docker deployment
```

---

## 🚀 Getting Started

### Prerequisites
- **Node.js** (v18+ recommended)
- **Python** 3.8+
- **Docker** & **Docker Compose** (Optional, for containerized run)

### Method 1: Using Docker (Recommended)
This is the easiest way to get the entire stack running.

1. Clone the repository and navigate to the project directory:
   ```bash
   cd FSOC---SIH
   ```
2. Build and start the containers:
   ```bash
   docker-compose up --build
   ```
3. Access the application:
   - **Frontend Dashboard**: `http://localhost:5173`
   - **Backend API**: `http://localhost:3000`

### Method 2: Manual Setup

#### 1. Setup Python Engine
```bash
cd python-engine
pip install -r requirements.txt
cd ..
```

#### 2. Setup Node Backend
```bash
cd node-backend
npm install
npm run dev
```

#### 3. Setup React Frontend
Open a new terminal window:
```bash
cd react-frontend
npm install
npm run dev
```
The React frontend will run on `http://localhost:5173` by default.

---

## ⚙️ Workflow & Architecture
1. **Frontend Command**: The user configures tracking parameters (like adding obstacles, changing noise levels) or selects a mode (Simulation / Benchmark / Webcam) via the React UI.
2. **Bridge Relay**: The React app sends these commands over WebSockets to the Node.js backend.
3. **Process Management**: The Node.js server acts as a manager. It spawns the corresponding Python process (e.g., `simulation_engine.py`) and passes configurations to it via `stdin`.
4. **Engine Execution**: The Python Engine processes physics, applies Kalman filtering or neural network predictions, and generates tracking telemetry.
5. **Data Streaming**: Python outputs structured JSON telemetry via `stdout`.
6. **Real-time Display**: Node.js reads the stdout, parses the telemetry, and broadcasts it back to the React UI via WebSockets for real-time rendering.

---

## 📜 License
This project was developed for the Smart India Hackathon (SIH). All rights reserved by the respective contributors and authors.
