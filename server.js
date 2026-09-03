import { spawn } from "child_process";
import express from "express";
import http from "http";
import { Server } from "socket.io";

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: { origin: "*" },
});

// Spawn the Python simulation engine
const pythonProcess = spawn("python", ["simulation_engine.py"]);

pythonProcess.stdout.on("data", (data) => {
  const output = data.toString().trim();
  const lines = output.split("\n");

  for (const line of lines) {
    try {
      if (line.startsWith("{") && line.endsWith("}")) {
        const telemetry = JSON.parse(line);
        // Print the JSON to the terminal so we can see it!
        console.log(JSON.stringify(telemetry));
        // Broadcast telemetry to all connected HTML dashboards
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
});

server.listen(3000, () => {
  console.log("✅ Telemetry Bridge running on http://localhost:3000");
});
