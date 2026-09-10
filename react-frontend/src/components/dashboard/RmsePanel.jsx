function RmsePanel({ canvasRef, telemetry }) {
  const disturbed = telemetry?.env_mode && telemetry.env_mode !== "Clear";
  return (
    <section className="dashboard-panel rmse-panel">
      <div className="panel-heading">
        <span>TRACKING ERROR / RMSE</span>
        <strong className={disturbed ? "status-bad" : "status-good"}>
          {telemetry?.env_mode || "CLEAR"}
        </strong>
      </div>
      <canvas ref={canvasRef} width="370" height="90" />
    </section>
  );
}

export default RmsePanel;
