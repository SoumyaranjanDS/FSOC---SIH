import { useState } from "react";
import BenchmarkModal from "./BenchmarkModal";

function PerformancePanel({ telemetry }) {
  const [showBenchmarks, setShowBenchmarks] = useState(false);
  const performance = telemetry?.performance || {};
  const retention = performance.lock_retention_rate ?? 100;
  const duration = performance.duration
    ? new Date(performance.duration * 1000).toISOString().substring(14, 19)
    : "00:00";
  const metric = (label, value, tone = "", complianceText = null, isPassing = null) => (
    <div className="metric" style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      <span>{label}</span>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <strong className={tone}>{value}</strong>
        {complianceText && (
          <span className={isPassing ? "status-good" : "status-bad"} style={{ fontSize: "0.75rem" }}>
            {complianceText} {isPassing ? "✓" : "✗"}
          </span>
        )}
      </div>
    </div>
  );

  const fps = performance.fps || 0;
  const fpsPassed = fps >= 20;
  
  const rmse = performance.global_rmse || 0;
  const rmsePassed = rmse <= 10;
  
  const targetLoss = 100 - retention;
  const lossPassed = targetLoss < 5;

  return (
    <section className="dashboard-panel performance-panel">
      <div className="panel-heading">
        <span>LIVE PERFORMANCE REPORT</span>
        <strong className={fpsPassed ? "status-good" : "status-bad"}>
          {fps.toFixed(1)} FPS
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
          "RMSE (Track Error)",
          `${rmse.toFixed(2)} px`,
          rmsePassed ? "status-good" : "status-bad",
          "Req ≤ 10",
          rmsePassed
        )}
        {metric(
          "Max Tracking Error",
          performance.max_error
            ? `${performance.max_error.toFixed(2)} px`
            : "0.00 px",
          "status-warn",
        )}
      </div>
      <div className="retention" style={{ marginTop: "16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
          <span>Target Loss Rate</span>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <span className={lossPassed ? "status-good" : "status-bad"} style={{ fontSize: "0.8rem" }}>
              (Req &lt; 5%) {lossPassed ? "✓" : "✗"}
            </span>
            <strong className={lossPassed ? "status-good" : "status-bad"}>
              {targetLoss.toFixed(1)}%
            </strong>
          </div>
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
