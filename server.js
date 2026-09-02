const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const { spawn } = require("child_process");
const path = require("path");

const app = express();
const server = http.createServer(app);
const io = new Server(server);

// Serve static files from the current directory
app.use(express.static(__dirname));

// Default route to serve the dashboard
app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "dashboard_concept.html"));
});

// Start the Python Engine
console.log("Starting Python Simulation Engine...");
const engine = spawn("python", ["engine.py"]);

engine.stdout.on("data", (data) => {
  const lines = data.toString().split("\n");
  for (const line of lines) {
    if (line.trim() === "") continue;
    try {
      const telemetry = JSON.parse(line);
      // Broadcast the telemetry to all connected web clients
      io.emit("telemetry", telemetry);
    } catch (err) {
      console.error(
        "Error parsing JSON from Python:",
        err.message,
        "Line:",
        line,
      );
    }
  }
});

engine.stderr.on("data", (data) => {
  console.error(`Python Error: ${data}`);
});

engine.on("close", (code) => {
  console.log(`Python engine process exited with code ${code}`);
});

io.on("connection", (socket) => {
  console.log("Web Dashboard connected:", socket.id);
  socket.on("disconnect", () => {
    console.log("Web Dashboard disconnected:", socket.id);
  });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Server listening on http://localhost:${PORT}`);
});
