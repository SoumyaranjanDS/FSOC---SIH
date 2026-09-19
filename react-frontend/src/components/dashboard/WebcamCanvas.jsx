import React, { useState, useEffect } from "react";

function WebcamCanvas({ engineStatus }) {
  const isRunning = engineStatus === "running_webcam" || engineStatus === "webcam_loading";
  const [retryCount, setRetryCount] = useState(0);
  const [hasError, setHasError] = useState(false);

  // If it's running but errored out (FastAPI still booting), retry every 2 seconds
  useEffect(() => {
    let interval;
    if (isRunning && hasError) {
      interval = setInterval(() => {
        setHasError(false); // Reset error state to try showing it again
        setRetryCount(prev => prev + 1);
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [isRunning, hasError]);

  // Reset state when stopped
  useEffect(() => {
    if (!isRunning) {
      setHasError(false);
      setRetryCount(0);
    }
  }, [isRunning]);

  return (
    <div className="simulation-canvas-wrapper" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', background: '#081013', position: 'relative' }}>
      {isRunning ? (
        <>
          <div style={{ position: 'absolute', zIndex: 0, color: '#55e6b2' }}>
            Starting Webcam Feed...
          </div>
          <img 
            key={retryCount}
            src={`http://localhost:5001/video_feed?t=${retryCount}`} 
            alt="Live Webcam Feed" 
            style={{ 
              maxWidth: '100%', 
              maxHeight: '100%', 
              objectFit: 'contain', 
              zIndex: 1, 
              position: 'relative',
              display: hasError ? 'none' : 'block'
            }}
            onError={() => {
              setHasError(true);
            }}
          />
        </>
      ) : (
        <div style={{ color: '#55e6b2', textAlign: 'center' }}>
          <h2>Live Webcam PTZ Mode</h2>
          <p>Click START in Mission Control to begin tracking.</p>
        </div>
      )}
    </div>
  );
}

export default WebcamCanvas;
