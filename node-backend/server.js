import { spawn } from "child_process";
import express from "express";
import http from "http";
import { Server } from "socket.io";
import path from "path";
import { fileURLToPath } from "url";
import multer from "multer";
import fs from "fs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: "*" } });

// Setup Multer for video uploads
const uploadDir = path.join(__dirname, "uploads");
if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir);
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadDir),
  filename: (req, file, cb) =>
    cb(null, "benchmark_" + Date.now() + path.extname(file.originalname)),
});
const upload = multer({ storage });

app.use((req, res, next) => {
  res.header("Access-Control-Allow-Origin", "*");
  res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept");
  next();
});

app.use("/uploads", express.static(path.join(__dirname, "uploads")));

app.post("/upload_video", upload.single("video"), (req, res) => {
  if (!req.file) return res.status(400).json({ error: "No video file provided" });
  const videoUrl = `http://localhost:3000/uploads/${req.file.filename}`;
  res.json({ path: req.file.path, filename: req.file.originalname, url: videoUrl });
});

let processes = {
  simulation: null,
  benchmark: null,
  webcam: null
};

function startPythonEngine() {
  if (processes.simulation) return;
  console.log("Starting Python Simulation Engine...");
  processes.simulation = spawn("python", ["-u", "../python-engine/simulation_engine.py"]);
  attachPythonListeners(processes.simulation, "simulation");
  io.emit("engine_status", { mode: "simulation", status: "running" });
}

function startBenchmarkEngine(videoPath) {
  if (processes.benchmark) stopPythonEngine("benchmark");
  console.log(`Starting Video Benchmark Engine for: ${videoPath}`);
  processes.benchmark = spawn("python", ["-u", "../python-engine/video/video_benchmark.py", videoPath]);
  attachPythonListeners(processes.benchmark, "benchmark");
  io.emit("engine_status", { mode: "benchmark", status: "running_benchmark" });
}

function startWebcamEngine() {
  if (processes.webcam) {
    stopPythonEngine("webcam");
    // FIX #2: Wait for port 5001 to be released before respawning
    setTimeout(doStartWebcam, 1500);
  } else {
    doStartWebcam();
  }
}

function doStartWebcam() {
  console.log("Starting Live Webcam Engine");
  // FIX #5: Emit loading status first
  io.emit("engine_status", { mode: "webcam", status: "webcam_loading" });
  processes.webcam = spawn("python", ["-u", "../python-engine/webcam_engine.py", "--headless"]);
  attachPythonListeners(processes.webcam, "webcam");
  io.emit("engine_status", { mode: "webcam", status: "running_webcam" });
}

function attachPythonListeners(pythonProcess, modeName) {
  if (!pythonProcess) return;
  let buffer = "";

  pythonProcess.stdout.on("data", (data) => {
    buffer += data.toString();
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
          const telemetry = JSON.parse(trimmed);
          
          if (telemetry.event === "started") {
            if (telemetry.mode === "webcam") {
              io.emit("engine_status", { mode: "webcam", status: "running_webcam" });
              io.emit("webcam_started", telemetry);
            } else if (telemetry.mode === "benchmark") {
              io.emit("engine_status", { mode: "benchmark", status: "running_benchmark" });
              io.emit("benchmark_started", telemetry);
            }
            continue;
          }
          if (telemetry.event === "complete") {
            if (telemetry.mode === "webcam") io.emit("webcam_complete", telemetry);
            else io.emit("benchmark_complete", telemetry);
            continue; 
          }
          if (telemetry.event === "error") { 
            if (telemetry.mode === "webcam") io.emit("webcam_error", telemetry);
            else io.emit("benchmark_error", telemetry); 
            continue; 
          }
          io.emit("telemetry", telemetry);
        } else {
          console.log(`[Python ${modeName}]: ${trimmed}`);
        }
      } catch (e) {
        console.log(`[Python ${modeName} Non-JSON]: ${trimmed}`);
      }
    }
  });

  pythonProcess.stderr.on("data", (data) => console.error(`[Python ${modeName} Error]: ${data.toString()}`));
  pythonProcess.on("close", (code) => {
    console.log(`Python ${modeName} engine exited with code ${code}`);
    processes[modeName] = null;
    io.emit("engine_status", { mode: modeName, status: "stopped" });
  });
}

function stopPythonEngine(modeName) {
  if (modeName === "all") {
    Object.keys(processes).forEach(stopPythonEngine);
    return;
  }
  
  if (processes[modeName]) {
    console.log(`Stopping Python Engine (${modeName})...`);
    const proc = processes[modeName];
    processes[modeName] = null;
    io.emit("engine_status", { mode: modeName, status: "stopped" });
    
    // FIX #2: Try graceful SIGTERM first so sockets are released cleanly,
    // then force-kill after 2 seconds if the process is still alive.
    try {
      proc.kill("SIGTERM");
    } catch (_) { /* already dead */ }
    setTimeout(() => {
      try {
        proc.kill("SIGKILL");
      } catch (_) { /* already dead */ }
    }, 2000);
  }
}

// Start simulation by default
startPythonEngine();

io.on("connection", (socket) => {
  console.log("React Client connected to Telemetry Bridge");
  
  // Send current status for all engines
  socket.emit("engine_status", { mode: "simulation", status: processes.simulation ? "running" : "stopped" });
  socket.emit("engine_status", { mode: "benchmark", status: processes.benchmark ? "running_benchmark" : "stopped" });
  socket.emit("engine_status", { mode: "webcam", status: processes.webcam ? "running_webcam" : "stopped" });

  socket.on("set_config", (config) => {
    if (processes.simulation && processes.simulation.stdin)
      processes.simulation.stdin.write(JSON.stringify(config) + "\n");
  });

  socket.on("engine_control", (action) => {
    if (action === "start") startPythonEngine();
    else if (action === "stop") stopPythonEngine("simulation");
    else if (action === "restart") { stopPythonEngine("simulation"); setTimeout(startPythonEngine, 500); }
  });

  socket.on("start_benchmark", ({ video_path }) => startBenchmarkEngine(video_path));
  socket.on("stop_benchmark", () => stopPythonEngine("benchmark"));
  
  socket.on("start_webcam", () => startWebcamEngine());
  socket.on("stop_webcam", () => stopPythonEngine("webcam"));
});

server.listen(3000, () => console.log("✅ Telemetry Bridge running on http://localhost:3000"));
