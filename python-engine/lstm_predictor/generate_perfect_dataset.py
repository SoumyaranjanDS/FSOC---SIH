import numpy as np
import math
import random
import os

WORLD_SIZE = 2000

def generate_perfect_path(path_type, num_sequences=5000, seq_length=240):
    """
    Generates training data with 4 variation types:
    - Type A (25%): Pure mathematical curves with wall bounces
    - Type B (25%): Varied starting positions with wall bounces
    - Type C (25%): Camera Jitter & Env Noise (High frequency noise & drift)
    - Type D (25%): Obstacle Occlusion (Simulated Kalman Coasting loss of signal)
    """
    dataset = []

    count_a = int(num_sequences * 0.25)
    count_b = int(num_sequences * 0.25)
    count_c = int(num_sequences * 0.25)
    
    for seq_idx in range(num_sequences):
        seq = []

        if seq_idx < count_a:
            var_type = "center"
        elif seq_idx < count_a + count_b:
            var_type = "offset"
        elif seq_idx < count_a + count_b + count_c:
            var_type = "jitter_env"
        else:
            var_type = "occlusion"

        # Speed variations
        speed = random.uniform(10.0, 20.0)

        # Phase variation
        t_phase = random.uniform(0.0, 2 * math.pi)
        bounce_x, bounce_y = 1.0, 1.0
        t_dx, t_dy = 0.0, 0.0
        
        # State for Random Path
        t_ax, t_ay = 0.0, 0.0

        # Starting position setup
        if var_type in ["offset", "jitter_env", "occlusion"]:
            t_x = random.uniform(300, WORLD_SIZE - 300)
            t_y = random.uniform(300, WORLD_SIZE - 300)
            circle_cx, circle_cy = t_x, t_y
        else:
            t_x, t_y = 1000.0, 1000.0
            circle_cx, circle_cy = 1000.0, 1000.0

        spiral_r = random.uniform(10.0, 500.0)
        spiral_dir = random.choice([1.0, -1.0])
        
        circle_R = random.uniform(200.0, 800.0)
        target_circle_R = circle_R
        circle_hit_edge = False
        
        if path_type == "Straight Line":
            angle = random.uniform(0, 2 * math.pi)
            self_t_dx = math.cos(angle) * speed
            self_t_dy = math.sin(angle) * speed
        elif path_type == "Random":
            self_t_dx = random.uniform(-10, 10)
            self_t_dy = random.uniform(-10, 10)

        # Occlusion state variables
        is_occluded = False
        occlusion_timer = 0
        coast_vx, coast_vy = 0.0, 0.0
        last_clean_x, last_clean_y = t_x, t_y

        for step in range(seq_length):
            # True Physics Update
            if path_type == "Spiral":
                if spiral_r < 10.0:
                    spiral_r = 10.0
                omega = speed / spiral_r
                t_phase += omega

                expansion_speed = speed * 0.15 * spiral_dir
                spiral_r += expansion_speed

                t_x = circle_cx + math.cos(t_phase) * spiral_r
                t_y = circle_cy + math.sin(t_phase) * spiral_r

                if (t_x < 100 or t_x > WORLD_SIZE - 100 or t_y < 100 or t_y > WORLD_SIZE - 100):
                    spiral_dir = -1.0
                if spiral_r <= 20.0 and spiral_dir == -1.0:
                    spiral_dir = 1.0

            elif path_type == "Circular":
                if circle_R < target_circle_R:
                    circle_R = min(circle_R + 1.0, target_circle_R)
                elif circle_R > target_circle_R:
                    circle_R = max(circle_R - 1.0, target_circle_R)

                omega = speed / max(circle_R, 10.0)
                old_phase = t_phase
                t_phase += omega

                if int(old_phase / (2 * math.pi)) < int(t_phase / (2 * math.pi)):
                    if not circle_hit_edge:
                        target_circle_R += 100.0
                    else:
                        target_circle_R = max(100.0, target_circle_R - 50.0)
                    circle_hit_edge = False

                proposed_x = circle_cx + math.cos(t_phase) * circle_R
                proposed_y = circle_cy + math.sin(t_phase) * circle_R

                if proposed_x < 100:
                    circle_cx += 100 - proposed_x
                    circle_hit_edge = True
                elif proposed_x > WORLD_SIZE - 100:
                    circle_cx -= proposed_x - (WORLD_SIZE - 100)
                    circle_hit_edge = True

                if proposed_y < 100:
                    circle_cy += 100 - proposed_y
                    circle_hit_edge = True
                elif proposed_y > WORLD_SIZE - 100:
                    circle_cy -= proposed_y - (WORLD_SIZE - 100)
                    circle_hit_edge = True

                t_x = circle_cx + math.cos(t_phase) * circle_R
                t_y = circle_cy + math.sin(t_phase) * circle_R

            elif path_type == "Random":
                if step % 15 == 0:
                    max_accel = speed * 0.15
                    t_ax = random.uniform(-max_accel, max_accel)
                    t_ay = random.uniform(-max_accel, max_accel)

                desired_dx = self_t_dx + t_ax
                desired_dy = self_t_dy + t_ay
                desired_speed = math.hypot(desired_dx, desired_dy)
                current_speed = math.hypot(self_t_dx, self_t_dy)
                
                if current_speed > 0.1 and desired_speed > 0.1:
                    current_heading = math.atan2(self_t_dy, self_t_dx)
                    desired_heading = math.atan2(desired_dy, desired_dx)
                    angle_diff = math.atan2(math.sin(desired_heading - current_heading), math.cos(desired_heading - current_heading))
                    max_turn_rad = math.radians(40.0 / 30.0)
                    angle_diff = max(-max_turn_rad, min(max_turn_rad, angle_diff))
                    new_heading = current_heading + angle_diff
                    self_t_dx = math.cos(new_heading) * desired_speed
                    self_t_dy = math.sin(new_heading) * desired_speed
                else:
                    self_t_dx, self_t_dy = desired_dx, desired_dy

                s = math.hypot(self_t_dx, self_t_dy)
                if s > speed:
                    self_t_dx = (self_t_dx / s) * speed
                    self_t_dy = (self_t_dy / s) * speed
                    
                t_dx = self_t_dx * bounce_x
                t_dy = self_t_dy * bounce_y
                t_x += t_dx
                t_y += t_dy
                
            else: # Figure of 8, Sinusoidal, Straight Line
                omega = speed / 800.0
                t_phase += omega

                if path_type == "Figure of 8":
                    t_dx = math.cos(2 * t_phase) * speed * bounce_x
                    t_dy = math.cos(t_phase) * speed * bounce_y
                elif path_type == "Sinusoidal":
                    t_dx = speed * 0.8 * bounce_x
                    t_dy = math.cos(t_phase * 3.0) * (speed * 0.6) * bounce_y
                elif path_type == "Straight Line":
                    t_dx = self_t_dx * bounce_x
                    t_dy = self_t_dy * bounce_y

                t_x += t_dx
                t_y += t_dy

            # Wall bounces
            if t_x < 100:
                t_x = 100.0
                bounce_x *= -1
                if path_type in ["Random", "Straight Line"]: self_t_dx *= -1
            elif t_x > WORLD_SIZE - 100:
                t_x = float(WORLD_SIZE - 100)
                bounce_x *= -1
                if path_type in ["Random", "Straight Line"]: self_t_dx *= -1
                
            if t_y < 100:
                t_y = 100.0
                bounce_y *= -1
                if path_type in ["Random", "Straight Line"]: self_t_dy *= -1
            elif t_y > WORLD_SIZE - 100:
                t_y = float(WORLD_SIZE - 100)
                bounce_y *= -1
                if path_type in ["Random", "Straight Line"]: self_t_dy *= -1
                
            t_x = max(50, min(WORLD_SIZE - 50, t_x))
            t_y = max(50, min(WORLD_SIZE - 50, t_y))

            # --- ADD NOISE, JITTER & OCCLUSION ---
            measured_x, measured_y = t_x, t_y
            
            if var_type == "jitter_env":
                # Camera jitter + atmospheric noise
                measured_x += random.uniform(-10, 10) + math.sin(step * 0.05) * 5
                measured_y += random.uniform(-10, 10) + math.cos(step * 0.05) * 5
                
            elif var_type == "occlusion":
                if not is_occluded and random.random() < 0.02 and step > 10 and step < seq_length - 30:
                    is_occluded = True
                    occlusion_timer = random.randint(15, 30)
                    # Compute coasting velocity from last 5 frames
                    if len(seq) >= 5:
                        coast_vx = (seq[-1][0] - seq[-5][0]) / 4.0
                        coast_vy = (seq[-1][1] - seq[-5][1]) / 4.0
                    else:
                        coast_vx, coast_vy = t_dx, t_dy
                        
                if is_occluded:
                    # Simulate Kalman linear coasting output during signal loss
                    last_clean_x += coast_vx
                    last_clean_y += coast_vy
                    measured_x, measured_y = last_clean_x, last_clean_y
                    occlusion_timer -= 1
                    if occlusion_timer <= 0:
                        is_occluded = False
                else:
                    last_clean_x, last_clean_y = measured_x, measured_y
            
            # Default tiny noise
            measured_x += random.uniform(-1, 1)
            measured_y += random.uniform(-1, 1)

            seq.append([measured_x, measured_y])

        dataset.append(seq)

    return np.array(dataset, dtype=np.float32)

if __name__ == "__main__":
    paths = ["Random", "Spiral", "Circular", "Figure of 8", "Sinusoidal", "Straight Line"]
    save_dir = os.path.dirname(os.path.abspath(__file__))

    for path in paths:
        print(f"Generating robust dataset for {path}...")
        data = generate_perfect_path(path, num_sequences=5000, seq_length=240)
        filename = f"trajectories_{path.replace(' ', '').lower()}.npy"
        np.save(os.path.join(save_dir, filename), data)
        print(f"Saved {filename}: {data.shape}")
