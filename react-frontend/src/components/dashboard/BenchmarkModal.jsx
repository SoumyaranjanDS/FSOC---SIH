function BenchmarkModal({ telemetry, onClose }) {
  const performance = telemetry?.performance || {};
  const acquisition = performance.acquisition_time ?? 0;
  const rmse = performance.avg_error ?? 0;
  const retention = performance.lock_retention_rate ?? 100;
  const lossRate = Math.max(0, 100 - retention);
  const reacquisition = performance.reacquisition_time ?? 0;
  const fps = performance.fps ?? 0;
  const rows = [
    [
      "Acquisition",
      acquisition ? `${acquisition.toFixed(2)} s` : "Waiting...",
      "≤ 2.00 s",
      acquisition > 0 && acquisition <= 2,
    ],
    ["Tracking RMSE", `${rmse.toFixed(1)} px`, "≤ 10 px", rmse <= 10],
    ["Target Loss", `${lossRate.toFixed(1)}%`, "< 5%", lossRate < 5],
    [
      "Re-acquisition",
      reacquisition ? `${reacquisition.toFixed(2)} s` : "Waiting...",
      "≤ 1.00 s",
      reacquisition > 0 && reacquisition <= 1,
    ],
    ["Processing", `${fps.toFixed(1)} FPS`, "≥ 20 FPS", fps >= 20],
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
          {rows.map(([label, value, requirement, passed]) => (
            <div className="benchmark-row" key={label}>
              <strong>{label}</strong>
              <span>{value}</span>
              <span>{requirement}</span>
              <b className={passed ? "status-good" : "status-bad"}>
                {passed ? "✓ PASS" : "WAITING"}
              </b>
            </div>
          ))}
        </div>
        <p className="modal-note">
          Values are updated from the live simulation telemetry.
        </p>
      </section>
    </div>
  );
}

export default BenchmarkModal;
