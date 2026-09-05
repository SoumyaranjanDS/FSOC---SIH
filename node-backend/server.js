import { spawn } from "child_process";
import express from "express";
import http from "http";
import { Server } from "socket.io";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: { origin: "*" },
});

let pythonProcess = null;

function startPythonEngine() {
  if (pythonProcess) return; // already running
  console.log("Starting Python Simulation Engine...");
  pythonProcess = spawn("python", ["../python-engine/simulation_engine.py"]);

  pythonProcess.stdout.on("data", (data) => {
    const output = data.toString().trim();
    const lines = output.split("\n");
    for (const line of lines) {
      try {
        if (line.startsWith("{") && line.endsWith("}")) {
          const telemetry = JSON.parse(line);
          io.emit("telemetry", telemetry);
        } else {
          console.log(`[Python]: ${line}`);
        }
      } catch (e) {
        console.log(`[Python JSON Error]: ${line}`);
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
  
  io.emit("engine_status", "running");
}

function stopPythonEngine() {
  if (pythonProcess) {
    console.log("Stopping Python Simulation Engine...");
    pythonProcess.kill("SIGKILL");
    pythonProcess = null;
    io.emit("engine_status", "stopped");
  }
}

// Auto-start on boot
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
});

server.listen(3000, () => {
  console.log("✅ Telemetry Bridge running on http://localhost:3000");
});
