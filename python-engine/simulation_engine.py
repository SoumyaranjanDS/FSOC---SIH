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
OBSTACLES_ENABLED = False

NOISE_TYPE = "None"
NOISE_STD_DEV = 20
CAMERA_JITTER = 0
ATMOSPHERIC = "Clear"
PLATFORM_MOTION = "None"

def stdin_listener():
    """Background thread to listen for commands from the Node Server"""
    global TARGET_MAX_SPEED, TARGET_PATH, OBSTACLES_ENABLED
    global NOISE_TYPE, NOISE_STD_DEV, CAMERA_JITTER, ATMOSPHERIC, PLATFORM_MOTION
    for line in sys.stdin:
        try:
            cmd = json.loads(line)
            if "target_speed" in cmd:
                TARGET_MAX_SPEED = float(cmd["target_speed"])
            if "target_path" in cmd:
                TARGET_PATH = cmd["target_path"]
            if "obstacles_enabled" in cmd:
                OBSTACLES_ENABLED = bool(cmd["obstacles_enabled"])
            if "noise_type" in cmd:
                NOISE_TYPE = cmd["noise_type"]
            if "noise_std_dev" in cmd:
                NOISE_STD_DEV = int(cmd["noise_std_dev"])
            if "camera_jitter" in cmd:
                CAMERA_JITTER = int(cmd["camera_jitter"])
            if "atmospheric" in cmd:
                ATMOSPHERIC = cmd["atmospheric"]
            if "platform_motion" in cmd:
                PLATFORM_MOTION = cmd["platform_motion"]
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
    
    # --- PERFORMANCE METRICS TRACKING ---
    sim_start_time = time.time()
    locked_frames = 0
    lost_frames = 0
    total_error = 0
    max_error = 0
    acquisition_time = 0.0
    initial_lock_achieved = False
    
    # Define Dynamic Obstacles (Virtual Clouds)
    def spawn_cloud():
        return {
            "x": random.randint(200, WORLD_SIZE - 400),
            "y": random.randint(200, WORLD_SIZE - 400),
            "w": random.randint(150, 350),
            "h": random.randint(100, 200),
            "dx": random.uniform(-4, 4),
            "dy": random.uniform(-4, 4),
            "lifetime": random.randint(150, 500),
            "active": random.random() > 0.2  # 80% chance to be active (visible)
        }
        
    obstacles = [spawn_cloud() for _ in range(4)]

    while True:
        # --- 1. WORLD GENERATION ---
        world = np.zeros((WORLD_SIZE, WORLD_SIZE), dtype=np.uint8)

        frame_count += 1
        
        # --- UPDATE VIRTUAL CLOUDS ---
        if OBSTACLES_ENABLED:
            for i in range(len(obstacles)):
                obs = obstacles[i]
                obs["x"] += obs["dx"]
                obs["y"] += obs["dy"]
                obs["lifetime"] -= 1
                
                # Bounce clouds off edges
                if obs["x"] < 0 or obs["x"] + obs["w"] > WORLD_SIZE:
                    obs["dx"] *= -1
                if obs["y"] < 0 or obs["y"] + obs["h"] > WORLD_SIZE:
                    obs["dy"] *= -1
                    
                # Randomly vanish/respawn
                if obs["lifetime"] <= 0:
                    obstacles[i] = spawn_cloud()

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
        
        # --- 1.5 OBSTACLE (VIRTUAL CLOUD) RENDERING ---
        # Draw obstacles AFTER the beacon, in pure black (0)
        # This completely erases the beacon pixels if they overlap!
        if OBSTACLES_ENABLED:
            for obs in obstacles:
                if obs.get("active", True):
                    center = (int(obs["x"] + obs["w"]/2), int(obs["y"] + obs["h"]/2))
                    axes = (int(obs["w"]/2), int(obs["h"]/2))
                    cv2.ellipse(world, center, axes, 0, 0, 360, 0, -1)

        # --- 2. VIRTUAL CAMERA (STEP 4: PTZ MOTORS) ---
        # Saturated P-Controller
        # The camera motors try to correct the error, but they have physical speed limits!
        # PDF: Max Pan Speed = 5 deg/s. (FOV 4 deg = 640px. So 5 deg/s = 800px/s)
        # At 30 FPS, Max Speed = 800 / 30 = 26.66 px/frame.
        MAX_MOTOR_SPEED = 26.66
        
        cam_dx = 0
        cam_dy = 0
        
        # Deadzone: if the error is tiny, don't jitter
        if abs(error_x) > 2: 
            cam_dx = error_x * 0.8  # Aggressive Proportional Gain
        if abs(error_y) > 2: 
            cam_dy = error_y * 0.8
        
        # Saturated clipping to perfectly match PDF physical constraints
        cam_dx = max(-MAX_MOTOR_SPEED, min(MAX_MOTOR_SPEED, cam_dx))
        cam_dy = max(-MAX_MOTOR_SPEED, min(MAX_MOTOR_SPEED, cam_dy))

        # Apply the physical motor movement
        cam_x += int(cam_dx)
        cam_y += int(cam_dy)

        # --- 2.2 PLATFORM MOTION (Camera Base Moving) ---
        if PLATFORM_MOTION == "Linear":
            cam_x += 5
        elif PLATFORM_MOTION == "Circular":
            cam_x += int(10 * math.cos(t * 2))
            cam_y += int(10 * math.sin(t * 2))
        elif PLATFORM_MOTION == "Random":
            cam_x += random.randint(-15, 15)
            cam_y += random.randint(-15, 15)
        elif PLATFORM_MOTION == "Figure of 8":
            cam_x += int(15 * math.cos(t * 1.5))
            cam_y += int(15 * math.sin(t * 3.0) / 2)
        elif PLATFORM_MOTION == "Spiral":
            cam_x += int((t * 2) * math.cos(t * 2))
            cam_y += int((t * 2) * math.sin(t * 2))

        # Ensure camera doesn't slice out of bounds (edge collision)
        cam_x = max(0, min(cam_x, WORLD_SIZE - CAM_WIDTH))
        cam_y = max(0, min(cam_y, WORLD_SIZE - CAM_HEIGHT))

        # --- 2.5 DISTURBANCE ENGINE (STEP 5) ---
        
        # 1. Camera Jitter (Random micro-vibrations in the viewport slice)
        jitter_x = random.randint(-CAMERA_JITTER, CAMERA_JITTER) if CAMERA_JITTER > 0 else 0
        jitter_y = random.randint(-CAMERA_JITTER, CAMERA_JITTER) if CAMERA_JITTER > 0 else 0
        
        view_x = max(0, min(cam_x + jitter_x, WORLD_SIZE - CAM_WIDTH))
        view_y = max(0, min(cam_y + jitter_y, WORLD_SIZE - CAM_HEIGHT))
        
        camera_feed = world[
            view_y : view_y + CAM_HEIGHT, view_x : view_x + CAM_WIDTH
        ].copy()

        # 2. Atmospheric Disturbance
        if ATMOSPHERIC != "Clear":
            if ATMOSPHERIC == "Haze":
                haze = np.full_like(camera_feed, 200)
                camera_feed = cv2.addWeighted(camera_feed, 0.75, haze, 0.25, 0)
            elif ATMOSPHERIC == "Fog":
                fog = np.full_like(camera_feed, 230)
                camera_feed = cv2.addWeighted(camera_feed, 0.4, fog, 0.6, 0)
            elif ATMOSPHERIC == "Low light":
                camera_feed = cv2.convertScaleAbs(camera_feed, alpha=0.3, beta=0)
            elif ATMOSPHERIC == "Rain":
                # Draw random translucent angled lines to simulate rain
                rain_overlay = camera_feed.copy()
                for _ in range(100):
                    rx = random.randint(-50, CAM_WIDTH + 50)
                    ry = random.randint(-50, CAM_HEIGHT + 50)
                    cv2.line(rain_overlay, (rx, ry), (rx - 10, ry + 30), (150, 150, 150), 1)
                camera_feed = cv2.addWeighted(rain_overlay, 0.4, camera_feed, 0.6, 0)

        # 3. Image Noise
        if NOISE_TYPE != "None":
            if NOISE_TYPE == "Salt & Pepper":
                prob = NOISE_STD_DEV / 200.0  # e.g., 20/200 = 10%
                rnd = np.random.rand(CAM_HEIGHT, CAM_WIDTH)
                camera_feed[rnd < (prob / 2)] = 0
                camera_feed[rnd > 1 - (prob / 2)] = 255
            elif NOISE_TYPE == "Gaussian":
                gauss = np.random.normal(0, NOISE_STD_DEV, (CAM_HEIGHT, CAM_WIDTH)).astype(np.float32)
                noisy = np.clip(camera_feed.astype(np.float32) + gauss, 0, 255).astype(np.uint8)
                camera_feed = noisy
            elif NOISE_TYPE == "Poisson":
                # Poisson noise is dependent on pixel intensity. Scale by std dev.
                noisy = np.random.poisson(camera_feed.astype(np.float32) / (NOISE_STD_DEV + 1)) * (NOISE_STD_DEV + 1)
                camera_feed = np.clip(noisy, 0, 255).astype(np.uint8)

        # --- 3. COMPUTER VISION TRACKER (AI SERVICE) ---
        # The AI doesn't know it's a simulation. It just takes an image and camera encoder positions.
        # We pass the obstacle positions so the tracker can find where the target will exit the cloud.
        active_obs_for_tracker = [
            {"x": int(o["x"]), "y": int(o["y"]), "w": int(o["w"]), "h": int(o["h"])}
            for o in obstacles if o.get("active", True)
        ] if OBSTACLES_ENABLED else []
        
        error_x, error_y, rmse, status_str, log_msg = tracker.update(
            camera_feed, cam_x, cam_y, current_path=TARGET_PATH, obstacles=active_obs_for_tracker
        )

        # --- UPDATE PERFORMANCE METRICS ---
        total_error += rmse
        if rmse > max_error:
            max_error = rmse
            
        if status_str in ["TRACKING", "DISTURBED", "ACQUIRING"]:
            locked_frames += 1
            if not initial_lock_achieved:
                acquisition_time = time.time() - sim_start_time
                initial_lock_achieved = True
        else:
            lost_frames += 1

        avg_error = total_error / frame_count
        lock_retention_rate = (locked_frames / (locked_frames + lost_frames)) * 100 if (locked_frames + lost_frames) > 0 else 0
        current_fps = frame_count / (time.time() - sim_start_time) if time.time() - sim_start_time > 0 else FPS
        
        # --- 4. TELEMETRY OUTPUT (STEP 6) ---
        # Package the data as JSON and print it to stdout for the Node server to catch
        active_obstacles = [
            {"x": int(o["x"]), "y": int(o["y"]), "w": int(o["w"]), "h": int(o["h"])}
            for o in obstacles if o.get("active", True)
        ]
        
        telemetry = {
            "target": {"x": true_x, "y": true_y},
            "camera": {"x": cam_x, "y": cam_y},
            "error": {"x": error_x, "y": error_y, "rmse": rmse},
            "status": status_str,
            "obstacles": active_obstacles if OBSTACLES_ENABLED else [],
            "performance": {
                "duration": time.time() - sim_start_time,
                "fps": current_fps,
                "acquisition_time": acquisition_time,
                "avg_error": avg_error,
                "max_error": max_error,
                "lock_retention_rate": lock_retention_rate
            }
        }

        # If Kalman Coasting is active, include the prediction for the UI
        if status_str == "KALMAN COASTING":
            telemetry["coasting_coord"] = {"x": int(tracker.kf.statePre[0, 0]), "y": int(tracker.kf.statePre[1, 0])}
            
            # Send the remaining LSTM predicted path for the UI to draw!
            if hasattr(tracker, "lstm_sequence") and tracker.lstm_sequence:
                telemetry["predicted_path"] = [{"x": int(p[0]), "y": int(p[1])} for p in tracker.lstm_sequence[:50]]
            
            # Send re-acquisition point if active
            if hasattr(tracker, "reacq_point") and tracker.reacq_point:
                telemetry["reacq_point"] = {"x": int(tracker.reacq_point[0]), "y": int(tracker.reacq_point[1])}

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
