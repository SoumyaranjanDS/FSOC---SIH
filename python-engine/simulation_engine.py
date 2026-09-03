import cv2
import numpy as np
import math
import time
import sys
import threading
import json
from kalman_tracker import KalmanTracker

# --- CONSTANTS (Strictly adhering to PDF SIH-26169) ---
WORLD_SIZE = 2000  # PDF: Screen Size (min.) 2000 x 2000 pixels
TARGET_SIZE = 10  # PDF: Target Size Default 10 x 10 pixels
CAM_WIDTH = 640  # PDF: Camera Resolution 640 x 480 pixels
CAM_HEIGHT = 480  # PDF: Camera Resolution 640 x 480 pixels
FPS = 30  # PDF: Camera update Rate 30 Hz (min.)
DELAY_MS = int(1000 / FPS)

MAX_SPEED_PX = 26  # Max Pan/Tilt speed per frame (approx 5 degrees/sec)

# --- DYNAMIC CONFIGURATION ---
TARGET_MAX_SPEED = 15.0
TARGET_PATH = "Random"

def stdin_listener():
    """Background thread to listen for commands from the Node Server"""
    global TARGET_MAX_SPEED, TARGET_PATH
    for line in sys.stdin:
        try:
            cmd = json.loads(line)
            if "target_speed" in cmd:
                TARGET_MAX_SPEED = float(cmd["target_speed"])
            if "target_path" in cmd:
                TARGET_PATH = cmd["target_path"]
        except Exception:
            pass

