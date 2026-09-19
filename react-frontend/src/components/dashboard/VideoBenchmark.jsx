import { useEffect, useRef, useState } from "react";
import BenchmarkModal from "./BenchmarkModal";
import BenchmarkPanel from "./BenchmarkPanel";

function useVideoBenchmark({
  socket,
  telemetry,
  engineStatus,
  camX,
  camY,
  onClearTelemetry,
  config,
  noiseType,
  setNoiseType,
  noiseStdDev,
  setNoiseStdDev,
  cameraJitter,
  setCameraJitter,
  platformMotion,
  setPlatformMotion,
  onConfigChange,
}) {
  const [benchmarkFile, setBenchmarkFile] = useState(null);
  const [benchmarkSummary, setBenchmarkSummary] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  // Own zoom state — independent of simulation zoom, never resets on start/stop
  const [benchmarkZoom, setBenchmarkZoom] = useState(0.4);
  // Real world dimensions of the video, set instantly on upload so aspect ratio is preserved
  const [worldDims, setWorldDims] = useState({ w: 2000, h: 2000 });
  const videoRef = useRef(null);

  const isRunning = engineStatus === "running_benchmark";

  // Track video FPS so we can seek to the exact frame Python just processed
  const videoFpsRef = useRef(30);

  useEffect(() => {
    const handleBenchmarkComplete = (data) => {
      if (videoRef.current) videoRef.current.pause();
      setBenchmarkSummary(data.summary);
    };

    // FIX 1+5: Play video ONLY when Python signals it is ready (not before)
    const handleBenchmarkStarted = (data) => {
      videoFpsRef.current = data.video_fps || 30;
      if (videoRef.current) {
        videoRef.current.currentTime = 0;
        videoRef.current.play().catch(() => {});
      }
    };

    socket.on("benchmark_complete", handleBenchmarkComplete);
    socket.on("benchmark_started", handleBenchmarkStarted);
    return () => {
      socket.off("benchmark_complete", handleBenchmarkComplete);
      socket.off("benchmark_started", handleBenchmarkStarted);
    };
  }, [socket]);

  useEffect(() => {
    // Pause when not running
    if (!isRunning && videoRef.current && !videoRef.current.paused) {
      videoRef.current.pause();
    }
  }, [isRunning]);

  const handleUpload = async (file) => {
    if (!file) return;
    setUploadError(null);
    setIsUploading(true);
    setBenchmarkFile(null);
    const formData = new FormData();
    formData.append("video", file);
    try {
      const res = await fetch("http://localhost:3000/upload_video", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      setBenchmarkFile(await res.json());
    } catch (err) {
      console.error("Upload failed", err);
      setUploadError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const start = () => {
    if (!benchmarkFile || isRunning) return;
    setBenchmarkSummary(null);
    onClearTelemetry();
    // Reset video to frame 0 but do NOT play yet — wait for benchmark_started from server
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
    }
    socket.emit("start_benchmark", { video_path: benchmarkFile.path });
    setTimeout(() => {
      if (onConfigChange && config) onConfigChange(config);
    }, 500);
  };

  const stop = () => {
    if (videoRef.current) videoRef.current.pause();
    socket.emit("stop_benchmark");
  };

  const reset = () => {
    stop();
    setBenchmarkSummary(null);
    setBenchmarkFile(null);
    setUploadError(null);
    onClearTelemetry();
    // Reset video dims so next upload starts fresh
    setWorldDims({ w: 2000, h: 2000 });
    if (videoRef.current) videoRef.current.currentTime = 0;
  };

  // ─── PANEL (left sidebar) ───────────────────────────────────────────────────
  const panel = (
    <BenchmarkPanel
      benchmarkFile={benchmarkFile}
      isUploading={isUploading}
      uploadError={uploadError}
      engineStatus={engineStatus}
      telemetry={telemetry}
      onUpload={handleUpload}
      onStart={start}
      onStop={stop}
      onReset={reset}
      zoomLevel={benchmarkZoom}
      setZoomLevel={setBenchmarkZoom}
      noiseType={noiseType}
      setNoiseType={setNoiseType}
      noiseStdDev={noiseStdDev}
      setNoiseStdDev={setNoiseStdDev}
      cameraJitter={cameraJitter}
      setCameraJitter={setCameraJitter}
      platformMotion={platformMotion}
      setPlatformMotion={setPlatformMotion}
      onConfigChange={onConfigChange}
    />
  );

  // ─── WORLD STAGE (center canvas) ────────────────────────────────────────────
  // Uses worldDims state which is updated immediately upon video upload.
  // This prevents the video from being squeezed and prevents size jumping at START.
  const worldW = worldDims.w;
  const worldH = worldDims.h;

  // FIX 2: camera position comes directly from live benchmark telemetry
  const camHudX = telemetry?.camera?.x ?? 0;
  const camHudY = telemetry?.camera?.y ?? 0;

  const stage = (
    <main className="simulation-stage">
      {/* THE WORLD — same pixel-accurate container as simulation */}
      <div
        style={{
          width: `${worldW}px`,
          height: `${worldH}px`,
          flexShrink: 0,
          position: "relative",
          background: "#0a0a0a",
          transform: `scale(${benchmarkZoom})`,
          transformOrigin: "center center",
          backgroundImage: "none",
        }}
      >
        {/* Video as the world background */}
        {benchmarkFile && (
          <video
            ref={videoRef}
            src={benchmarkFile.url}
            onLoadedMetadata={(e) => {
              setWorldDims({
                w: e.target.videoWidth,
                h: e.target.videoHeight,
              });
            }}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              objectFit: "fill",
              zIndex: 0,
              pointerEvents: "none",
            }}
            muted
            playsInline
          />
        )}

        {/* Empty state */}
        {!benchmarkFile && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              color: "#2a4a4d",
              fontSize: 14,
              gap: 8,
            }}
          >
            <div style={{ fontSize: 36 }}>🎬</div>
            <div>Upload a video in the panel to begin</div>
          </div>
        )}

        {/* FIX 4: Frame-sync — seek video to the exact frame Python just processed */}
        {telemetry?.frame && videoRef.current && isRunning && (() => {
          const target = telemetry.frame / videoFpsRef.current;
          // Only seek if more than 0.3s out of sync to avoid jitter
          if (Math.abs(videoRef.current.currentTime - target) > 0.3) {
            videoRef.current.currentTime = target;
          }
          return null;
        })()}

        {/* Live overlays — only render when telemetry is flowing */}
        {telemetry && (
          <>
            {/* Centroid trail (pink dashed path across the world) */}
            {telemetry.centroid_trail?.length > 0 && (
              <svg
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: `${worldW}px`,
                  height: `${worldH}px`,
                  pointerEvents: "none",
                  zIndex: 2,
                  overflow: "visible",
                }}
              >
                <polyline
                  points={telemetry.centroid_trail
                    .map((p) => `${p.x},${p.y}`)
                    .join(" ")}
                  fill="none"
                  stroke="#ff00ff"
                  strokeWidth="2"
                  strokeDasharray="4, 4"
                />
              </svg>
            )}

            {/* Live centroid dot */}
            {telemetry.centroid && (
              <div
                style={{
                  position: "absolute",
                  left: `${telemetry.centroid.x - 4}px`,
                  top: `${telemetry.centroid.y - 4}px`,
                  width: "8px",
                  height: "8px",
                  background: "#ff00ff",
                  borderRadius: "50%",
                  boxShadow: "0 0 10px #ff00ff",
                  zIndex: 3,
                  pointerEvents: "none",
                }}
              />
            )}

            {/* Kalman predicted path */}
            {telemetry.predicted_path?.length > 0 && (
              <svg
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: `${worldW}px`,
                  height: `${worldH}px`,
                  pointerEvents: "none",
                  zIndex: 2,
                  overflow: "visible",
                }}
              >
                <polyline
                  points={telemetry.predicted_path
                    .map((p) => `${p.x},${p.y}`)
                    .join(" ")}
                  fill="none"
                  stroke="#00c8ff"
                  strokeWidth="3"
                  strokeDasharray="10, 6"
                />
              </svg>
            )}

            {/* Kalman coasting position */}
            {telemetry.coasting_coord && (
              <div
                style={{
                  position: "absolute",
                  left: `${telemetry.coasting_coord.x - 8}px`,
                  top: `${telemetry.coasting_coord.y - 8}px`,
                  width: "16px",
                  height: "16px",
                  border: "2px solid #00c8ff",
                  borderRadius: "50%",
                  boxShadow: "0 0 15px #00c8ff",
                  animation: "blink 1s infinite",
                  zIndex: 3,
                  pointerEvents: "none",
                }}
              />
            )}

            {/* PTZ Camera Viewport HUD — FIX 2: uses telemetry camera position */}
            <div
              style={{
                position: "absolute",
                left: `${camHudX}px`,
                top: `${camHudY}px`,
                width: "640px",
                height: "480px",
                border: "1px solid rgba(0, 255, 0, 0.2)",
                background: "rgba(0, 255, 0, 0.02)",
                boxShadow: "inset 0 0 50px rgba(0, 255, 0, 0.05)",
                zIndex: 4,
                pointerEvents: "none",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                padding: "15px",
                boxSizing: "border-box",
              }}
            >
              {/* Corner brackets */}
              <div
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "30px",
                  height: "30px",
                  borderTop: "3px solid #00ff00",
                  borderLeft: "3px solid #00ff00",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  top: 0,
                  right: 0,
                  width: "30px",
                  height: "30px",
                  borderTop: "3px solid #00ff00",
                  borderRight: "3px solid #00ff00",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  bottom: 0,
                  left: 0,
                  width: "30px",
                  height: "30px",
                  borderBottom: "3px solid #00ff00",
                  borderLeft: "3px solid #00ff00",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  bottom: 0,
                  right: 0,
                  width: "30px",
                  height: "30px",
                  borderBottom: "3px solid #00ff00",
                  borderRight: "3px solid #00ff00",
                }}
              />

              {/* Top HUD row */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  color: "#00ff00",
                  fontFamily: "monospace",
                  fontSize: "14px",
                  fontWeight: "bold",
                  textShadow: "0 0 5px #00ff00",
                }}
              >
                <div
                  style={{ display: "flex", alignItems: "center", gap: "8px" }}
                >
                  <div
                    style={{
                      width: "12px",
                      height: "12px",
                      borderRadius: "50%",
                      background: "#ff0000",
                      animation: "blink 1s infinite",
                    }}
                  />
                  REC
                </div>
                <div>FOV: 4.0° | PTZ-TRACK</div>
                <div>F: {telemetry.frame || 0}</div>
              </div>

              {/* Center crosshair */}
              <div
                style={{
                  position: "absolute",
                  left: "50%",
                  top: "50%",
                  transform: "translate(-50%, -50%)",
                  width: "40px",
                  height: "40px",
                  border: "1px solid rgba(0, 255, 0, 0.4)",
                  borderRadius: "50%",
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    left: "20px",
                    top: "-10px",
                    width: "1px",
                    height: "60px",
                    background: "rgba(0, 255, 0, 0.6)",
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: "-10px",
                    top: "20px",
                    width: "60px",
                    height: "1px",
                    background: "rgba(0, 255, 0, 0.6)",
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: "19px",
                    top: "19px",
                    width: "2px",
                    height: "2px",
                    background: "#00ff00",
                  }}
                />
              </div>

              {/* Target lock box */}
              {telemetry.status === "TRACKING" && telemetry.error && (
                <div
                  style={{
                    position: "absolute",
                    left: `${320 + (telemetry.error.x || 0) - 20}px`,
                    top: `${240 + (telemetry.error.y || 0) - 20}px`,
                    width: "40px",
                    height: "40px",
                    border: "2px dashed #00ff00",
                    animation: "spin 10s linear infinite",
                  }}
                />
              )}

              {/* Bottom HUD row */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  color: "#00ff00",
                  fontFamily: "monospace",
                  fontSize: "12px",
                  textShadow: "0 0 5px #00ff00",
                  alignItems: "flex-end",
                }}
              >
                <div>
                  ERR X: {telemetry.error?.x?.toFixed(1) ?? "0.0"}
                  <br />
                  ERR Y: {telemetry.error?.y?.toFixed(1) ?? "0.0"}
                </div>
                <div
                  style={{
                    textAlign: "center",
                    fontSize: "16px",
                    fontWeight: "bold",
                  }}
                >
                  {telemetry.status ?? "WAITING"}
                </div>
                <div style={{ textAlign: "right" }}>
                  RMSE: {telemetry.error?.rmse?.toFixed(2) ?? "0.00"}
                  <br />
                  SPD: 5°/s LIMIT
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </main>
  );

  // ─── RESULTS MODAL ──────────────────────────────────────────────────────────
  const modal = benchmarkSummary ? (
    <BenchmarkModal
      telemetry={{
        performance: {
          acquisition_time: benchmarkSummary.acquisition_time_sec,
          avg_error: benchmarkSummary.avg_centroid_error,
          max_error: benchmarkSummary.max_centroid_error,
          lock_retention_rate: benchmarkSummary.lock_retention_rate,
          reacquisition_time: benchmarkSummary.avg_reacquisition_sec,
          fps: benchmarkSummary.processing_fps,
        },
      }}
      onClose={() => setBenchmarkSummary(null)}
    />
  ) : null;

  return { panel, stage, modal };
}

export default useVideoBenchmark;
