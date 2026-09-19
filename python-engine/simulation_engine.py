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

# --- DYNAMIC CONFIGURATION ---
TARGET_MAX_SPEED = 15.0
TARGET_PATH = "Random"
OBSTACLES_ENABLED = False
DUAL_TARGET_ENABLED = False

NOISE_TYPE = "None"
NOISE_STD_DEV = 20
CAMERA_JITTER = 0
ATMOSPHERIC = "Clear"
PLATFORM_MOTION = "None"


def stdin_listener():
    """Background thread to listen for commands from the Node Server"""
    global TARGET_MAX_SPEED, TARGET_PATH, OBSTACLES_ENABLED, DUAL_TARGET_ENABLED
    global NOISE_TYPE, NOISE_STD_DEV, CAMERA_JITTER, ATMOSPHERIC, PLATFORM_MOTION
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            cmd = json.loads(line.strip())
            if "path" in cmd:
                TARGET_PATH = cmd["path"]
            if "target_path" in cmd:
                TARGET_PATH = cmd["target_path"]
            if "speed" in cmd:
                TARGET_MAX_SPEED = float(cmd["speed"])
            if "target_speed" in cmd:
                TARGET_MAX_SPEED = float(cmd["target_speed"])
            if "obstacles" in cmd:
                OBSTACLES_ENABLED = bool(cmd["obstacles"])
            if "obstacles_enabled" in cmd:
                OBSTACLES_ENABLED = bool(cmd["obstacles_enabled"])
            if "dual_target" in cmd:
                DUAL_TARGET_ENABLED = bool(cmd["dual_target"])
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
    tracker = KalmanTracker(
        WORLD_SIZE // 2, WORLD_SIZE // 2, CAM_WIDTH, CAM_HEIGHT, WORLD_SIZE
    )

    # Initial error is 0
    error_x = 0
    error_y = 0

    import random

    t_x, t_y = float(WORLD_SIZE // 2), float(WORLD_SIZE // 2)
    t_dx, t_dy = random.uniform(-10, 10), random.uniform(-10, 10)

    # Second target state
    t2_x, t2_y = float(WORLD_SIZE // 2), float(WORLD_SIZE // 2)
    t2_dx, t2_dy = -t_dx, -t_dy
    t2_phase = math.pi  # 180 degree phase offset

    # Smooth Target Physics State
    t_ax, t_ay = 0.0, 0.0
    frame_count = 0
    t_phase = 0.0
    bounce_x, bounce_y = 1.0, 1.0
    
    prev_dual_target = False

    # Advanced Path State
    circle_cx, circle_cy = float(WORLD_SIZE // 2), float(WORLD_SIZE // 2)
    circle_R = 450.0
    target_circle_R = 450.0
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
    # Rolling RMSE history for the error graph (last 150 frames)
    rmse_history = []

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
            "active": random.random() > 0.2,  # 80% chance to be active (visible)
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
            # Determine the starting coordinate for the chosen path
            target_cx, target_cy = float(WORLD_SIZE // 2), float(WORLD_SIZE // 2)
            if TARGET_PATH == "Circular":
                target_cx += 450.0
            elif TARGET_PATH == "Spiral":
                target_cx += 10.0
                
            dist = math.hypot(target_cx - t_x, target_cy - t_y)
            if dist <= TARGET_MAX_SPEED:
                t_x, t_y = target_cx, target_cy
                transitioning_to_center = False

                # Reset path-specific mathematical states exactly at the center
                if TARGET_PATH == "Circular":
                    circle_cx, circle_cy = float(WORLD_SIZE // 2), float(WORLD_SIZE // 2)
                    circle_R = 450.0
                    target_circle_R = 450.0
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
                # Move towards starting coordinate at max speed
                t_dx = ((target_cx - t_x) / dist) * TARGET_MAX_SPEED
                t_dy = ((target_cy - t_y) / dist) * TARGET_MAX_SPEED
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

            if (
                t_x < 100
                or t_x > WORLD_SIZE - 100
                or t_y < 100
                or t_y > WORLD_SIZE - 100
            ):
                spiral_dir = -1.0  # Hit outer edge, spiral inwards
            if spiral_r <= 20.0 and spiral_dir == -1.0:
                spiral_dir = 1.0  # Hit center, spiral outwards again

        elif TARGET_PATH == "Circular":
            # Fixed Circle Physics
            circle_R = 450.0

            omega = TARGET_MAX_SPEED / circle_R
            t_phase += omega

            proposed_x = circle_cx + math.cos(t_phase) * circle_R
            proposed_y = circle_cy + math.sin(t_phase) * circle_R

            # Smooth Edge Sliding without changing radius
            if proposed_x < 100:
                circle_cx += 100 - proposed_x
            elif proposed_x > WORLD_SIZE - 100:
                circle_cx -= proposed_x - (WORLD_SIZE - 100)

            if proposed_y < 100:
                circle_cy += 100 - proposed_y
            elif proposed_y > WORLD_SIZE - 100:
                circle_cy -= proposed_y - (WORLD_SIZE - 100)

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
                    angle_diff = math.atan2(
                        math.sin(desired_heading - current_heading),
                        math.cos(desired_heading - current_heading),
                    )
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

        # Handle secondary target physics (offset by 180 degrees)
        if DUAL_TARGET_ENABLED:
            if not prev_dual_target:
                tracker.add_track(WORLD_SIZE // 2, WORLD_SIZE // 2)
                prev_dual_target = True
                t2_phase = t_phase + math.pi
                
            if TARGET_PATH == "Circular":
                t2_phase += omega
                t2_x = circle_cx + math.cos(t2_phase) * circle_R
                t2_y = circle_cy + math.sin(t2_phase) * circle_R
            elif TARGET_PATH == "Spiral":
                t2_phase += omega
                t2_x = cx + math.cos(t2_phase) * spiral_r
                t2_y = cy + math.sin(t2_phase) * spiral_r
            else:
                # Basic offset for random/sinusoidal
                t2_x = WORLD_SIZE - t_x
                t2_y = WORLD_SIZE - t_y
        else:
            if prev_dual_target:
                tracker.remove_track()
                prev_dual_target = False

        true_x, true_y = int(t_x), int(t_y)

        # Draw the beacon on the world
        top_left = (true_x - TARGET_SIZE // 2, true_y - TARGET_SIZE // 2)
        bottom_right = (true_x + TARGET_SIZE // 2, true_y + TARGET_SIZE // 2)
        cv2.rectangle(world, top_left, bottom_right, 255, -1)

        if DUAL_TARGET_ENABLED:
            true2_x, true2_y = int(t2_x), int(t2_y)
            top_left2 = (true2_x - TARGET_SIZE // 2, true2_y - TARGET_SIZE // 2)
            bottom_right2 = (true2_x + TARGET_SIZE // 2, true2_y + TARGET_SIZE // 2)
            cv2.rectangle(world, top_left2, bottom_right2, 255, -1)

        # --- 1.5 OBSTACLE (VIRTUAL CLOUD) RENDERING ---
        # Draw obstacles AFTER the beacon, in pure black (0)
        # This completely erases the beacon pixels if they overlap!
        if OBSTACLES_ENABLED:
            for obs in obstacles:
                if obs.get("active", True):
                    center = (
                        int(obs["x"] + obs["w"] / 2),
                        int(obs["y"] + obs["h"] / 2),
                    )
                    axes = (int(obs["w"] / 2), int(obs["h"] / 2))
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
        jitter_x = (
            random.randint(-CAMERA_JITTER, CAMERA_JITTER) if CAMERA_JITTER > 0 else 0
        )
        jitter_y = (
            random.randint(-CAMERA_JITTER, CAMERA_JITTER) if CAMERA_JITTER > 0 else 0
        )

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
                    cv2.line(
                        rain_overlay, (rx, ry), (rx - 10, ry + 30), (150, 150, 150), 1
                    )
                camera_feed = cv2.addWeighted(rain_overlay, 0.4, camera_feed, 0.6, 0)

        # 3. Image Noise
        if NOISE_TYPE != "None":
            if NOISE_TYPE == "Salt & Pepper":
                prob = NOISE_STD_DEV / 200.0  # e.g., 20/200 = 10%
                rnd = np.random.rand(CAM_HEIGHT, CAM_WIDTH)
                camera_feed[rnd < (prob / 2)] = 0
                camera_feed[rnd > 1 - (prob / 2)] = 255
            elif NOISE_TYPE == "Gaussian":
                gauss = np.random.normal(
                    0, NOISE_STD_DEV, (CAM_HEIGHT, CAM_WIDTH)
                ).astype(np.float32)
                noisy = np.clip(camera_feed.astype(np.float32) + gauss, 0, 255).astype(
                    np.uint8
                )
                camera_feed = noisy
            elif NOISE_TYPE == "Poisson":
                # Poisson noise is dependent on pixel intensity. Scale by std dev.
                noisy = np.random.poisson(
                    camera_feed.astype(np.float32) / (NOISE_STD_DEV + 1)
                ) * (NOISE_STD_DEV + 1)
                camera_feed = np.clip(noisy, 0, 255).astype(np.uint8)

        # --- 3. COMPUTER VISION TRACKER (AI SERVICE) ---
        # The AI doesn't know it's a simulation. It just takes an image and camera encoder positions.
        # We pass the obstacle positions so the tracker can find where the target will exit the cloud.
        active_obs_for_tracker = (
            [
                {"x": int(o["x"]), "y": int(o["y"]), "w": int(o["w"]), "h": int(o["h"])}
                for o in obstacles
                if o.get("active", True)
            ]
            if OBSTACLES_ENABLED
            else []
        )

        # Build environment params dict for adaptive tracker pipeline
        env_params = {
            "atmospheric":     ATMOSPHERIC,
            "noise_type":      NOISE_TYPE,
            "noise_std":       NOISE_STD_DEV,
            "camera_jitter":   CAMERA_JITTER,
            "platform_motion": PLATFORM_MOTION,
        }

        error_x, error_y, rmse, status_str, log_msg = tracker.update(
            camera_feed,
            cam_x,
            cam_y,
            current_path=TARGET_PATH,
            obstacles=active_obs_for_tracker,
            env_params=env_params,
        )

        # Rolling RMSE history for error graph
        rmse_history.append(round(rmse, 2))
        if len(rmse_history) > 150:
            rmse_history.pop(0)

        # --- UPDATE PERFORMANCE METRICS ---
        if not hasattr(tracker, "sum_squared_error"):
            tracker.sum_squared_error = 0.0
            tracker.sum_absolute_error = 0.0
            
        tracker.sum_squared_error += (error_x**2 + error_y**2)
        tracker.sum_absolute_error += rmse
        
        if rmse > max_error:
            max_error = rmse

        if status_str in ["TRACKING", "DISTURBED", "ACQUIRING"]:
            locked_frames += 1
            if not initial_lock_achieved:
                acquisition_time = time.time() - sim_start_time
                initial_lock_achieved = True
        else:
            lost_frames += 1

        avg_error = tracker.sum_absolute_error / frame_count
        global_rmse = math.sqrt(tracker.sum_squared_error / frame_count)
        
        lock_retention_rate = (
            (locked_frames / (locked_frames + lost_frames)) * 100
            if (locked_frames + lost_frames) > 0
            else 0
        )
        current_fps = (
            frame_count / (time.time() - sim_start_time)
            if time.time() - sim_start_time > 0
            else FPS
        )

        # --- 4. TELEMETRY OUTPUT (STEP 6) ---
        # Package the data as JSON and print it to stdout for the Node server to catch
        active_obstacles = [
            {"x": int(o["x"]), "y": int(o["y"]), "w": int(o["w"]), "h": int(o["h"])}
            for o in obstacles
            if o.get("active", True)
        ]

        # Build human-readable environment mode string for the UI
        env_parts = []
        if ATMOSPHERIC != "Clear":
            env_parts.append(ATMOSPHERIC)
        if NOISE_TYPE != "None":
            env_parts.append(NOISE_TYPE)
        if CAMERA_JITTER > 0:
            env_parts.append(f"Jitter±{CAMERA_JITTER}")
        if PLATFORM_MOTION != "None":
            env_parts.append(f"Plat:{PLATFORM_MOTION}")
        env_mode_str = " | ".join(env_parts) if env_parts else "Clear"

        telemetry = {
            "target": {"x": true_x, "y": true_y},
            "camera": {"x": cam_x, "y": cam_y},
            "error": {"x": error_x, "y": error_y, "rmse": rmse},
            "status": status_str,
            "env_mode": env_mode_str,
            "rmse_history": rmse_history,
            "obstacles": active_obstacles if OBSTACLES_ENABLED else [],
            "performance": {
                "duration": time.time() - sim_start_time,
                "fps": current_fps,
                "acquisition_time": acquisition_time,
                "avg_error": avg_error,
                "global_rmse": global_rmse,
                "max_error": max_error,
                "lock_retention_rate": lock_retention_rate,
            },
        }
        
        if DUAL_TARGET_ENABLED:
            telemetry["target2"] = {"x": int(t2_x), "y": int(t2_y)}

        # If Kalman Coasting is active, include the prediction for the UI
        if status_str == "KALMAN COASTING":
            telemetry["coasting_coord"] = {
                "x": int(tracker.kf.statePre[0, 0]),
                "y": int(tracker.kf.statePre[1, 0]),
            }

            # Send the remaining GRU predicted path for the UI to draw!
            if hasattr(tracker, "gru_sequence") and tracker.gru_sequence:
                telemetry["predicted_path"] = [
                    {"x": int(p[0]), "y": int(p[1])} for p in tracker.gru_sequence[:50]
                ]

            # Send re-acquisition point if active
            if hasattr(tracker, "reacq_point") and tracker.reacq_point:
                telemetry["reacq_point"] = {
                    "x": int(tracker.reacq_point[0]),
                    "y": int(tracker.reacq_point[1]),
                }

        # If the AI produced a text log, send it to the UI!
        if log_msg:
            telemetry["log"] = log_msg
            
        # Tag the telemetry with the mode
        telemetry["mode"] = "simulation"

        # Print JSON so Node.js can read it (using flush=True to prevent buffering lag)
        import json

        print(json.dumps(telemetry), flush=True)

        # --- 5. HEADLESS TIMING ---
        # Instead of cv2.waitKey blocking and rendering windows, we simply sleep to maintain 30 FPS
        time.sleep(DELAY_MS / 1000.0)


if __name__ == "__main__":
    main()
