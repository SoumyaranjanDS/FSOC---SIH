function BenchmarkPanel({
  benchmarkFile,
  isUploading,
  engineStatus,
  telemetry,
  onUpload,
  onStart,
  onStop,
  onReset,
}) {
  const isRunning = engineStatus === "running_benchmark";

  return (
    <aside className="dashboard-panel control-panel benchmark-panel">
      <div className="panel-kicker">VIDEO VALIDATION</div>
      <h1>Benchmark Mode</h1>
      <div className="benchmark-upload">
        <label htmlFor="benchmark-video">Input video</label>
        <input
          id="benchmark-video"
          type="file"
          accept="video/mp4,video/x-m4v,video/*"
          onChange={(event) => onUpload(event.target.files?.[0])}
          disabled={isUploading || isRunning}
        />
        {isUploading && <span className="muted">Uploading video...</span>}
        {benchmarkFile && !isUploading && (
          <span className="status-good benchmark-file-name">
            {benchmarkFile.filename}
          </span>
        )}
      </div>
      {telemetry?.mode === "benchmark" && (
        <div className="benchmark-progress">
          <div>
            <span>Frame {telemetry.frame || 0}</span>
            <span>{Math.round((telemetry.progress || 0) * 100)}%</span>
          </div>
          <div className="progress">
            <span style={{ width: `${(telemetry.progress || 0) * 100}%` }} />
          </div>
        </div>
      )}
      <div className="engine-actions">
        <button
          className="button button-start"
          type="button"
          onClick={onStart}
          disabled={!benchmarkFile || isRunning || isUploading}
        >
          START
        </button>
        <button
          className="button button-stop"
          type="button"
          onClick={onStop}
          disabled={!isRunning}
        >
          STOP
        </button>
        <button
          className="button button-restart"
          type="button"
          onClick={onReset}
          disabled={isRunning || !benchmarkFile}
        >
          RESET
        </button>
      </div>
      <div className="status-list">
        <div>
          Bridge <strong className="muted">VIDEO INPUT</strong>
        </div>
        <div>
          Engine{" "}
          <strong className={isRunning ? "status-good" : "status-bad"}>
            {isRunning ? "RUNNING" : "STOPPED"}
          </strong>
        </div>
        <div>
          Frames <strong>{telemetry?.total_frames || "-"}</strong>
        </div>
      </div>
    </aside>
  );
}

export default BenchmarkPanel;
