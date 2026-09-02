import time
import math
import random
import json
import sys


def main():
    FPS = 30
    dt = 1.0 / FPS
    t = 0.0

    # Ensure stdout is flushed immediately so Node.js receives real-time data
    sys.stdout.reconfigure(line_buffering=True)

    while True:
        t += 0.012 * 3  # Time step scaled to look good at 30Hz

        # --- VIRTUAL WORLD MATH (Figure 8 Path) ---
        trueX = 50.0 + 40.0 * math.sin(t)
        trueY = 50.0 + 30.0 * math.sin(t * 2.0)

        # Camera PTZ simulation (follows the true target but slightly lags)
        # In a real system, this is limited by motor speed (e.g. 10 deg/s)
        lagX = 50.0 + 40.0 * math.sin(t - 0.2)
        lagY = 50.0 + 30.0 * math.sin(t * 2.0 - 0.2)

        # --- CAMERA FEED MATH ---
        # The camera sees the difference between where it's pointing and the target
        errorX = (trueX - lagX) * 6.0
        errorY = (trueY - lagY) * 6.0

        # Injecting OpenCV "Jitter/Noise" (Salt & Pepper / Gaussian)
        noiseX = (random.random() - 0.5) * 3.0
        noiseY = (random.random() - 0.5) * 3.0

        camX = 50.0 + errorX + noiseX
        camY = 50.0 + errorY + noiseY

        trackerX = 50.0 + errorX
        trackerY = 50.0 + errorY

        # --- LSTM AI PATH PREDICTION ---
        # Generating a predicted future path curve
        pred_points = []
        for i in range(1, 4):
            futureT = t + (i * 0.5)
            fx = 50.0 + ((50.0 + 40.0 * math.sin(futureT)) - lagX) * 6.0
            fy = 50.0 + ((50.0 + 30.0 * math.sin(futureT * 2.0)) - lagY) * 6.0
            pred_points.append({"x": fx, "y": fy})

        # Calculate RMSE Error
        rmse = abs(errorX + errorY)

        # Generate Telemetry Packet
        packet = {
            "world": {"trueX": trueX, "trueY": trueY, "fovX": lagX, "fovY": lagY},
            "camera": {
                "camX": camX,
                "camY": camY,
                "trackerX": trackerX,
                "trackerY": trackerY,
                "predictions": pred_points,
            },
            "metrics": {
                "rmse": round(rmse, 2),
                "pan": round(lagX - 50.0, 1),
                "tilt": round(lagY - 50.0, 1),
                "highError": rmse > 15.0,
            },
        }

        # Print JSON to stdout for Node.js to consume
        print(json.dumps(packet))

        time.sleep(dt)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
