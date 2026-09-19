import { useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";
import "./App.css";
import ControlPanel from "./components/dashboard/ControlPanel";
import LogsPanel from "./components/dashboard/LogsPanel";
import PerformancePanel from "./components/dashboard/PerformancePanel";
import RmsePanel from "./components/dashboard/RmsePanel";
import SimulationCanvas from "./components/dashboard/SimulationCanvas";
import WebcamCanvas from "./components/dashboard/WebcamCanvas";
import StatusPanel from "./components/dashboard/StatusPanel";
import TopNav from "./components/dashboard/TopNav";
import useVideoBenchmark from "./components/dashboard/VideoBenchmark";

const socket = io("http://localhost:3000");

function App() {
  const [telemetry, setTelemetry] = useState(null);
  const [connected, setConnected] = useState(false);
  const [logs, setLogs] = useState([]);
  const [engineStatuses, setEngineStatuses] = useState({
    simulation: "stopped",
    benchmark: "stopped",
    webcam: "stopped",
  });
  const [operatingMode, setOperatingModeState] = useState("simulation");
  const operatingModeRef = useRef("simulation");
  const [targetSpeed, setTargetSpeed] = useState(15);
  const [targetPath, setTargetPath] = useState("Random");
  const [obstaclesEnabled, setObstaclesEnabled] = useState(false);
  const [dualTargetEnabled, setDualTargetEnabled] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(0.4);
  const [noiseType, setNoiseType] = useState("None");
  const [noiseStdDev, setNoiseStdDev] = useState(20);
  const [cameraJitter, setCameraJitter] = useState(0);
  const [atmospheric, setAtmospheric] = useState("Clear");
  const [platformMotion, setPlatformMotion] = useState("None");
  const rmseCanvasRef = useRef(null);
  const previousTelemetryRef = useRef({});
  const camX = telemetry?.camera?.x || 0;
  const camY = telemetry?.camera?.y || 0;

  const benchmark = useVideoBenchmark({
    socket,
    telemetry,
    engineStatus: engineStatuses.benchmark,
    camX,
    camY,
    onClearTelemetry: () => {
      setTelemetry(null);
      setLogs([]);
    },
    config: {
      noise_type: noiseType,
      noise_std_dev: noiseStdDev,
      camera_jitter: cameraJitter,
      platform_motion: platformMotion,
    },
    noiseType,
    setNoiseType,
    noiseStdDev,
    setNoiseStdDev,
    cameraJitter,
    setCameraJitter,
    platformMotion,
    setPlatformMotion,
    onConfigChange: (c) => socket.emit("set_config", c),
  });

  const setOperatingMode = (mode) => {
    setOperatingModeState(mode);
    operatingModeRef.current = mode;
    setTelemetry(null);
    setLogs([]);
  };

  useEffect(() => {
    const handleConnect = () => setConnected(true);
    const handleDisconnect = () => setConnected(false);
    const handleEngineStatus = (statusData) => {
      if (statusData && statusData.mode) {
        setEngineStatuses((prev) => ({
          ...prev,
          [statusData.mode]: statusData.status,
        }));
      } else if (typeof statusData === "string") {
        setEngineStatuses((prev) => ({
          ...prev,
          [operatingModeRef.current]: statusData,
        }));
      }
    };
    const handleTelemetry = (data) => {
      if (data.mode && operatingModeRef.current !== data.mode)
        return;

      setTelemetry(data);
      const previous = previousTelemetryRef.current;
      const frame = formatSimulationTime(data.performance?.duration);
      const events = [];
      if (data.log) events.push(data.log);
      if (!previous.hasTarget && data.target)
        events.push("BEACON DETECTED - TRACK LOCK ACQUIRED");
      if (data.obstacles?.length && !previous.hasObstacles) {
        events.push(
          `OBJECT DETECTED - ${data.obstacles.length} VIRTUAL OBSTACLE${data.obstacles.length === 1 ? "" : "S"}`,
        );
      }
      if (previous.status && previous.status !== data.status && data.status)
        events.push(`TRACKING STATE: ${data.status}`);
      if (
        data.performance?.acquisition_time > 0 &&
        !previous.acquisitionReported
      ) {
        events.push(
          `ACQUISITION COMPLETE - ${data.performance.acquisition_time.toFixed(2)} s`,
        );
      }
      if (
        data.performance?.reacquisition_time > 0 &&
        !previous.reacquisitionReported
      ) {
        events.push(
          `RE-ACQUISITION COMPLETE - ${data.performance.reacquisition_time.toFixed(2)} s`,
        );
      }
      if (
        Math.floor(data.performance?.duration || 0) >
        Math.floor(previous.duration || 0)
      ) {
        events.push(`SIMULATION TIME ${frame}`);
      }
      if (events.length)
        setLogs((current) =>
          [...current, ...events.map((event) => `[${frame}] ${event}`)].slice(
            -80,
          ),
        );
      previousTelemetryRef.current = {
        hasTarget: Boolean(data.target),
        hasObstacles: Boolean(data.obstacles?.length),
        status: data.status,
        duration: data.performance?.duration || 0,
        acquisitionReported: Boolean(data.performance?.acquisition_time > 0),
        reacquisitionReported: Boolean(
          data.performance?.reacquisition_time > 0,
        ),
      };
      drawRmse(data.rmse_history, rmseCanvasRef.current);
    };
    socket.on("connect", handleConnect);
    socket.on("disconnect", handleDisconnect);
    socket.on("engine_status", handleEngineStatus);
    socket.on("telemetry", handleTelemetry);
    return () => {
      socket.off("connect", handleConnect);
      socket.off("disconnect", handleDisconnect);
      socket.off("engine_status", handleEngineStatus);
      socket.off("telemetry", handleTelemetry);
    };
  }, []);

  const sendConfig = (config) => socket.emit("set_config", config);
  const sendEngineCommand = (action) => {
    if (operatingModeRef.current === "webcam") {
      if (action === "start") socket.emit("start_webcam");
      if (action === "stop") socket.emit("stop_webcam");
      if (action === "restart") {
        socket.emit("stop_webcam");
        setTimeout(() => socket.emit("start_webcam"), 500);
      }
      return;
    }

    socket.emit("engine_control", action);
    if (action === "start" || action === "restart") {
      setTimeout(
        () =>
          sendConfig({
            target_speed: targetSpeed,
            target_path: targetPath,
            obstacles_enabled: obstaclesEnabled,
            dual_target: dualTargetEnabled,
            noise_type: noiseType,
            noise_std_dev: noiseStdDev,
            camera_jitter: cameraJitter,
            atmospheric,
            platform_motion: platformMotion,
          }),
        500,
      );
    }
  };

  const targetX = telemetry?.target?.x || 0;
  const targetY = telemetry?.target?.y || 0;

  return (
    <div className="dashboard-shell">
      <TopNav connected={connected} />
      <div className="dashboard-body">
        {operatingMode === "benchmark" ? (
          benchmark.panel
        ) : (
          <ControlPanel
            connected={connected}
            operatingMode={operatingMode}
            engineStatus={engineStatuses[operatingMode]}
            status={telemetry?.status || "WAITING"}
            targetX={targetX}
            targetY={targetY}
            camX={camX}
            camY={camY}
            targetSpeed={targetSpeed}
            setTargetSpeed={setTargetSpeed}
            targetPath={targetPath}
            setTargetPath={setTargetPath}
            obstaclesEnabled={obstaclesEnabled}
            setObstaclesEnabled={setObstaclesEnabled}
            dualTargetEnabled={dualTargetEnabled}
            setDualTargetEnabled={setDualTargetEnabled}
            zoomLevel={zoomLevel}
            setZoomLevel={setZoomLevel}
            noiseType={noiseType}
            setNoiseType={setNoiseType}
            noiseStdDev={noiseStdDev}
            setNoiseStdDev={setNoiseStdDev}
            cameraJitter={cameraJitter}
            setCameraJitter={setCameraJitter}
            atmospheric={atmospheric}
            setAtmospheric={setAtmospheric}
            platformMotion={platformMotion}
            setPlatformMotion={setPlatformMotion}
            onCommand={sendEngineCommand}
            onConfigChange={sendConfig}
          />
        )}
        <div className="dashboard-content">
          <div className="mode-switcher">
            <button
              className={operatingMode === "simulation" ? "active" : ""}
              onClick={() => setOperatingMode("simulation")}
            >
              SIMULATION
            </button>
            <button
              className={operatingMode === "webcam" ? "active" : ""}
              onClick={() => setOperatingMode("webcam")}
            >
              LIVE WEBCAM
            </button>
            <button
              className={operatingMode === "benchmark" ? "active" : ""}
              onClick={() => setOperatingMode("benchmark")}
            >
              VIDEO BENCHMARK
            </button>
          </div>
          <StatusPanel telemetry={telemetry} />
          {operatingMode === "benchmark" ? (
            benchmark.stage
          ) : operatingMode === "webcam" ? (
            <WebcamCanvas engineStatus={engineStatuses.webcam} />
          ) : (
            <SimulationCanvas
              telemetry={telemetry}
              zoomLevel={zoomLevel}
              atmospheric={atmospheric}
              noiseType={noiseType}
              camX={camX}
              camY={camY}
              targetX={targetX}
              targetY={targetY}
            />
          )}
        </div>
        <div className="dashboard-sidebar">
          <LogsPanel logs={logs} />
          <PerformancePanel telemetry={telemetry} />
          <RmsePanel canvasRef={rmseCanvasRef} telemetry={telemetry} />
        </div>
      </div>
      {benchmark.modal}
    </div>
  );
}

function formatSimulationTime(seconds = 0) {
  const totalSeconds = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  return `T+${minutes}:${(totalSeconds % 60).toFixed(2).padStart(5, "0")}`;
}

function drawRmse(history, canvas) {
  if (!history?.length || !canvas) return;
  const context = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const maxValue = Math.max(...history, 50);
  context.clearRect(0, 0, width, height);
  context.fillStyle = "#081013";
  context.fillRect(0, 0, width, height);
  context.strokeStyle = "#173036";
  for (let index = 0; index <= 4; index += 1) {
    const y = (height / 4) * index;
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(width, y);
    context.stroke();
  }
  context.beginPath();
  history.forEach((value, index) => {
    const x = (index / (history.length - 1 || 1)) * width;
    const y = height - (value / maxValue) * height;
    if (index === 0) context.moveTo(x, y);
    else context.lineTo(x, y);
  });
  context.strokeStyle = "#55e6b2";
  context.lineWidth = 2;
  context.stroke();
}

export default App;
