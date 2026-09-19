function BenchmarkPanel({
  benchmarkFile,
  isUploading,
  uploadError,
  engineStatus,
  telemetry,
  onUpload,
  onStart,
  onStop,
  onReset,
  zoomLevel,
  setZoomLevel,
  noiseType, setNoiseType,
  noiseStdDev, setNoiseStdDev,
  cameraJitter, setCameraJitter,
  platformMotion, setPlatformMotion,
  onConfigChange,
}) {
  const isRunning = engineStatus === "running_benchmark";
  const isLoading = engineStatus === "benchmark_loading";
  const isBusy = isRunning || isLoading;

  const update = (key, value, setter) => {
    if (setter) setter(value);
    if (onConfigChange) onConfigChange({ [key]: value });
  };

  return (
    <aside className="dashboard-panel control-panel benchmark-panel">
      <div className="panel-kicker">VIDEO VALIDATION</div>
      <h1>Benchmark Mode</h1>

      {/* Upload zone */}
      <div className="benchmark-upload">
        <label className="benchmark-upload-label" htmlFor="benchmark-video">
          {isUploading
            ? "⏳ Uploading..."
            : benchmarkFile
              ? "✅ Video ready — re-upload to change"
              : "📁 Select video file"}
        </label>
        <input
          id="benchmark-video"
          type="file"
          accept="video/mp4,video/x-m4v,video/*"
          onChange={(event) => onUpload(event.target.files?.[0])}
          disabled={isUploading || isRunning}
          style={{ display: "none" }}
        />
        {uploadError && (
          <span className="status-bad" style={{ fontSize: 10 }}>
            ⚠ {uploadError}
          </span>
        )}
        {benchmarkFile && !isUploading && (
          <span className="status-good benchmark-file-name">
            {benchmarkFile.filename}
          </span>
        )}
      </div>

      {/* Progress bar — only visible during run */}
      {isRunning && telemetry?.mode === "benchmark" && (
        <div className="benchmark-progress">
          <div>
            <span>Frame {telemetry.frame || 0} / {telemetry.total_frames || "?"}</span>
            <span>{Math.round((telemetry.progress || 0) * 100)}%</span>
          </div>
          <div className="progress">
            <span style={{ width: `${(telemetry.progress || 0) * 100}%` }} />
          </div>
        </div>
      )}

      {/* Engine actions */}
      <div className="engine-actions">
        <button
          className="button button-start"
          type="button"
          onClick={onStart}
          disabled={!benchmarkFile || isBusy || isUploading}
        >
          ▶ START
        </button>
        <button
          className="button button-stop"
          type="button"
          onClick={onStop}
          disabled={!isBusy}
        >
          ■ STOP
        </button>
        <button
          className="button button-restart"
          type="button"
          onClick={onReset}
          disabled={isBusy}
        >
          ↺ RESET
        </button>
      </div>

      {/* Telemetry Dashboard */}
      <div className="status-list telemetry-dashboard">
        <div className="section-label" style={{ marginBottom: "8px", borderBottom: "1px solid #333", paddingBottom: "4px" }}>
          FSOC TRACKING TELEMETRY
        </div>
        
        {telemetry?.performance ? (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
              <span className="muted">FPS</span>
              <span>
                <strong>{telemetry.performance.fps}</strong>
                <span className={telemetry.performance.fps >= 20 ? "status-good" : "status-bad"} style={{ marginLeft: "8px", fontSize: "0.85em" }}>
                   (≥20) {telemetry.performance.fps >= 20 ? "✓" : "✗"}
                </span>
              </span>
            </div>
            
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
              <span className="muted">Avg Error</span>
              <span><strong>{telemetry.performance.avg_error}</strong> px</span>
            </div>
            
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
              <span className="muted">RMSE</span>
              <span>
                <strong>{telemetry.performance.global_rmse || 0}</strong> px
                <span className={(telemetry.performance.global_rmse || 0) <= 10 ? "status-good" : "status-bad"} style={{ marginLeft: "8px", fontSize: "0.85em" }}>
                   (≤10) {(telemetry.performance.global_rmse || 0) <= 10 ? "✓" : "✗"}
                </span>
              </span>
            </div>
            
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
              <span className="muted">Max Error</span>
              <span><strong>{telemetry.performance.max_error}</strong> px</span>
            </div>
            
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
              <span className="muted">Target Loss</span>
              <span>
                <strong>{(100 - telemetry.performance.lock_retention_rate).toFixed(1)}</strong> %
                <span className={(100 - telemetry.performance.lock_retention_rate) < 5 ? "status-good" : "status-bad"} style={{ marginLeft: "8px", fontSize: "0.85em" }}>
                   (&lt;5%) {(100 - telemetry.performance.lock_retention_rate) < 5 ? "✓" : "✗"}
                </span>
              </span>
            </div>
            
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
              <span className="muted">Acquisition</span>
              <span><strong>{telemetry.performance.acquisition_time || "—"}</strong> s</span>
            </div>
            
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
              <span className="muted">Re-Acquisition</span>
              <span><strong>{telemetry.performance.avg_reacq_time || "—"}</strong> s</span>
            </div>
            
            <div style={{ marginTop: "12px", paddingTop: "8px", borderTop: "1px solid #333", display: "flex", justifyContent: "space-between" }}>
               <span>Tracking State:</span>
               <strong className={telemetry?.status === "TRACKING" ? "status-good" : "status-warn"}>{telemetry?.status}</strong>
            </div>
          </>
        ) : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Engine Status:</span>
              <strong className={isRunning ? "status-good" : isLoading ? "status-warn" : "status-bad"}>
                {isRunning ? "RUNNING" : isLoading ? "LOADING…" : "STOPPED"}
              </strong>
            </div>
            <div className="muted" style={{ marginTop: "8px" }}>Waiting for telemetry...</div>
          </>
        )}
      </div>

      {/* Disturbances & Zoom */}
      <div className="config-section">
        <div className="section-label">VIEW</div>

        <label>Zoom: {Math.round(zoomLevel * 100)}%</label>
        <input
          type="range"
          min="0.1"
          max="1.5"
          step="0.05"
          value={zoomLevel}
          onChange={(e) => setZoomLevel(parseFloat(e.target.value))}
        />

        <div className="section-label">CAMERA FILTERS</div>

        <label>Image Noise</label>
        <select
          value={noiseType}
          onChange={(e) => update("noise_type", e.target.value, setNoiseType)}
        >
          <option>None</option>
          <option value="Salt & Pepper">Salt &amp; Pepper</option>
          <option>Gaussian</option>
          <option>Poisson</option>
        </select>

        {noiseType !== "None" && (
          <>
            <label>Noise Intensity: {noiseStdDev}</label>
            <input
              type="range"
              min="1"
              max="100"
              value={noiseStdDev}
              onChange={(e) =>
                update("noise_std_dev", parseInt(e.target.value, 10), setNoiseStdDev)
              }
            />
          </>
        )}

        <label>Camera Jitter: ±{cameraJitter}px</label>
        <input
          type="range"
          min="0"
          max="50"
          value={cameraJitter}
          onChange={(e) =>
            update("camera_jitter", parseInt(e.target.value, 10), setCameraJitter)
          }
        />

        <div className="section-label">PLATFORM MOTION</div>
        <select
          value={platformMotion}
          onChange={(e) => update("platform_motion", e.target.value, setPlatformMotion)}
        >
          <option>None</option>
          <option>Linear</option>
          <option>Circular</option>
          <option>Random</option>
          <option>Figure of 8</option>
          <option>Spiral</option>
        </select>
      </div>
    </aside>
  );
}

export default BenchmarkPanel;
