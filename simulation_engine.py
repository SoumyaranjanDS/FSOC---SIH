import cv2
import numpy as np
import math
import time

# --- CONSTANTS (Strictly adhering to PDF SIH-26169) ---
WORLD_SIZE = 2000  # PDF: Screen Size (min.) 2000 x 2000 pixels
TARGET_SIZE = 10  # PDF: Target Size Default 10 x 10 pixels
CAM_WIDTH = 640  # PDF: Camera Resolution 640 x 480 pixels
CAM_HEIGHT = 480  # PDF: Camera Resolution 640 x 480 pixels
FPS = 30  # PDF: Camera update Rate 30 Hz (min.)
DELAY_MS = int(1000 / FPS)


MAX_SPEED_PX = 26  # Max Pan/Tilt speed per frame (approx 5 degrees/sec)


def main():
    print("Starting Step 4: PTZ Motor Physics...")

    t = 0.0

    # Initialize Camera position at the center of the universe
    cam_x = (WORLD_SIZE // 2) - (CAM_WIDTH // 2)
    cam_y = (WORLD_SIZE // 2) - (CAM_HEIGHT // 2)

    # Initial error is 0
    error_x = 0
    error_y = 0

    while True:
        # --- 1. WORLD GENERATION ---
        world = np.zeros((WORLD_SIZE, WORLD_SIZE), dtype=np.uint8)

        # PDF: Motion Selectable (Figure of 8 used here)
        t += 0.05
        true_x = int(1000 + 800 * math.sin(t))
        true_y = int(1000 + 400 * math.sin(t * 2))

        # Draw the beacon on the world
        top_left = (true_x - TARGET_SIZE // 2, true_y - TARGET_SIZE // 2)
        bottom_right = (true_x + TARGET_SIZE // 2, true_y + TARGET_SIZE // 2)
        cv2.rectangle(world, top_left, bottom_right, 255, -1)

        # --- 2. VIRTUAL CAMERA (STEP 4: PTZ MOTORS) ---
        # The camera motors try to correct the error, but they have physical speed limits!
        # PDF: Max Pan Speed = 5 deg/s. (FOV 4 deg = 640px. So 5 deg/s = 800px/s = ~26px/frame)
        move_x = max(-MAX_SPEED_PX, min(error_x, MAX_SPEED_PX))
        move_y = max(-MAX_SPEED_PX, min(error_y, MAX_SPEED_PX))

        # Apply the physical motor movement
        cam_x += move_x
        cam_y += move_y

        # Ensure camera doesn't slice out of bounds (edge collision)
        cam_x = max(0, min(cam_x, WORLD_SIZE - CAM_WIDTH))
        cam_y = max(0, min(cam_y, WORLD_SIZE - CAM_HEIGHT))

        # --- 2.5 DISTURBANCE ENGINE (STEP 5) ---
        # (Disabled by user request for clear visualization)
        camera_feed = world[
            cam_y : cam_y + CAM_HEIGHT, cam_x : cam_x + CAM_WIDTH
        ].copy()

        # --- 3. COMPUTER VISION TRACKER (STEP 3) ---
        # The tracker receives the raw camera_feed. It is currently a 1-channel grayscale image.
        # 3a. Thresholding (Isolate bright spots)
        _, thresh = cv2.threshold(camera_feed, 200, 255, cv2.THRESH_BINARY)

        # 3b. Find Contours
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # 3c. Convert feed to BGR so we can draw a GREEN crosshair for visualization
        display_feed = cv2.cvtColor(camera_feed, cv2.COLOR_GRAY2BGR)

        if len(contours) > 0:
            # Find the largest contour (assuming it's the beacon)
            c = max(contours, key=cv2.contourArea)
            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])

                # Draw the green crosshair on the detected center
                cv2.drawMarker(
                    display_feed, (cx, cy), (0, 255, 0), cv2.MARKER_CROSS, 20, 2
                )

                # Calculate the error from the dead-center (320, 240)
                error_x = cx - (CAM_WIDTH // 2)
                error_y = cy - (CAM_HEIGHT // 2)
                # print(f"Error X: {error_x}, Error Y: {error_y}") # Uncomment to see in console

        # Calculate RMSE (Root Mean Square Error)
        rmse = math.sqrt(error_x**2 + error_y**2)

        # --- 4. TELEMETRY OUTPUT (STEP 6) ---
        # Package the data as JSON and print it to stdout for the Node server to catch
        telemetry = {
            "target": {"x": true_x, "y": true_y},
            "camera": {"x": cam_x, "y": cam_y},
            "error": {"x": error_x, "y": error_y, "rmse": round(rmse, 2)},
            "status": "TRACKING" if len(contours) > 0 else "LOST",
        }

        # Print JSON so Node.js can read it (using flush=True to prevent buffering lag)
        import json

        print(json.dumps(telemetry), flush=True)

        # --- 5. DISPLAY (For debugging) ---
        # Display the full world (scaled down to fit monitor)
        display_world = cv2.resize(world, (800, 800))
        cv2.imshow("Step 1: The Virtual Sky (Scaled down)", display_world)

        # Display what the Camera actually sees with the CV Tracking overlay!
        cv2.imshow("Step 3: CV Tracker Feed (640x480)", display_feed)

        if cv2.waitKey(DELAY_MS) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
