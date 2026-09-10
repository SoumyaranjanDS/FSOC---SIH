"""
video_benchmark.py  —  SIH26169 FSOC Benchmark Mode
=====================================================
Reads a judge-supplied MP4 video as the 'world', pans a virtual 640x480
camera viewport over it using the same PTZ motor physics as simulation mode,
and runs the identical KalmanTracker pipeline.

Usage (called by Node.js):
    python video_benchmark.py "C:/path/to/video.mp4"

Emits JSON lines to stdout (same format as simulation_engine.py telemetry).
On EOF: writes benchmark_results.csv + benchmark_summary.json to video directory.
"""

import sys
import os
import cv2
import numpy as np
import time
import math
import csv
import threading
import random
import json

# Allow importing from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from video_tracker import VideoTracker

# ──────────────────────────────────────────────────────────────────────────────
#  CONSTANTS  (same as simulation_engine.py per PDF SIH-26169)
# ──────────────────────────────────────────────────────────────────────────────
CAM_W      = 640
CAM_H      = 480
MAX_SPEED  = 26.66          # px/frame  ← 5°/sec × (640px/4°FOV) / 30FPS

# Adaptive Clear environment — tracker auto-tunes to video content
ENV_PARAMS = {
    "atmospheric":     "Clear",
    "noise_type":      "None",
    "noise_std":       20,
    "camera_jitter":   0,
    "platform_motion": "None",
}

def stdin_listener():
    """Background thread to listen for commands from the Node Server"""
    import json
    for line in sys.stdin:
        try:
            cmd = json.loads(line)
            if "noise_type" in cmd:
                ENV_PARAMS["noise_type"] = cmd["noise_type"]
            if "noise_std_dev" in cmd:
                ENV_PARAMS["noise_std"] = int(cmd["noise_std_dev"])
            if "camera_jitter" in cmd:
                ENV_PARAMS["camera_jitter"] = int(cmd["camera_jitter"])
            if "atmospheric" in cmd:
                ENV_PARAMS["atmospheric"] = cmd["atmospheric"]
            if "platform_motion" in cmd:
                ENV_PARAMS["platform_motion"] = cmd["platform_motion"]
        except Exception:
            pass

