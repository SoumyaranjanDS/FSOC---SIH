import { useEffect, useRef } from "react";

function LogsPanel({ logs }) {
  const logViewportRef = useRef(null);

  useEffect(() => {
    const viewport = logViewportRef.current;
    if (viewport) viewport.scrollTop = viewport.scrollHeight;
  }, [logs]);

  return (
    <section className="dashboard-panel logs-panel">
      <div className="panel-heading">
        <span>EVENT LOG</span>
        <span className="live-dot">LIVE</span>
      </div>
      <div className="logs-list" ref={logViewportRef} aria-live="polite">
        {logs.length === 0 ? (
          <span className="muted">Waiting for AI events...</span>
        ) : (
          logs.map((log, index) => (
            <span key={`${log}-${index}`} className={getLogClass(log)}>
              {log}
            </span>
          ))
        )}
      </div>
    </section>
  );
}

function getLogClass(log) {
  if (log.includes("DETECTED")) return "log-detected";
  if (log.includes("LOST")) return "log-danger";
  if (log.includes("DISTURBED")) return "log-warn";
  if (log.includes("REACQUIRING")) return "log-magenta";
  if (log.includes("ACQUIRING")) return "log-info";
  return "log-good";
}

export default LogsPanel;
