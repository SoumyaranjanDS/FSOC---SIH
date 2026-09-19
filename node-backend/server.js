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

let pythonProcess = null;
let currentEngineMode = "stopped";

function startPythonEngine() {
  if (pythonProcess) return;
  console.log("Starting Python Simulation Engine...");
  pythonProcess = spawn("python", ["../python-engine/simulation_engine.py"]);
  currentEngineMode = "simulation";
  attachPythonListeners();
  io.emit("engine_status", "running");
}

function startBenchmarkEngine(videoPath) {
  if (pythonProcess) stopPythonEngine();
  console.log(`Starting Video Benchmark Engine for: ${videoPath}`);
  pythonProcess = spawn("python", ["../python-engine/video/video_benchmark.py", videoPath]);
  currentEngineMode = "benchmark";
  attachPythonListeners();
  io.emit("engine_status", "benchmark_loading");
}

function attachPythonListeners() {
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
            io.emit("engine_status", "running_benchmark");
            io.emit("benchmark_started", telemetry);
            continue;
          }
          if (telemetry.event === "complete") { io.emit("benchmark_complete", telemetry); continue; }
          if (telemetry.event === "error") { io.emit("benchmark_error", telemetry); continue; }
          io.emit("telemetry", telemetry);
        } else {
          console.log(`[Python]: ${trimmed}`);
        }
      } catch (e) {
        console.log(`[Python Non-JSON]: ${trimmed}`);
      }
    }
  });

  pythonProcess.stderr.on("data", (data) => console.error(`[Python Error]: ${data.toString()}`));
  pythonProcess.on("close", (code) => {
    console.log(`Python engine exited with code ${code}`);
    pythonProcess = null;
    currentEngineMode = "stopped";
    io.emit("engine_status", "stopped");
  });
}

function stopPythonEngine() {
  if (pythonProcess) {
    console.log("Stopping Python Engine...");
    pythonProcess.kill("SIGKILL");
    pythonProcess = null;
    currentEngineMode = "stopped";
    io.emit("engine_status", "stopped");
  }
}

startPythonEngine();

io.on("connection", (socket) => {
  console.log("React Client connected to Telemetry Bridge");
  if (currentEngineMode === "simulation") socket.emit("engine_status", "running");
  else if (currentEngineMode === "benchmark") socket.emit("engine_status", "running_benchmark");
  else socket.emit("engine_status", "stopped");

  socket.on("set_config", (config) => {
    if (pythonProcess && pythonProcess.stdin)
      pythonProcess.stdin.write(JSON.stringify(config) + "\n");
  });

  socket.on("engine_control", (action) => {
    if (action === "start") startPythonEngine();
    else if (action === "stop") stopPythonEngine();
    else if (action === "restart") { stopPythonEngine(); setTimeout(startPythonEngine, 500); }
  });

  socket.on("start_benchmark", ({ video_path }) => startBenchmarkEngine(video_path));
  socket.on("stop_benchmark", () => stopPythonEngine());
});

server.listen(3000, () => console.log("✅ Telemetry Bridge running on http://localhost:3000"));
