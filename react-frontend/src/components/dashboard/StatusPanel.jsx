function StatusPanel({ telemetry }) {
  return (
    <section className="dashboard-panel status-panel">
      <div className="panel-heading">
        <span>TRACKING STATE</span>
        <strong>{telemetry?.status || "WAITING"}</strong>
      </div>
      <p>
        Target and camera telemetry are streamed from the simulation engine.
      </p>
    </section>
  );
}

export default StatusPanel;
