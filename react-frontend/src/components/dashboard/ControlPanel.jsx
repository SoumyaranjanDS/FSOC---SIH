function ControlPanel({
  connected,
  engineStatus,
  status,
  targetX,
  targetY,
  camX,
  camY,
  targetSpeed,
  setTargetSpeed,
  targetPath,
  setTargetPath,
  obstaclesEnabled,
  setObstaclesEnabled,
  dualTargetEnabled,
  setDualTargetEnabled,
  zoomLevel,
  setZoomLevel,
  noiseType,
  setNoiseType,
  noiseStdDev,
  setNoiseStdDev,
  cameraJitter,
  setCameraJitter,
  atmospheric,
  setAtmospheric,
  platformMotion,
  setPlatformMotion,
  onCommand,
  onConfigChange,
}) {
  const update = (key, value, setter) => {
    setter(value);
    onConfigChange({ [key]: value });
  };

  return (
    <aside className="dashboard-panel control-panel">
      <div className="panel-kicker">CONFIGURATION</div>
      <h1>Mission Control</h1>
      <div className="control-mode-row">
        <span>Mode</span>
        <strong>SIMULATION</strong>
      </div>
      <div className="engine-actions">
        <button
          className="button button-start"
          onClick={() => onCommand("start")}
          disabled={engineStatus === "running"}
        >
          <span className="button-icon" aria-hidden="true">
            &#9654;
          </span>
          START
        </button>
        <button
          className="button button-stop"
          onClick={() => onCommand("stop")}
          disabled={engineStatus === "stopped"}
        >
          STOP
        </button>
        <button
          className="button button-restart"
          onClick={() => onCommand("restart")}
        >
          RESTART
        </button>
      </div>
      <div className="status-list">
        <div>
          Bridge{" "}
          <strong className={connected ? "status-good" : "status-bad"}>
            {connected ? "ONLINE" : "OFFLINE"}
          </strong>
        </div>
        <div>
          Engine{" "}
          <strong
            className={
              engineStatus === "running" ? "status-good" : "status-bad"
            }
          >
            {engineStatus === "running" ? "RUNNING" : "STOPPED"}
          </strong>
        </div>
        <div>
          Tracking{" "}
          <strong
            className={status === "TRACKING" ? "status-good" : "status-warn"}
          >
            {status}
          </strong>
        </div>
      </div>
      {status === "PREDICTING" && (
        <div className="alert alert-warn">
          TARGET LOST - KALMAN PREDICTION ACTIVE
        </div>
      )}
      {status === "KALMAN COASTING" && (
        <div className="alert alert-info">
          KALMAN COASTING ACTIVE
          {status && (
            <small>
              {" "}
              Prediction: ({targetX}, {targetY})
            </small>
          )}
        </div>
      )}
      <div className="coordinate-grid">
        <div>
          <span>TARGET BEACON</span>
          <strong>X: {targetX}px</strong>
          <strong>Y: {targetY}px</strong>
        </div>
        <div>
          <span>CAMERA SENSOR</span>
          <strong>X: {camX}px</strong>
          <strong>Y: {camY}px</strong>
        </div>
      </div>
      <div className="config-section">
        <div className="section-label">LIVE CONFIGURATION</div>
        <label>Map Zoom: {Math.round(zoomLevel * 100)}%</label>
        <input
          type="range"
          min="0.1"
          max="2"
          step="0.05"
          value={zoomLevel}
          onChange={(event) => setZoomLevel(parseFloat(event.target.value))}
        />
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={obstaclesEnabled}
            onChange={(event) =>
              update(
                "obstacles_enabled",
                event.target.checked,
                setObstaclesEnabled,
              )
            }
          />{" "}
          Enable Virtual Clouds
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={dualTargetEnabled}
            onChange={(event) =>
              update(
                "dual_target",
                event.target.checked,
                setDualTargetEnabled,
              )
            }
          />{" "}
          Enable Dual Targets (Multi-Beacon Tracking)
        </label>
        <label>Target Path Profile</label>
        <select
          value={targetPath}
          onChange={(event) =>
            update("target_path", event.target.value, setTargetPath)
          }
        >
          <option value="Random">Random (Smooth Inertia)</option>
          <option value="Straight Line">Straight Line</option>
          <option value="Circular">Circular</option>
          <option value="Figure of 8">Figure of 8</option>
          <option value="Spiral">Spiral</option>
          <option value="Sinusoidal">Sinusoidal</option>
        </select>
        <label>
          Target Speed: <strong>{targetSpeed} px/frame</strong>
        </label>
        <input
          type="range"
          min="1"
          max="35"
          value={targetSpeed}
          onChange={(event) =>
            update("target_speed", event.target.value, setTargetSpeed)
          }
        />
        <div className="section-label">DISTURBANCES &amp; NOISE</div>
        <label>Atmospheric Condition</label>
        <select
          value={atmospheric}
          onChange={(event) =>
            update("atmospheric", event.target.value, setAtmospheric)
          }
        >
          <option>Clear</option>
          <option>Haze</option>
          <option>Fog</option>
          <option>Rain</option>
          <option>Low light</option>
        </select>
        <label>Image Noise</label>
        <select
          value={noiseType}
          onChange={(event) =>
            update("noise_type", event.target.value, setNoiseType)
          }
        >
          <option>None</option>
          <option>Salt &amp; Pepper</option>
          <option>Gaussian</option>
          <option>Poisson</option>
        </select>
        {noiseType !== "None" && (
          <>
            <label>Noise StdDev: {noiseStdDev}</label>
            <input
              type="range"
              min="1"
              max="100"
              value={noiseStdDev}
              onChange={(event) =>
                update(
                  "noise_std_dev",
                  parseInt(event.target.value, 10),
                  setNoiseStdDev,
                )
              }
            />
          </>
        )}
        <label>Camera Jitter: +/- {cameraJitter}px</label>
        <input
          type="range"
          min="0"
          max="50"
          value={cameraJitter}
          onChange={(event) =>
            update(
              "camera_jitter",
              parseInt(event.target.value, 10),
              setCameraJitter,
            )
          }
        />
        <label>Platform Motion</label>
        <select
          value={platformMotion}
          onChange={(event) =>
            update("platform_motion", event.target.value, setPlatformMotion)
          }
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

export default ControlPanel;
