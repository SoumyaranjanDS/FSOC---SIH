import { useState } from "react";
import BenchmarkModal from "./BenchmarkModal";

function PerformancePanel({ telemetry }) {
  const [showBenchmarks, setShowBenchmarks] = useState(false);
  const performance = telemetry?.performance || {};
  const retention = performance.lock_retention_rate ?? 100;
  const duration = performance.duration
    ? new Date(performance.duration * 1000).toISOString().substring(14, 19)
    : "00:00";
  const metric = (label, value, tone = "") => (
    <div className="metric">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
    </div>
  );

  return (
    <section className="dashboard-panel performance-panel">
      <div className="panel-heading">
        <span>LIVE PERFORMANCE REPORT</span>
        <strong className="status-good">
          {performance.fps?.toFixed(1) || "0.0"} FPS
        </strong>
      </div>
      <div className="metrics-grid">
        {metric("Simulation Time", duration)}
        {metric(
          "Acquisition Time",
          performance.acquisition_time
            ? `${performance.acquisition_time.toFixed(2)} s`
            : "Waiting...",
          performance.acquisition_time > 0 ? "status-good" : "muted",
        )}
        {metric(
          "Avg Tracking Error",
          performance.avg_error
            ? `${performance.avg_error.toFixed(2)} px`
            : "0.00 px",
          performance.avg_error > 10 ? "status-bad" : "status-good",
        )}
        {metric(
          "Max Tracking Error",
          performance.max_error
            ? `${performance.max_error.toFixed(2)} px`
            : "0.00 px",
          "status-warn",
        )}
      </div>
      <div className="retention">
        <div>
          <span>Lock Retention Rate</span>
          <strong className={retention > 95 ? "status-good" : "status-bad"}>
            {retention.toFixed(1)}%
          </strong>
        </div>
        <div className="progress">
          <span style={{ width: `${retention}%` }} />
        </div>
      </div>
      <div className="benchmark-trigger-row">
        <div>
          <span className="benchmark-kicker">PERFORMANCE COMPLIANCE</span>
          <strong>Mission benchmarks</strong>
        </div>
        <button
          className="benchmark-button"
          type="button"
          onClick={() => setShowBenchmarks(true)}
        >
          VIEW ALL BENCHMARKS <span aria-hidden="true">-&gt;</span>
        </button>
      </div>
      {showBenchmarks && (
        <BenchmarkModal
          telemetry={telemetry}
          onClose={() => setShowBenchmarks(false)}
        />
      )}
    </section>
  );
}

export default PerformancePanel;
