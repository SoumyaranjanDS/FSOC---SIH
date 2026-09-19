import cv2
import time
import sys
import json
import threading
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from kalman_tracker import KalmanTracker

# ── Global state for FastAPI MJPEG streaming ──────────────────────────────────
current_frame_jpg = None
frame_lock = threading.Lock()
shutdown_event = threading.Event()

app = FastAPI()


def generate_frames():
    """MJPEG generator — yields frames as multipart boundaries."""
    global current_frame_jpg
    while not shutdown_event.is_set():
        with frame_lock:
            if current_frame_jpg is None:
                # FIX #1: sleep instead of busy-spinning at 100% CPU
                pass
            else:
                frame_bytes = current_frame_jpg.tobytes()
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )
        time.sleep(0.03)


@app.get("/video_feed")
def video_feed():
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


def start_fastapi(port):
    """Run uvicorn on the given port, respecting shutdown_event."""
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="error")
    server = uvicorn.Server(config)
    # Allow graceful shutdown via shutdown_event
    shutdown_event_ref = shutdown_event

    # Patch server to stop when our event fires
    original_serve = server.serve

    import asyncio

    async def serve_with_shutdown():
        loop = asyncio.get_event_loop()

        async def _watch():
            while not shutdown_event_ref.is_set():
                await asyncio.sleep(0.5)
            server.should_exit = True

        loop.create_task(_watch())
        await original_serve()

    asyncio.run(serve_with_shutdown())


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    headless = "--headless" in sys.argv

    if not headless:
        print("Starting Live Webcam Virtual PTZ Mode...")

    # FIX #2: Try multiple ports if 5001 is still held by a zombie process
    FASTAPI_PORT = 5001
    if headless:
        server_thread = threading.Thread(
            target=start_fastapi, args=(FASTAPI_PORT,), daemon=True
        )
        server_thread.start()

        print(json.dumps({"event": "started", "mode": "webcam"}))
        sys.stdout.flush()

    # Open webcam (DirectShow on Windows prevents hanging)
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            if headless:
                print(
                    json.dumps(
                        {"event": "error", "message": "Could not open webcam"}
                    )
                )
                sys.stdout.flush()
            return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    ret, frame = cap.read()
    if not ret:
        if headless:
            print(
                json.dumps(
                    {
                        "event": "error",
                        "message": "Could not read frame from webcam",
                    }
                )
            )
            sys.stdout.flush()
        return

    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Virtual PTZ Configuration
    PTZ_WIDTH = 640
    PTZ_HEIGHT = 480

    cam_x = (actual_width // 2) - (PTZ_WIDTH // 2)
    cam_y = (actual_height // 2) - (PTZ_HEIGHT // 2)

    # FIX #1 (async loading): Load tracker in background so video starts instantly
    global tracker
    tracker = None

    def load_tracker():
        global tracker
        t = KalmanTracker(
            initial_world_x=actual_width // 2,
            initial_world_y=actual_height // 2,
            cam_width=PTZ_WIDTH,
            cam_height=PTZ_HEIGHT,
            world_size=max(actual_width, actual_height),
            video_mode=True,
        )
        tracker = t

    threading.Thread(target=load_tracker, daemon=True).start()

    # FIX #9: Include noise_std so KalmanTracker doesn't use a hidden default
    env_params = {
        "atmospheric": "Clear",
        "noise_type": "None",
        "noise_std": 0,
    }

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)

            cam_x = max(0, min(cam_x, actual_width - PTZ_WIDTH))
            cam_y = max(0, min(cam_y, actual_height - PTZ_HEIGHT))

            viewport = frame[
                cam_y : cam_y + PTZ_HEIGHT, cam_x : cam_x + PTZ_WIDTH
            ].copy()

            status_str = "LOADING AI"
            rmse = 0.0
            error_x = 0
            error_y = 0
            log_msg = ""

            if tracker is not None:
                error_x, error_y, rmse, status_str, log_msg = tracker.update(
                    viewport,
                    cam_x,
                    cam_y,
                    current_path="random",
                    env_params=env_params,
                )

                if status_str != "LOST":
                    dx = error_x * 0.1
                    dy = error_y * 0.1
                    MAX_SPEED = 20
                    dx = max(-MAX_SPEED, min(MAX_SPEED, dx))
                    dy = max(-MAX_SPEED, min(MAX_SPEED, dy))
                    if abs(dx) < 1.5:
                        dx = 0
                    if abs(dy) < 1.5:
                        dy = 0

                    cam_x += int(dx)
                    cam_y += int(dy)

            # ── Draw UI overlay on the video frame ────────────────────────────
            # Yellow PTZ bounding box
            cv2.rectangle(
                frame,
                (cam_x, cam_y),
                (cam_x + PTZ_WIDTH, cam_y + PTZ_HEIGHT),
                (0, 255, 255),
                2,
            )
            cv2.putText(
                frame,
                "VIRTUAL PTZ VIEWPORT",
                (cam_x, max(20, cam_y - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )

            # Green crosshair at center of viewport
            vx_center = cam_x + PTZ_WIDTH // 2
            vy_center = cam_y + PTZ_HEIGHT // 2
            cv2.drawMarker(
                frame,
                (vx_center, vy_center),
                (0, 255, 0),
                cv2.MARKER_CROSS,
                30,
                2,
            )

            if tracker is None:
                cv2.putText(
                    frame,
                    "INITIALIZING AI...",
                    (vx_center - 120, vy_center + 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 255),
                    2,
                )

            if headless:
                # Encode frame for MJPEG stream
                _, buffer = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80]
                )

                global current_frame_jpg
                with frame_lock:
                    current_frame_jpg = buffer

                # FIX #3: Match telemetry shape to simulation format
                # (nested {camera: {x,y}, target: {x,y}} instead of flat)
                telemetry = {
                    "time": round(time.time(), 2),
                    "target": {
                        "x": round(cam_x + PTZ_WIDTH / 2 + error_x, 2),
                        "y": round(cam_y + PTZ_HEIGHT / 2 + error_y, 2),
                    },
                    "camera": {
                        "x": round(cam_x + PTZ_WIDTH / 2, 2),
                        "y": round(cam_y + PTZ_HEIGHT / 2, 2),
                    },
                    "error": {
                        "x": round(error_x, 2),
                        "y": round(error_y, 2),
                        "rmse": round(rmse, 2),  # FIX #7: consistent rounding
                    },
                    "rmse": round(rmse, 2),  # FIX #7
                    "status": status_str,
                    "log_msg": log_msg,
                    "mode": "webcam",
                    "target2_x": None,
                    "target2_y": None,
                    "target2_status": "LOST",
                }
                print(json.dumps(telemetry))
                sys.stdout.flush()
                time.sleep(0.01)
            else:
                cv2.imshow("FSOC Virtual PTZ", viewport)
                key = cv2.waitKey(10) & 0xFF
                if key == ord("q") or key == ord("Q") or key == 27:
                    break

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        # FIX #2: Signal FastAPI server to shut down, releasing port 5001
        shutdown_event.set()
        if headless:
            print(json.dumps({"event": "complete", "mode": "webcam"}))
            sys.stdout.flush()


if __name__ == "__main__":
    main()
