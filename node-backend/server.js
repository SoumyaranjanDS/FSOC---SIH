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
const io = new Server(server, {
  cors: { origin: "*" },
});

// Setup Multer for video uploads
const uploadDir = path.join(__dirname, "uploads");
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir);
}
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadDir),
  filename: (req, file, cb) =>
    cb(null, "benchmark_" + Date.now() + path.extname(file.originalname)),
});
const upload = multer({ storage });

// Enable CORS for Express routes
app.use((req, res, next) => {
  res.header("Access-Control-Allow-Origin", "*");
  res.header(
    "Access-Control-Allow-Headers",
    "Origin, X-Requested-With, Content-Type, Accept",
  );
  next();
});

// Serve uploaded videos statically
app.use("/uploads", express.static(path.join(__dirname, "uploads")));

// Handle video upload
app.post("/upload_video", upload.single("video"), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: "No video file provided" });
  }
  const videoUrl = `http://localhost:3000/uploads/${req.file.filename}`;
  res.json({ path: req.file.path, filename: req.file.originalname, url: videoUrl });
});

let pythonProcess = null;

function startPythonEngine() {
  if (pythonProcess) return; // already running
  console.log("Starting Python Simulation Engine...");
  pythonProcess = spawn("python", ["../python-engine/simulation_engine.py"]);
  attachPythonListeners();
  io.emit("engine_status", "running");
}

function startBenchmarkEngine(videoPath) {
  if (pythonProcess) {
    stopPythonEngine();
  }
  console.log(`Starting Video Benchmark Engine for: ${videoPath}`);
  pythonProcess = spawn("python", [
    "../python-engine/video/video_benchmark.py",
    videoPath,
  ]);
  attachPythonListeners();
  io.emit("engine_status", "running_benchmark");
}

function attachPythonListeners() {
  if (!pythonProcess) return;

  pythonProcess.stdout.on("data", (data) => {
    const output = data.toString().trim();
    const lines = output.split("\n");
    for (const line of lines) {
      try {
        if (line.startsWith("{") && line.endsWith("}")) {
          const telemetry = JSON.parse(line);
          if (telemetry.event === "complete") {
            io.emit("benchmark_complete", telemetry);
          } else {
            io.emit("telemetry", telemetry);
          }
        } else {
          console.log(`[Python]: ${line}`);
        }
      } catch (e) {
        // Not JSON, just normal print
        // console.log(`[Python Non-JSON]: ${line}`);
      }
    }
  });

  pythonProcess.stderr.on("data", (data) => {
    console.error(`[Python Error]: ${data}`);
  });

  pythonProcess.on("close", (code) => {
    console.log(`Python engine exited with code ${code}`);
    pythonProcess = null;
    io.emit("engine_status", "stopped");
  });
}

function stopPythonEngine() {
  if (pythonProcess) {
    console.log("Stopping Python Engine...");
    pythonProcess.kill("SIGKILL");
    pythonProcess = null;
    io.emit("engine_status", "stopped");
  }
}

// Auto-start on boot (simulation mode)
startPythonEngine();

io.on("connection", (socket) => {
  console.log("React Client connected to Telemetry Bridge");

  // Send current status immediately upon connection
  socket.emit("engine_status", pythonProcess ? "running" : "stopped");

  socket.on("set_config", (config) => {
    if (pythonProcess && pythonProcess.stdin) {
      pythonProcess.stdin.write(JSON.stringify(config) + "\n");
    }
  });

  socket.on("engine_control", (action) => {
    if (action === "start") {
      startPythonEngine();
    } else if (action === "stop") {
      stopPythonEngine();
    } else if (action === "restart") {
      stopPythonEngine();
      setTimeout(startPythonEngine, 500); // Wait half a second before spawning again
    }
  });

  socket.on("start_benchmark", ({ video_path }) => {
    startBenchmarkEngine(video_path);
  });

  socket.on("stop_benchmark", () => {
    stopPythonEngine();
  });
});

server.listen(3000, () => {
  console.log("✅ Telemetry Bridge running on http://localhost:3000");
});
