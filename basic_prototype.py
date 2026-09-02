import cv2
import numpy as np
import math
import os

# Configuration
WORLD_W, WORLD_H = 1000, 1000
CAM_W, CAM_H = 400, 400
FPS = 30
DURATION_SEC = 10
TOTAL_FRAMES = FPS * DURATION_SEC

# Initial state
target_x, target_y = 800.0, 500.0
cam_pan, cam_tilt = 800.0, 500.0  # Center of camera in world coordinates

output_path = os.path.join(os.path.dirname(__file__), "prototype_output.mp4")
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(output_path, fourcc, FPS, (CAM_W, CAM_H))

print("Starting simulation...")

for frame_idx in range(TOTAL_FRAMES):
    # 1. Update Target Position (Move in a circle)
    time_sec = frame_idx / FPS
    radius = 300
    target_x = 500 + radius * math.cos(time_sec * 1.5)
    target_y = 500 + radius * math.sin(time_sec * 1.5)

    # 2. Render Virtual World
    world = np.zeros((WORLD_H, WORLD_W, 3), dtype=np.uint8)

    # Draw background grid for visual reference
    for x in range(0, WORLD_W, 100):
        cv2.line(world, (x, 0), (x, WORLD_H), (50, 50, 50), 1)
    for y in range(0, WORLD_H, 100):
        cv2.line(world, (0, y), (WORLD_W, y), (50, 50, 50), 1)

    # Draw Target (White beacon)
    cv2.circle(world, (int(target_x), int(target_y)), 10, (255, 255, 255), -1)

    # 3. Simulate Camera View (Crop from world)
    # Ensure camera bounds don't exceed world
    cam_left = int(cam_pan - CAM_W / 2)
    cam_top = int(cam_tilt - CAM_H / 2)

    # Pad world if camera goes out of bounds
    padded_world = cv2.copyMakeBorder(
        world, CAM_H, CAM_H, CAM_W, CAM_W, cv2.BORDER_CONSTANT, value=(0, 0, 0)
    )

    # Extract camera view (shift by padding)
    view_left = cam_left + CAM_W
    view_top = cam_top + CAM_H
    camera_view = padded_world[
        view_top : view_top + CAM_H, view_left : view_left + CAM_W
    ].copy()

    # 4. Computer Vision (Detection)
    gray = cv2.cvtColor(camera_view, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        # Assume largest contour is target
        c = max(contours, key=cv2.contourArea)
        M = cv2.moments(c)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            # Draw crosshair on detection
            cv2.drawMarker(camera_view, (cx, cy), (0, 255, 0), cv2.MARKER_CROSS, 20, 2)

            # 5. Tracking / Control Logic (Proportional Control)
            # Center of camera is (CAM_W/2, CAM_H/2)
            error_x = cx - (CAM_W / 2)
            error_y = cy - (CAM_H / 2)

            # P Controller
            Kp = 0.3
            pan_velocity = error_x * Kp
            tilt_velocity = error_y * Kp

            # Update camera pan/tilt for next frame
            cam_pan += pan_velocity
            cam_tilt += tilt_velocity

            cv2.putText(
                camera_view,
                f"LOCKED E:({int(error_x)}, {int(error_y)})",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
    else:
        cv2.putText(
            camera_view,
            "SEARCHING",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2,
        )

    # Draw center crosshair
    cv2.drawMarker(
        camera_view, (CAM_W // 2, CAM_H // 2), (255, 0, 0), cv2.MARKER_CROSS, 20, 1
    )

    out.write(camera_view)

out.release()
print(f"Simulation complete. Output saved to {output_path}")