# Start the listener thread
threading.Thread(target=stdin_listener, daemon=True).start()


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"mode": "benchmark", "event": "error",
                          "message": "No video path provided"}), flush=True)
        sys.exit(1)

    video_path = sys.argv[1]

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(json.dumps({"mode": "benchmark", "event": "error",
                          "message": f"Cannot open video: {video_path}"}), flush=True)
        sys.exit(1)

    VID_W        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    VID_H        = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_delay  = 1.0 / video_fps

    # Initialize camera to center
    cam_x = float(clamp((VID_W - CAM_W) // 2, 0, max(0, VID_W - CAM_W)))
    cam_y = float(clamp((VID_H - CAM_H) // 2, 0, max(0, VID_H - CAM_H)))

    tracker = VideoTracker(
        VID_W // 2, VID_H // 2,   # initial cam position estimate
        CAM_W, CAM_H,
        max(VID_W, VID_H)          # world size = video dimensions
    )

    # ── Metrics ──────────────────────────────────────────────────────────────
    frame_count       = 0
    start_time        = time.time()
    locked_frames     = 0
    lost_frames       = 0
    total_rmse        = 0.0
    sum_sq_rmse       = 0.0
    max_error         = 0.0
    acquisition_time  = None
    acq_achieved      = False
    last_lost_time    = None
    reacq_times       = []
    rmse_history      = []
    frame_log         = []
    centroid_trail    = []   # last 60 centroid positions for UI trail

    print(json.dumps({
        "mode":          "benchmark",
        "event":         "started",
        "video_width":   VID_W,
        "video_height":  VID_H,
        "total_frames":  total_frames,
        "video_fps":     video_fps,
        "video_path":    video_path,
    }), flush=True)

    # ── Main loop ─────────────────────────────────────────────────────────────
    while cap.isOpened():
        loop_start = time.time()

        ret, full_frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # Convert to grayscale — tracker is grayscale-only
        gray = cv2.cvtColor(full_frame, cv2.COLOR_BGR2GRAY) \
               if len(full_frame.shape) == 3 else full_frame.copy()

        # ── Crop virtual viewport ─────────────────────────────────────────────
        # Apply camera jitter to the viewport crop location
        jitter_x = random.randint(-ENV_PARAMS["camera_jitter"], ENV_PARAMS["camera_jitter"]) if ENV_PARAMS["camera_jitter"] > 0 else 0
        jitter_y = random.randint(-ENV_PARAMS["camera_jitter"], ENV_PARAMS["camera_jitter"]) if ENV_PARAMS["camera_jitter"] > 0 else 0

        x1       = int(clamp(cam_x + jitter_x, 0, max(0, VID_W - CAM_W)))
        y1       = int(clamp(cam_y + jitter_y, 0, max(0, VID_H - CAM_H)))
        viewport = gray[y1: y1 + CAM_H, x1: x1 + CAM_W].copy()

        # ── Apply Atmospheric Effects & Noise to Viewport ─────────────────────
        atm = ENV_PARAMS["atmospheric"]
        if atm != "Clear":
            if atm == "Haze":
                haze = np.full_like(viewport, 200)
                viewport = cv2.addWeighted(viewport, 0.75, haze, 0.25, 0)
            elif atm == "Fog":
                fog = np.full_like(viewport, 230)
                viewport = cv2.addWeighted(viewport, 0.4, fog, 0.6, 0)
            elif atm == "Low light":
                viewport = cv2.convertScaleAbs(viewport, alpha=0.3, beta=0)
            elif atm == "Rain":
                rain_overlay = viewport.copy()
                for _ in range(100):
                    rx = random.randint(-50, CAM_W + 50)
                    ry = random.randint(-50, CAM_H + 50)
                    cv2.line(rain_overlay, (rx, ry), (rx - 10, ry + 30), (150, 150, 150), 1)
                viewport = cv2.addWeighted(rain_overlay, 0.4, viewport, 0.6, 0)

        noise = ENV_PARAMS["noise_type"]
        std_dev = ENV_PARAMS["noise_std"]
        if noise != "None":
            if noise == "Salt & Pepper":
                prob = std_dev / 200.0
                rnd = np.random.rand(CAM_H, CAM_W)
                viewport[rnd < (prob / 2)] = 0
                viewport[rnd > 1 - (prob / 2)] = 255
            elif noise == "Gaussian":
                gauss = np.random.normal(0, std_dev, (CAM_H, CAM_W)).astype(np.float32)
                viewport = np.clip(viewport.astype(np.float32) + gauss, 0, 255).astype(np.uint8)
            elif noise == "Poisson":
                noisy = np.random.poisson(viewport.astype(np.float32) / (std_dev + 1)) * (std_dev + 1)
                viewport = np.clip(noisy, 0, 255).astype(np.uint8)

        # ── Run tracking pipeline ─────────────────────────────────────────────
        error_x, error_y, rmse, status_str, log_msg = tracker.update(
            viewport, cam_x, cam_y, "Random", [], ENV_PARAMS
        )

        # ── PTZ motor physics (matched perfectly to simulation_engine.py) ─────
        cam_dx = 0
        cam_dy = 0
        if abs(error_x) > 2:
            cam_dx = error_x * 0.8
        if abs(error_y) > 2:
            cam_dy = error_y * 0.8

        cam_dx = clamp(cam_dx, -MAX_SPEED, MAX_SPEED)
        cam_dy = clamp(cam_dy, -MAX_SPEED, MAX_SPEED)

        cam_x  = clamp(cam_x + cam_dx, 0, max(0, VID_W - CAM_W))
        cam_y  = clamp(cam_y + cam_dy, 0, max(0, VID_H - CAM_H))

        # ── Metrics update ────────────────────────────────────────────────────
        centroid_x = cam_x + CAM_W // 2 + error_x
        centroid_y = cam_y + CAM_H // 2 + error_y

        if status_str == "TRACKING":
            locked_frames += 1
            if not acq_achieved:
                acquisition_time = time.time() - start_time
                acq_achieved = True
            if last_lost_time is not None:
                reacq_times.append(time.time() - last_lost_time)
                last_lost_time = None
        else:
            lost_frames += 1
            if last_lost_time is None and acq_achieved:
                last_lost_time = time.time()

        total_rmse   += rmse
        sum_sq_rmse  += rmse ** 2
        max_error     = max(max_error, rmse)

        rmse_history.append(round(rmse, 2))
        if len(rmse_history) > 150:
            rmse_history.pop(0)

        centroid_trail.append({"x": centroid_x, "y": centroid_y})
        if len(centroid_trail) > 60:
            centroid_trail.pop(0)

        # ── Frame-level log ───────────────────────────────────────────────────
        frame_log.append({
            "frame":       frame_count,
            "timestamp":   round(frame_count / video_fps, 3),
            "cam_x":       cam_x,
            "cam_y":       cam_y,
            "centroid_x":  centroid_x,
            "centroid_y":  centroid_y,
            "error_x":     error_x,
            "error_y":     error_y,
            "rmse":        round(rmse, 2),
            "status":      status_str,
        })

        # ── Running stats ─────────────────────────────────────────────────────
        elapsed  = time.time() - start_time
        fps_now  = frame_count / elapsed if elapsed > 0 else video_fps
        avg_err  = total_rmse / frame_count
        lock_rt  = (locked_frames / frame_count) * 100

        # ── Telemetry JSON ────────────────────────────────────────────────────
        telemetry = {
            "mode":          "benchmark",
            "frame":         frame_count,
            "total_frames":  total_frames,
            "progress":      round(frame_count / total_frames, 4) if total_frames > 0 else 0,
            "camera":        {"x": cam_x, "y": cam_y},
            "centroid":      {"x": centroid_x, "y": centroid_y},
            "centroid_trail": centroid_trail,
            "error":         {"x": error_x, "y": error_y, "rmse": round(rmse, 2)},
            "status":        status_str,
            "rmse_history":  rmse_history,
            "video":         {"width": VID_W, "height": VID_H},
            "performance": {
                "fps":              round(fps_now, 1),
                "avg_error":        round(avg_err, 2),
                "max_error":        round(max_error, 2),
                "lock_retention_rate": round(lock_rt, 1),
                "acquisition_time": round(acquisition_time, 3) if acquisition_time else None,
                "avg_reacq_time":   round(sum(reacq_times) / len(reacq_times), 3)
                                    if reacq_times else None,
            },
        }
        if log_msg:
            telemetry["log"] = log_msg

        print(json.dumps(telemetry), flush=True)

        # ── Pace to video FPS ─────────────────────────────────────────────────
        sleep = frame_delay - (time.time() - loop_start)
        if sleep > 0:
            time.sleep(sleep)

    cap.release()

    # ── Final metrics ─────────────────────────────────────────────────────────
    rmse_overall = math.sqrt(sum_sq_rmse / frame_count) if frame_count > 0 else 0.0
    final_summary = {
        "total_frames":        frame_count,
        "duration_sec":        round(frame_count / video_fps, 2),
        "processing_fps":      round(frame_count / (time.time() - start_time), 1),
        "acquisition_time_sec": round(acquisition_time, 3) if acquisition_time else None,
        "avg_centroid_error":  round(total_rmse / frame_count, 2) if frame_count > 0 else 0,
        "max_centroid_error":  round(max_error, 2),
        "rmse_overall":        round(rmse_overall, 2),
        "lock_retention_rate": round(locked_frames / frame_count * 100, 1) if frame_count > 0 else 0,
        "avg_reacquisition_sec": round(sum(reacq_times) / len(reacq_times), 3) if reacq_times else None,
        "total_reacquisitions":  len(reacq_times),
    }

    # ── Write CSV ─────────────────────────────────────────────────────────────
    out_dir  = os.path.dirname(os.path.abspath(video_path))
    csv_path  = os.path.join(out_dir, "benchmark_results.csv")
    json_path = os.path.join(out_dir, "benchmark_summary.json")

    if frame_log:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=frame_log[0].keys())
            writer.writeheader()
            writer.writerows(frame_log)

    with open(json_path, "w") as f:
        json.dump(final_summary, f, indent=2)

    # ── Emit completion event ─────────────────────────────────────────────────
    print(json.dumps({
        "mode":      "benchmark",
        "event":     "complete",
        "summary":   final_summary,
        "csv_path":  csv_path,
        "json_path": json_path,
    }), flush=True)


if __name__ == "__main__":
    main()
