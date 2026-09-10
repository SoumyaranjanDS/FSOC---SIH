import { useEffect, useRef, useState } from "react";

function SimulationCanvas({
  telemetry,
  zoomLevel,
  atmospheric,
  noiseType,
  camX,
  camY,
  targetX,
  targetY,
}) {
  const [displayCamera, setDisplayCamera] = useState({ x: camX, y: camY });
  const targetCameraRef = useRef({ x: camX, y: camY });

  useEffect(() => {
    targetCameraRef.current = { x: camX, y: camY };
    let animationFrame;

    const settleCamera = () => {
      setDisplayCamera((current) => {
        const next = {
          x: current.x + (targetCameraRef.current.x - current.x) * 0.18,
          y: current.y + (targetCameraRef.current.y - current.y) * 0.18,
        };
        const settled =
          Math.abs(next.x - targetCameraRef.current.x) < 0.1 &&
          Math.abs(next.y - targetCameraRef.current.y) < 0.1;
        if (settled) {
          cancelAnimationFrame(animationFrame);
          return targetCameraRef.current;
        }
        animationFrame = requestAnimationFrame(settleCamera);
        return next;
      });
    };

    animationFrame = requestAnimationFrame(settleCamera);
    return () => cancelAnimationFrame(animationFrame);
  }, [camX, camY]);

  return (
    <main className="simulation-stage">
      <div className="world" style={{ transform: `scale(${zoomLevel})` }}>
        <span className="axis-label axis-origin">(0,0)</span>
        <span className="axis-label axis-center">(1000,1000)</span>
        <span className="axis-label axis-end">(2000,2000)</span>
        {telemetry && (
          <>
            {atmospheric !== "Clear" && (
              <div
                className={`atmosphere atmosphere-${atmospheric.toLowerCase().replace(" ", "-")}`}
              />
            )}
            {noiseType !== "None" && (
              <div
                className="noise-overlay"
                style={{ top: displayCamera.y, left: displayCamera.x }}
              />
            )}
            {telemetry.obstacles?.map((obstacle, index) => (
              <div
                key={index}
                className="obstacle"
                style={{
                  left: obstacle.x,
                  top: obstacle.y,
                  width: obstacle.w,
                  height: obstacle.h,
                }}
              >
                CLOUD
              </div>
            ))}
            <div
              className="target-beacon"
              style={{ left: targetX - 5, top: targetY - 5 }}
            />
            {telemetry.predicted_path?.length > 0 && (
              <svg className="prediction-path" viewBox="0 0 2000 2000">
                <polyline
                  points={telemetry.predicted_path
                    .map((point) => `${point.x},${point.y}`)
                    .join(" ")}
                />
              </svg>
            )}
            {telemetry.coasting_coord && (
              <div
                className="coasting-dot"
                style={{
                  left: telemetry.coasting_coord.x - 8,
                  top: telemetry.coasting_coord.y - 8,
                }}
              />
            )}
            <div
              className="camera-viewport"
              style={{ left: displayCamera.x, top: displayCamera.y }}
            >
              <i />
              <i />
            </div>
          </>
        )}
      </div>
    </main>
  );
}

export default SimulationCanvas;