def main():
    print("Starting Step 4: PTZ Motor Physics...")
    
    # Start the IPC thread
    ipc_thread = threading.Thread(target=stdin_listener, daemon=True)
    ipc_thread.start()

    t = 0.0

    # Initialize Camera position at the center of the universe
    cam_x = (WORLD_SIZE // 2) - (CAM_WIDTH // 2)
    cam_y = (WORLD_SIZE // 2) - (CAM_HEIGHT // 2)

    # Initialize the new decoupled AI Brain
    # (We start the beacon at the center of the world at t=0)
    tracker = KalmanTracker(WORLD_SIZE // 2, WORLD_SIZE // 2, CAM_WIDTH, CAM_HEIGHT, WORLD_SIZE)

    # Initial error is 0
    error_x = 0
    error_y = 0

    import random

    t_x, t_y = float(WORLD_SIZE // 2), float(WORLD_SIZE // 2)
    t_dx, t_dy = random.uniform(-10, 10), random.uniform(-10, 10)
    
    # Smooth Target Physics State
    t_ax, t_ay = 0.0, 0.0
    frame_count = 0
    t_phase = 0.0
    bounce_x, bounce_y = 1.0, 1.0
    
    # Advanced Path State
    circle_cx, circle_cy = float(WORLD_SIZE // 2), float(WORLD_SIZE // 2)
    circle_R = 400.0
    target_circle_R = 400.0
    circle_hit_edge = False
    spiral_r = 10.0
    spiral_dir = 1.0
    
    # Track the previous path to detect switches
    prev_path = TARGET_PATH
    transitioning_to_center = False

    while True:
        # --- 1. WORLD GENERATION ---
        world = np.zeros((WORLD_SIZE, WORLD_SIZE), dtype=np.uint8)

        frame_count += 1

        # Track path switches to reset state if needed
        if TARGET_PATH != prev_path:
            if TARGET_PATH in ["Circular", "Spiral", "Figure of 8", "Sinusoidal"]:
                transitioning_to_center = True
            else:
                transitioning_to_center = False
            prev_path = TARGET_PATH

        # --- TARGET PHYSICS ENGINE ---
        if transitioning_to_center:
            # Smoothly fly to the center of the map before starting the mathematical path
            cx, cy = WORLD_SIZE // 2, WORLD_SIZE // 2
            dist = math.hypot(cx - t_x, cy - t_y)
            if dist <= TARGET_MAX_SPEED:
                t_x, t_y = float(cx), float(cy)
                transitioning_to_center = False
                
                # Reset path-specific mathematical states exactly at the center
                if TARGET_PATH == "Circular":
                    circle_cx, circle_cy = t_x, t_y
                    circle_R = 400.0
                    target_circle_R = 400.0
                    t_phase = 0.0
                    circle_hit_edge = False
                elif TARGET_PATH == "Spiral":
                    spiral_r = 10.0
                    spiral_dir = 1.0
                    t_phase = 0.0
                elif TARGET_PATH == "Figure of 8":
                    t_phase = 0.0
                    bounce_x, bounce_y = 1.0, 1.0
                elif TARGET_PATH == "Sinusoidal":
                    t_phase = 0.0
                    bounce_x, bounce_y = 1.0, 1.0
            else:
                # Move towards center at max speed
                t_dx = ((cx - t_x) / dist) * TARGET_MAX_SPEED
                t_dy = ((cy - t_y) / dist) * TARGET_MAX_SPEED
                t_x += t_dx
                t_y += t_dy
                
        elif TARGET_PATH == "Spiral":
            # Bouncing Spiral Physics
            cx, cy = WORLD_SIZE // 2, WORLD_SIZE // 2
            
            if spiral_r < 10.0:
                spiral_r = 10.0
            omega = TARGET_MAX_SPEED / spiral_r
            t_phase += omega
            
            expansion_speed = TARGET_MAX_SPEED * 0.15 * spiral_dir
            spiral_r += expansion_speed
            
            t_x = cx + math.cos(t_phase) * spiral_r
            t_y = cy + math.sin(t_phase) * spiral_r
            t_dx, t_dy = 0, 0
            
            if t_x < 100 or t_x > WORLD_SIZE - 100 or t_y < 100 or t_y > WORLD_SIZE - 100:
                spiral_dir = -1.0  # Hit outer edge, spiral inwards
            if spiral_r <= 20.0 and spiral_dir == -1.0:
                spiral_dir = 1.0   # Hit center, spiral outwards again
                
        elif TARGET_PATH == "Circular":
            # Smart Circle Physics (Dynamic Breathing Radius + Edge Sliding)
            if circle_R < target_circle_R:
                circle_R = min(circle_R + 1.0, target_circle_R)
            elif circle_R > target_circle_R:
                circle_R = max(circle_R - 1.0, target_circle_R)
                
            omega = TARGET_MAX_SPEED / max(circle_R, 10.0)
            
            old_phase = t_phase
            t_phase += omega
            # Check for a full 360 rotation
            if int(old_phase / (2*math.pi)) < int(t_phase / (2*math.pi)):
                if not circle_hit_edge:
                    target_circle_R += 100.0  # Grow!
                else:
                    target_circle_R = max(100.0, target_circle_R - 50.0)  # Shrink!
                circle_hit_edge = False
            
            proposed_x = circle_cx + math.cos(t_phase) * circle_R
            proposed_y = circle_cy + math.sin(t_phase) * circle_R
            
            # Smooth Edge Sliding
            if proposed_x < 100:
                circle_cx += (100 - proposed_x)
                circle_hit_edge = True
            elif proposed_x > WORLD_SIZE - 100:
                circle_cx -= (proposed_x - (WORLD_SIZE - 100))
                circle_hit_edge = True
                
            if proposed_y < 100:
                circle_cy += (100 - proposed_y)
                circle_hit_edge = True
            elif proposed_y > WORLD_SIZE - 100:
                circle_cy -= (proposed_y - (WORLD_SIZE - 100))
                circle_hit_edge = True
                
            t_x = circle_cx + math.cos(t_phase) * circle_R
            t_y = circle_cy + math.sin(t_phase) * circle_R
            t_dx, t_dy = 0, 0
            
        else:
            # Velocity-Based Physics (Bounces off walls)
            omega = TARGET_MAX_SPEED / 800.0
            t_phase += omega

            if TARGET_PATH == "Random":
                if frame_count % 15 == 0:
                    max_accel = TARGET_MAX_SPEED * 0.15
                    t_ax = random.uniform(-max_accel, max_accel)
                    t_ay = random.uniform(-max_accel, max_accel)

                desired_dx = t_dx + t_ax
                desired_dy = t_dy + t_ay
                desired_speed = math.hypot(desired_dx, desired_dy)
                current_speed = math.hypot(t_dx, t_dy)
                
                if current_speed > 0.1 and desired_speed > 0.1:
                    current_heading = math.atan2(t_dy, t_dx)
                    desired_heading = math.atan2(desired_dy, desired_dx)
                    angle_diff = math.atan2(math.sin(desired_heading - current_heading), math.cos(desired_heading - current_heading))
                    max_turn_rad = math.radians(40.0 / 30.0)
                    angle_diff = max(-max_turn_rad, min(max_turn_rad, angle_diff))
                    new_heading = current_heading + angle_diff
                    t_dx = math.cos(new_heading) * desired_speed
                    t_dy = math.sin(new_heading) * desired_speed
                else:
                    t_dx, t_dy = desired_dx, desired_dy

                speed = math.hypot(t_dx, t_dy)
                if speed > TARGET_MAX_SPEED:
                    t_dx = (t_dx / speed) * TARGET_MAX_SPEED
                    t_dy = (t_dy / speed) * TARGET_MAX_SPEED
                    
            elif TARGET_PATH == "Straight Line":
                speed = math.hypot(t_dx, t_dy)
                if speed < 0.1:
                    t_dx, t_dy = TARGET_MAX_SPEED * bounce_x, 0.0
                else:
                    t_dx = (t_dx / speed) * TARGET_MAX_SPEED
                    t_dy = (t_dy / speed) * TARGET_MAX_SPEED
                    
            elif TARGET_PATH == "Figure of 8":
                # Vertical Figure 8: Swap X and Y frequencies
                t_dx = math.cos(2 * t_phase) * TARGET_MAX_SPEED * bounce_x
                t_dy = math.cos(t_phase) * TARGET_MAX_SPEED * bounce_y
                
            elif TARGET_PATH == "Sinusoidal":
                # Moderate curve: Increased frequency multiplier (shorter wavelength) 
                # and reduced amplitude multiplier
                t_dx = TARGET_MAX_SPEED * 0.8 * bounce_x
                t_dy = math.cos(t_phase * 3.0) * (TARGET_MAX_SPEED * 0.6) * bounce_y

            # Apply velocity
            t_x += t_dx
            t_y += t_dy

            # Bounce off edges
            if t_x < 100:
                t_x, bounce_x = 100.0, bounce_x * -1
                t_dx *= -1
            elif t_x > WORLD_SIZE - 100:
                t_x, bounce_x = float(WORLD_SIZE - 100), bounce_x * -1
                t_dx *= -1

            if t_y < 100:
                t_y, bounce_y = 100.0, bounce_y * -1
                t_dy *= -1
            elif t_y > WORLD_SIZE - 100:
                t_y, bounce_y = float(WORLD_SIZE - 100), bounce_y * -1
                t_dy *= -1

        true_x, true_y = int(t_x), int(t_y)

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

        # --- 3. COMPUTER VISION TRACKER (AI SERVICE) ---
        # The AI doesn't know it's a simulation. It just takes an image and camera encoder positions.
        error_x, error_y, rmse, status_str, log_msg = tracker.update(
            camera_feed, cam_x, cam_y
        )

        # --- 4. TELEMETRY OUTPUT (STEP 6) ---
        # Package the data as JSON and print it to stdout for the Node server to catch
        telemetry = {
            "target": {"x": true_x, "y": true_y},
            "camera": {"x": cam_x, "y": cam_y},
            "error": {"x": error_x, "y": error_y, "rmse": rmse},
            "status": status_str,
        }

        # If Kalman Coasting is active, include the prediction for the UI
        if status_str == "KALMAN COASTING":
            telemetry["coasting_coord"] = {"x": int(tracker.kf.statePre[0, 0]), "y": int(tracker.kf.statePre[1, 0])}

        # If the AI produced a text log, send it to the UI!
        if log_msg:
            telemetry["log"] = log_msg

        # Print JSON so Node.js can read it (using flush=True to prevent buffering lag)
        import json

        print(json.dumps(telemetry), flush=True)

        # --- 5. HEADLESS TIMING ---
        # Instead of cv2.waitKey blocking and rendering windows, we simply sleep to maintain 30 FPS
        time.sleep(DELAY_MS / 1000.0)


if __name__ == "__main__":
    main()
