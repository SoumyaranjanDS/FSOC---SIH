import { useState, useEffect } from "react";
import { io } from "socket.io-client";
import "./App.css";

const socket = io("http://localhost:3000");

function App() {
  const [telemetry, setTelemetry] = useState(null);
  const [connected, setConnected] = useState(false);
  const [logs, setLogs] = useState([]);
  const [engineStatus, setEngineStatus] = useState("stopped");

  // Control Panel States
  const [targetSpeed, setTargetSpeed] = useState(15);
  const [targetPath, setTargetPath] = useState("Random");
  const [obstaclesEnabled, setObstaclesEnabled] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(0.4);

  const handleSpeedChange = (e) => {
    const speed = e.target.value;
    setTargetSpeed(speed);
    socket.emit("set_config", { target_speed: speed });
  };

  const handlePathChange = (e) => {
    const path = e.target.value;
    setTargetPath(path);
    socket.emit("set_config", { target_path: path });
  };

  const handleObstaclesChange = (e) => {
    const enabled = e.target.checked;
    setObstaclesEnabled(enabled);
    socket.emit("set_config", { obstacles_enabled: enabled });
  };

  // --- DISTURBANCES & NOISE CONTROLS ---
  const [noiseType, setNoiseType] = useState("None");
  const [noiseStdDev, setNoiseStdDev] = useState(20);
  const [cameraJitter, setCameraJitter] = useState(0);
  const [atmospheric, setAtmospheric] = useState("Clear");
  const [platformMotion, setPlatformMotion] = useState("None");

  const handleNoiseTypeChange = (e) => {
    const val = e.target.value;
    setNoiseType(val);
    socket.emit("set_config", { noise_type: val });
  };
  const handleNoiseStdDevChange = (e) => {
    const val = parseInt(e.target.value, 10);
    setNoiseStdDev(val);
    socket.emit("set_config", { noise_std_dev: val });
  };
  const handleCameraJitterChange = (e) => {
    const val = parseInt(e.target.value, 10);
    setCameraJitter(val);
    socket.emit("set_config", { camera_jitter: val });
  };
  const handleAtmosphericChange = (e) => {
    const val = e.target.value;
    setAtmospheric(val);
    socket.emit("set_config", { atmospheric: val });
  };
  const handlePlatformMotionChange = (e) => {
    const val = e.target.value;
    setPlatformMotion(val);
    socket.emit("set_config", { platform_motion: val });
  };

  const sendEngineCommand = (action) => {
    socket.emit("engine_control", action);
  };

  useEffect(() => {
    socket.on("connect", () => setConnected(true));
    socket.on("disconnect", () => setConnected(false));
    socket.on("engine_status", (status) => setEngineStatus(status));
    socket.on("telemetry", (data) => {
      setTelemetry(data);
      if (data.log) {
        setLogs((prev) => {
          const newLogs = [
            ...prev,
            `[${new Date().toLocaleTimeString()}] ${data.log}`,
          ];
          return newLogs.slice(-20); // Keep only the last 20 logs
        });
      }
    });

    return () => {
      socket.off("connect");
      socket.off("disconnect");
      socket.off("engine_status");
      socket.off("telemetry");
    };
  }, []);

  // Safely extract coordinates if telemetry exists
  const targetX = telemetry?.target?.x || 0;
  const targetY = telemetry?.target?.y || 0;
  const camX = telemetry?.camera?.x || 0;
  const camY = telemetry?.camera?.y || 0;
  const status = telemetry?.status || "WAITING";

  return (
    <div
      style={{
        width: "100vw",
        height: "100vh",
        overflow: "hidden",
        background: "#050505",
        fontFamily: "monospace",
      }}
    >
      {/* 1. FIXED HUD (Always visible on screen) */}
      <div
        style={{
          position: "fixed",
          top: 20,
          left: 20,
          zIndex: 1000,
          background: "rgba(10, 10, 10, 0.8)",
          border: "1px solid #333",
          padding: "15px",
          borderRadius: "8px",
          color: "#0f0",
          backdropFilter: "blur(5px)",
          // We must allow pointer events so the user can interact with the slider!
          pointerEvents: "auto",
        }}
      >
        <h2
          style={{
            margin: "0 0 10px 0",
            borderBottom: "1px solid #333",
            paddingBottom: "5px",
          }}
        >
          FSOC Optical Testbed
        </h2>

        {/* ENGINE CONTROLS */}
        <div style={{ display: "flex", gap: "10px", marginBottom: "15px" }}>
          <button
            onClick={() => sendEngineCommand("start")}
            disabled={engineStatus === "running"}
            style={{
              flex: 1,
              padding: "8px",
              background: engineStatus === "running" ? "#222" : "#166534",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            START
          </button>
          <button
            onClick={() => sendEngineCommand("stop")}
            disabled={engineStatus === "stopped"}
            style={{
              flex: 1,
              padding: "8px",
              background: engineStatus === "stopped" ? "#222" : "#991b1b",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            STOP
          </button>
          <button
            onClick={() => sendEngineCommand("restart")}
            style={{
              flex: 1,
              padding: "8px",
              background: "#b45309",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            RESTART
          </button>
        </div>

        <div>Bridge: {connected ? "🟢 ONLINE" : "🔴 OFFLINE"}</div>
        <div>
          Engine: {engineStatus === "running" ? "🟢 RUNNING" : "🔴 STOPPED"}
        </div>
        <div>
          Tracking:{" "}
          <span style={{ color: status === "TRACKING" ? "#0f0" : "#f00" }}>
            {status}
          </span>
        </div>

        {status === "PREDICTING" && (
          <div
            style={{
              marginTop: "10px",
              padding: "8px",
              background: "rgba(255, 200, 0, 0.15)",
              border: "1px solid #ffc800",
              color: "#ffc800",
              fontWeight: "bold",
              textAlign: "center",
            }}
          >
            ⚠ TARGET LOST — KALMAN PREDICTION ACTIVE ⚠
          </div>
        )}

        {status === "KALMAN COASTING" && (
          <div
            style={{
              marginTop: "10px",
              padding: "8px",
              background: "rgba(0, 200, 255, 0.15)",
              border: "1px solid #00c8ff",
              color: "#00c8ff",
              fontWeight: "bold",
              textAlign: "center",
              animation: "blink 1s infinite",
            }}
          >
            🌀 KALMAN COASTING ACTIVE 🌀
            {telemetry?.coasting_coord && (
              <div
                style={{
                  fontSize: "11px",
                  marginTop: "4px",
                  fontWeight: "normal",
                  color: "#88ddff",
                }}
              >
                Prediction: ({telemetry.coasting_coord.x},{" "}
                {telemetry.coasting_coord.y})
              </div>
            )}
          </div>
        )}

        <div style={{ display: "flex", gap: "20px", marginTop: "15px" }}>
          <div style={{ borderLeft: "2px solid #fff", paddingLeft: "10px" }}>
            <div style={{ color: "#aaa", fontSize: "12px" }}>TARGET BEACON</div>
            <div>X: {targetX}px</div>
            <div>Y: {targetY}px</div>
          </div>
          <div style={{ borderLeft: "2px solid #0f0", paddingLeft: "10px" }}>
            <div style={{ color: "#aaa", fontSize: "12px" }}>CAMERA SENSOR</div>
            <div>X: {camX}px</div>
            <div>Y: {camY}px</div>
          </div>
        </div>

        {/* 1.2 CONTROL PANEL (Bidirectional Configuration) */}
        <div
          style={{
            marginTop: "15px",
            borderTop: "1px solid #333",
            paddingTop: "10px",
          }}
        >
          <div style={{ color: "#aaa", fontSize: "12px", marginBottom: "5px" }}>
            LIVE CONFIGURATION
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "5px" }}>
            <label
              style={{
                fontSize: "12px",
                display: "flex",
                justifyContent: "space-between",
                marginTop: "10px",
              }}
            >
              <span>Map Zoom: {Math.round(zoomLevel * 100)}%</span>
            </label>
            <input
              type="range"
              min="0.1"
              max="2.0"
              step="0.05"
              value={zoomLevel}
              onChange={(e) => setZoomLevel(parseFloat(e.target.value))}
              style={{
                width: "100%",
                cursor: "pointer",
                accentColor: "#00aaff",
              }}
            />

            <label
              style={{
                fontSize: "12px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
                marginTop: "15px",
                padding: "8px",
                background: "rgba(255, 255, 255, 0.05)",
                borderRadius: "4px",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={obstaclesEnabled}
                onChange={handleObstaclesChange}
                style={{ width: "16px", height: "16px", cursor: "pointer" }}
              />
              <span
                style={{
                  fontWeight: "bold",
                  color: obstaclesEnabled ? "#fff" : "#888",
                }}
              >
                Enable Virtual Clouds (Obstacles)
              </span>
            </label>

            <label
              style={{
                fontSize: "12px",
                display: "flex",
                justifyContent: "space-between",
                marginTop: "10px",
              }}
            >
              <span>Target Path Profile:</span>
            </label>
            <select
              value={targetPath}
              onChange={handlePathChange}
              style={{
                width: "100%",
                padding: "5px",
                background: "#222",
                color: "#0f0",
                border: "1px solid #333",
                cursor: "pointer",
              }}
            >
              <option value="Random">Random (Smooth Inertia)</option>
              <option value="Straight Line">Straight Line</option>
              <option value="Circular">Circular</option>
              <option value="Figure of 8">Figure of 8</option>
              <option value="Spiral">Spiral</option>
              <option value="Sinusoidal">Sinusoidal</option>
            </select>
            <label
              style={{
                fontSize: "12px",
                display: "flex",
                justifyContent: "space-between",
                marginTop: "10px",
              }}
            >
              <span>Target Speed (px/frame):</span>
              <span
                style={{
                  color: targetSpeed > 26 ? "#f00" : "#0f0",
                  fontWeight: "bold",
                }}
              >
                {targetSpeed} {targetSpeed > 26 && " (ESCAPING)"}
              </span>
            </label>
            <input
              type="range"
              min="1"
              max="40"
              value={targetSpeed}
              onChange={handleSpeedChange}
              style={{
                width: "100%",
                cursor: "pointer",
                accentColor: targetSpeed > 26 ? "#f00" : "#0f0",
              }}
            />

            <div
              style={{
                color: "#aaa",
                fontSize: "12px",
                marginTop: "15px",
                marginBottom: "5px",
                borderTop: "1px solid #333",
                paddingTop: "10px",
              }}
            >
              DISTURBANCES & NOISE
            </div>

            <label
              style={{
                fontSize: "11px",
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              <span>Atmospheric Condition:</span>
            </label>
            <select
              value={atmospheric}
              onChange={handleAtmosphericChange}
              style={{
                width: "100%",
                padding: "4px",
                background: "#222",
                color: "#00aaff",
                border: "1px solid #333",
                cursor: "pointer",
                fontSize: "12px",
              }}
            >
              <option value="Clear">Clear</option>
              <option value="Haze">Haze</option>
              <option value="Fog">Fog</option>
              <option value="Rain">Rain</option>
              <option value="Low light">Low Light</option>
            </select>

            <label
              style={{
                fontSize: "11px",
                display: "flex",
                justifyContent: "space-between",
                marginTop: "5px",
              }}
            >
              <span>Image Noise:</span>
            </label>
            <select
              value={noiseType}
              onChange={handleNoiseTypeChange}
              style={{
                width: "100%",
                padding: "4px",
                background: "#222",
                color: "#ff8800",
                border: "1px solid #333",
                cursor: "pointer",
                fontSize: "12px",
              }}
            >
              <option value="None">None</option>
              <option value="Salt & Pepper">Salt & Pepper</option>
              <option value="Gaussian">Gaussian</option>
              <option value="Poisson">Poisson</option>
            </select>
            {noiseType !== "None" && (
              <div
                style={{ display: "flex", alignItems: "center", gap: "10px" }}
              >
                <span style={{ fontSize: "11px" }}>StdDev: {noiseStdDev}</span>
                <input
                  type="range"
                  min="1"
                  max="100"
                  value={noiseStdDev}
                  onChange={handleNoiseStdDevChange}
                  style={{ flex: 1, accentColor: "#ff8800" }}
                />
              </div>
            )}

            <label
              style={{
                fontSize: "11px",
                display: "flex",
                justifyContent: "space-between",
                marginTop: "5px",
              }}
            >
              <span>Camera Jitter (± px): {cameraJitter}</span>
            </label>
            <input
              type="range"
              min="0"
              max="50"
              value={cameraJitter}
              onChange={handleCameraJitterChange}
              style={{ width: "100%", accentColor: "#ff0044" }}
            />

            <label
              style={{
                fontSize: "11px",
                display: "flex",
                justifyContent: "space-between",
                marginTop: "5px",
              }}
            >
              <span>Platform Motion:</span>
            </label>
            <select
              value={platformMotion}
              onChange={handlePlatformMotionChange}
              style={{
                width: "100%",
                padding: "4px",
                background: "#222",
                color: "#ff00ff",
                border: "1px solid #333",
                cursor: "pointer",
                fontSize: "12px",
              }}
            >
              <option value="None">None</option>
              <option value="Linear">Linear</option>
              <option value="Circular">Circular</option>
              <option value="Random">Random</option>
              <option value="Figure of 8">Figure of 8</option>
              <option value="Spiral">Spiral</option>
            </select>
          </div>
        </div>
      </div>

      {/* 1.5 LOGS TERMINAL (Right Side HUD) */}
      <div
        style={{
          position: "fixed",
          top: 20,
          right: 20,
          zIndex: 1000,
          background: "rgba(5, 5, 5, 0.9)",
          border: "1px solid #333",
          padding: "15px",
          borderRadius: "8px",
          color: "#0f0",
          width: "400px",
          height: "300px",
          overflowY: "auto",
          backdropFilter: "blur(5px)",
          pointerEvents: "none",
        }}
      >
        <h3
          style={{
            margin: "0 0 10px 0",
            borderBottom: "1px solid #333",
            paddingBottom: "5px",
            color: "#aaa",
            fontSize: "14px",
          }}
        >
          AI Core Terminal
        </h3>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "5px",
            fontSize: "12px",
          }}
        >
          {logs.length === 0 ? (
            <span style={{ color: "#555" }}>Waiting for AI events...</span>
          ) : (
            logs.map((log, i) => (
              <span
                key={i}
                style={{ 
                  color: log.includes("LOST") ? "#f00" 
                       : log.includes("DISTURBED") ? "#ffaa00" 
                       : log.includes("REACQUIRING") ? "#ff00ff"
                       : log.includes("ACQUIRING") ? "#00aaff"
                       : "#0f0" 
                }}
              >
                {log}
              </span>
            ))
          )}
        </div>
      </div>

      {/* 1.6 PERFORMANCE METRICS (Right Side HUD) */}
      <div
        style={{
          position: "fixed",
          top: 340,
          right: 20,
          zIndex: 1000,
          background: "rgba(5, 5, 5, 0.9)",
          border: "1px solid #333",
          padding: "15px",
          borderRadius: "8px",
          color: "#fff",
          width: "400px",
          backdropFilter: "blur(5px)",
          pointerEvents: "none",
        }}
      >
        <h3
          style={{
            margin: "0 0 10px 0",
            borderBottom: "1px solid #333",
            paddingBottom: "5px",
            color: "#00aaff",
            fontSize: "14px",
            display: "flex",
            justifyContent: "space-between"
          }}
        >
          <span>Live Performance Report</span>
          <span style={{color: "#0f0"}}>{telemetry?.performance?.fps?.toFixed(1) || "0.0"} FPS</span>
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", fontSize: "12px" }}>
          
          <div style={{ background: "#111", padding: "8px", borderRadius: "4px", border: "1px solid #222" }}>
            <div style={{ color: "#888", marginBottom: "4px" }}>Simulation Time</div>
            <div style={{ fontSize: "16px", color: "#fff" }}>
              {telemetry?.performance?.duration ? new Date(telemetry.performance.duration * 1000).toISOString().substr(14, 5) : "00:00"}
            </div>
          </div>

          <div style={{ background: "#111", padding: "8px", borderRadius: "4px", border: "1px solid #222" }}>
            <div style={{ color: "#888", marginBottom: "4px" }}>Acquisition Time</div>
            <div style={{ fontSize: "16px", color: telemetry?.performance?.acquisition_time > 0 ? "#0f0" : "#888" }}>
              {telemetry?.performance?.acquisition_time ? telemetry.performance.acquisition_time.toFixed(2) + " s" : "Waiting..."}
            </div>
          </div>

          <div style={{ background: "#111", padding: "8px", borderRadius: "4px", border: "1px solid #222" }}>
            <div style={{ color: "#888", marginBottom: "4px" }}>Avg Tracking Error</div>
            <div style={{ fontSize: "16px", color: telemetry?.performance?.avg_error > 10 ? "#f00" : "#0f0" }}>
              {telemetry?.performance?.avg_error ? telemetry.performance.avg_error.toFixed(2) + " px" : "0.00 px"}
            </div>
          </div>

          <div style={{ background: "#111", padding: "8px", borderRadius: "4px", border: "1px solid #222" }}>
            <div style={{ color: "#888", marginBottom: "4px" }}>Max Tracking Error</div>
            <div style={{ fontSize: "16px", color: "#ffaa00" }}>
              {telemetry?.performance?.max_error ? telemetry.performance.max_error.toFixed(2) + " px" : "0.00 px"}
            </div>
          </div>

          <div style={{ gridColumn: "span 2", background: "#111", padding: "8px", borderRadius: "4px", border: "1px solid #222" }}>
            <div style={{ color: "#888", marginBottom: "4px", display: "flex", justifyContent: "space-between" }}>
              <span>Lock Retention Rate</span>
              <span style={{ color: telemetry?.performance?.lock_retention_rate > 95 ? "#0f0" : "#f00" }}>
                {telemetry?.performance?.lock_retention_rate ? telemetry.performance.lock_retention_rate.toFixed(1) + "%" : "100.0%"}
              </span>
            </div>
            {/* Progress Bar */}
            <div style={{ width: "100%", height: "4px", background: "#333", borderRadius: "2px", overflow: "hidden", marginTop: "4px" }}>
              <div style={{ 
                width: `${telemetry?.performance?.lock_retention_rate || 100}%`, 
                height: "100%", 
                background: (telemetry?.performance?.lock_retention_rate || 100) > 95 ? "#0f0" : "#f00",
                transition: "width 0.2s, background 0.2s"
              }} />
            </div>
          </div>

        </div>
      </div>

      {/* 2. SCROLLABLE 2000x2000 GRAPH VIEWER */}
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "auto",
          border: "1px solid #222",
        }}
      >
        {/* THE 2000x2000 WORLD CONTAINER */}
        <div
          style={{
            width: "2000px",
            height: "2000px",
            flexShrink: 0,
            position: "relative",
            background: "#0a0a0a",
            transform: `scale(${zoomLevel})`,
            transformOrigin: "center center",
            backgroundImage: `
            linear-gradient(#1a1a1a 1px, transparent 1px),
            linear-gradient(90deg, #1a1a1a 1px, transparent 1px)
          `,
            backgroundSize: "100px 100px" /* Draw a grid line every 100px */,
          }}
        >
          {/* Axis Labels (Just a few to show scale) */}
          <div
            style={{
              position: "absolute",
              top: "10px",
              left: "10px",
              color: "#555",
            }}
          >
            (0,0)
          </div>
          <div
            style={{
              position: "absolute",
              top: "1000px",
              left: "1000px",
              color: "#555",
            }}
          >
            (1000,1000)
          </div>
          <div
            style={{
              position: "absolute",
              bottom: "10px",
              right: "10px",
              color: "#555",
            }}
          >
            (2000,2000)
          </div>

          {telemetry && (
            <>
              {/* ATMOSPHERIC DISTURBANCE OVERLAYS */}
              {atmospheric !== "Clear" && (
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "2000px",
                    height: "2000px",
                    pointerEvents: "none",
                    zIndex: 5, // Above everything
                    background:
                      atmospheric === "Haze"
                        ? "rgba(200, 200, 200, 0.5)"
                        : atmospheric === "Fog"
                        ? "radial-gradient(circle at center, rgba(255,255,255,0.6) 0%, rgba(200,200,200,0.9) 100%)"
                        : atmospheric === "Low light"
                        ? "rgba(0, 0, 0, 0.75)"
                        : atmospheric === "Rain"
                        ? "repeating-linear-gradient(105deg, transparent, transparent 10px, rgba(255,255,255,0.3) 10px, rgba(255,255,255,0.3) 12px)"
                        : "transparent",
                    transition: "background 0.5s ease",
                  }}
                />
              )}

              {/* IMAGE NOISE OVERLAYS (Only inside the Camera Viewport) */}
              {noiseType !== "None" && (
                <div
                  style={{
                    position: "absolute",
                    top: `${camY}px`,
                    left: `${camX}px`,
                    width: "640px",
                    height: "480px",
                    pointerEvents: "none",
                    zIndex: 4, // Below atmospheric, but above the camera lines
                    background: noiseType === "Salt & Pepper"
                        ? "url('data:image/svg+xml;utf8,<svg viewBox=\"0 0 200 200\" xmlns=\"http://www.w3.org/2000/svg\"><filter id=\"noiseFilter\"><feTurbulence type=\"fractalNoise\" baseFrequency=\"0.95\" numOctaves=\"3\" stitchTiles=\"stitch\"/></filter><rect width=\"100%\" height=\"100%\" filter=\"url(%23noiseFilter)\" opacity=\"0.5\"/></svg>')"
                        : noiseType === "Gaussian"
                        ? "url('data:image/svg+xml;utf8,<svg viewBox=\"0 0 200 200\" xmlns=\"http://www.w3.org/2000/svg\"><filter id=\"noiseFilter\"><feTurbulence type=\"fractalNoise\" baseFrequency=\"0.6\" numOctaves=\"3\" stitchTiles=\"stitch\"/></filter><rect width=\"100%\" height=\"100%\" filter=\"url(%23noiseFilter)\" opacity=\"0.3\"/></svg>')"
                        : "url('data:image/svg+xml;utf8,<svg viewBox=\"0 0 200 200\" xmlns=\"http://www.w3.org/2000/svg\"><filter id=\"noiseFilter\"><feTurbulence type=\"fractalNoise\" baseFrequency=\"2.0\" numOctaves=\"1\" stitchTiles=\"stitch\"/></filter><rect width=\"100%\" height=\"100%\" filter=\"url(%23noiseFilter)\" opacity=\"0.4\"/></svg>')",
                    mixBlendMode: "screen",
                  }}
                />
              )}

              {/* THE VIRTUAL CLOUDS (OBSTACLES) */}
              {telemetry.obstacles &&
                telemetry.obstacles.map((obs, i) => (
                  <div
                    key={i}
                    style={{
                      position: "absolute",
                      left: `${obs.x}px`,
                      top: `${obs.y}px`,
                      width: `${obs.w}px`,
                      height: `${obs.h}px`,
                      background:
                        "linear-gradient(180deg, rgba(200, 200, 200, 0.9) 0%, rgba(120, 120, 120, 0.9) 100%)",
                      borderRadius: "50%",
                      boxShadow:
                        "0 0 30px rgba(150, 150, 150, 0.5), inset 0 10px 20px rgba(255,255,255,0.3)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "rgba(50, 50, 50, 0.8)",
                      fontSize: "30px",
                      pointerEvents: "none",
                      zIndex: 4,
                    }}
                  >
                    ☁️
                  </div>
                ))}

              {/* THE TARGET BEACON (10x10 White Square) */}
              <div
                style={{
                  position: "absolute",
                  left: `${targetX - 5}px`, // Center the 10x10 dot
                  top: `${targetY - 5}px`,
                  width: "10px",
                  height: "10px",
                  background: "#fff",
                  boxShadow: "0 0 10px #fff", // Glowing effect
                  zIndex: 2,
                }}
              />

              {/* NLP PREDICTED PATH VISUALIZATION */}
              {telemetry?.predicted_path &&
                telemetry.predicted_path.length > 0 && (
                  <svg
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "2000px",
                      height: "2000px",
                      pointerEvents: "none",
                      zIndex: 1,
                    }}
                  >
                    <polyline
                      points={telemetry.predicted_path
                        .map((p) => `${p.x},${p.y}`)
                        .join(" ")}
                      fill="none"
                      stroke="#00c8ff"
                      strokeWidth="4"
                      strokeDasharray="10, 10"
                      style={{ filter: "drop-shadow(0 0 8px #00c8ff)" }}
                    />
                  </svg>
                )}

              {/* KALMAN COASTING PREDICTION (Pulsing Cyan Dot) */}
              {telemetry?.coasting_coord && (
                <div
                  style={{
                    position: "absolute",
                    left: `${telemetry.coasting_coord.x - 8}px`,
                    top: `${telemetry.coasting_coord.y - 8}px`,
                    width: "16px",
                    height: "16px",
                    borderRadius: "50%",
                    background: "rgba(0, 200, 255, 0.6)",
                    boxShadow: "0 0 20px #00c8ff, 0 0 40px #00c8ff",
                    zIndex: 3,
                    animation: "blink 0.5s infinite",
                  }}
                />
              )}

              {/* THE CAMERA VIEWPORT (640x480 Green Hollow Box) */}
              <div
                style={{
                  position: "absolute",
                  left: `${camX}px`,
                  top: `${camY}px`,
                  width: "640px",
                  height: "480px",
                  border: "2px solid rgba(0, 255, 0, 0.7)",
                  background: "rgba(0, 255, 0, 0.05)",
                  zIndex: 1,
                  pointerEvents: "none", // Don't block clicking
                }}
              >
                {/* Camera Crosshair (Center of the camera) */}
                <div
                  style={{
                    position: "absolute",
                    left: "320px",
                    top: "240px",
                    width: "20px",
                    height: "1px",
                    background: "rgba(0, 255, 0, 0.5)",
                    transform: "translate(-50%, -50%)",
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: "320px",
                    top: "240px",
                    width: "1px",
                    height: "20px",
                    background: "rgba(0, 255, 0, 0.5)",
                    transform: "translate(-50%, -50%)",
                  }}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
