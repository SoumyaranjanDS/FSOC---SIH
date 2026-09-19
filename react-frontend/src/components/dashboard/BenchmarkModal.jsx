function BenchmarkModal({ telemetry, onClose }) {
  const performance = telemetry?.performance || {};
  const acquisition = performance.acquisition_time ?? 0;
  const rmse = performance.global_rmse ?? performance.avg_error ?? 0;
  const retention = performance.lock_retention_rate ?? 100;
  const lossRate = Math.max(0, 100 - retention);
  const reacquisition = performance.avg_reacq_time ?? 0;
  const fps = performance.fps ?? 0;
  const hasData = fps > 0;

  let acqValue = "Waiting...";
  let acqResult = "WAITING";
  if (performance.acquisition_time !== undefined && performance.acquisition_time !== null) {
      acqValue = `${acquisition.toFixed(2)} s`;
      acqResult = acquisition <= 2 ? "✓ PASS" : "✗ FAIL";
  }

  let rmseResult = "WAITING";
  if (hasData) {
      rmseResult = rmse <= 10 ? "✓ PASS" : "✗ FAIL";
  }

  let lossResult = "WAITING";
  if (hasData) {
      lossResult = lossRate < 5 ? "✓ PASS" : "✗ FAIL";
  }

  let reacqValue = "Waiting...";
  let reacqResult = "WAITING";
  if (performance.avg_reacq_time !== undefined && performance.avg_reacq_time !== null) {
      reacqValue = `${reacquisition.toFixed(2)} s`;
      reacqResult = reacquisition <= 1 ? "✓ PASS" : "✗ FAIL";
  } else if (hasData && lossRate === 0) {
      reacqValue = "0.00 s";
      reacqResult = "✓ PASS";
  }

  const fpsResult = hasData ? (fps >= 20 ? "✓ PASS" : "✗ FAIL") : "WAITING";

  const rows = [
    ["Acquisition", acqValue, "≤ 2.00 s", acqResult],
    ["Tracking RMSE", hasData ? `${rmse.toFixed(1)} px` : "Waiting...", "≤ 10 px", rmseResult],
    ["Target Loss", hasData ? `${lossRate.toFixed(1)}%` : "Waiting...", "< 5%", lossResult],
    ["Re-acquisition", reacqValue, "≤ 1.00 s", reacqResult],
    ["Processing", hasData ? `${fps.toFixed(1)} FPS` : "Waiting...", "≥ 20 FPS", fpsResult],
  ];

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="benchmark-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="benchmark-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-heading">
          <div>
            <span className="section-label">VALIDATION REPORT</span>
            <h2 id="benchmark-title">Performance Compliance</h2>
          </div>
          <button
            className="modal-close"
            type="button"
            onClick={onClose}
            aria-label="Close benchmarks"
          >
            &times;
          </button>
        </div>
        <div className="benchmark-table">
          <div className="benchmark-table-header">
            <span>Metric</span>
            <span>Measured</span>
            <span>Requirement</span>
            <span>Result</span>
          </div>
          {rows.map(([label, value, requirement, resultString]) => {
            let statusClass = "status-bad";
            if (resultString === "✓ PASS") statusClass = "status-good";
            if (resultString === "WAITING") statusClass = "status-warn"; 
            
            return (
              <div className="benchmark-row" key={label}>
                <strong>{label}</strong>
                <span>{value}</span>
                <span>{requirement}</span>
                <b className={statusClass}>
                  {resultString}
                </b>
              </div>
            );
          })}
        </div>
        <p className="modal-note">
          Values are updated from the live simulation telemetry.
        </p>
        {telemetry?.mode === "benchmark" && (
          <div style={{ display: "flex", justifyContent: "center", marginTop: "20px" }}>
            <a
              href="http://localhost:3000/uploads/benchmark_results.csv"
              download="benchmark_results.csv"
              target="_blank"
              rel="noreferrer"
              className="button button-start"
              style={{ textDecoration: "none", padding: "10px 20px", display: "inline-block", backgroundColor: "#00e676", color: "#000" }}
            >
              📥 Download CSV Performance Report
            </a>
          </div>
        )}
      </section>
    </div>
  );
}

export default BenchmarkModal;
