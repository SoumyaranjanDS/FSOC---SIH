import numpy as np
import math
import random
import os

WORLD_SIZE = 2000


def generate_perfect_path(path_type, num_sequences=5000, seq_length=240):
    """
    Generates training data with 3 variation types:
    - Type A (40%): Pure mathematical curves with wall bounces
    - Type B (40%): Varied starting positions with wall bounces
    - Type C (20%): Extra speed/phase jitter for robustness

    ALL types include wall bounces to match the real simulation physics exactly.
    """
    dataset = []

    count_a = int(num_sequences * 0.4)
    count_b = int(num_sequences * 0.4)

    for seq_idx in range(num_sequences):
        seq = []

        if seq_idx < count_a:
            var_type = "center"
        elif seq_idx < count_a + count_b:
            var_type = "offset"
        else:
            var_type = "jitter"

        # Speed variations
        if var_type == "jitter":
            speed = random.uniform(10.0, 20.0)
        else:
            speed = random.uniform(12.0, 18.0)

        # Phase variation
        t_phase = random.uniform(0.0, 2 * math.pi)
        bounce_x, bounce_y = 1.0, 1.0
        t_dx, t_dy = 0.0, 0.0

        # =============================================
        #  SPIRAL (Position-based, matching real sim)
        # =============================================
        if path_type == "Spiral":
            cx, cy = WORLD_SIZE // 2, WORLD_SIZE // 2

            if var_type == "center":
                spiral_r = random.uniform(10.0, 50.0)
            elif var_type == "offset":
                spiral_r = random.uniform(50.0, 500.0)
            else:
                spiral_r = random.uniform(10.0, 800.0)

            spiral_dir = random.choice([1.0, -1.0])

            for _ in range(seq_length):
                if spiral_r < 10.0:
                    spiral_r = 10.0
                omega = speed / spiral_r
                t_phase += omega

                expansion_speed = speed * 0.15 * spiral_dir
                spiral_r += expansion_speed

                t_x = cx + math.cos(t_phase) * spiral_r
                t_y = cy + math.sin(t_phase) * spiral_r

                if (
                    t_x < 100
                    or t_x > WORLD_SIZE - 100
                    or t_y < 100
                    or t_y > WORLD_SIZE - 100
                ):
                    spiral_dir = -1.0
                if spiral_r <= 20.0 and spiral_dir == -1.0:
                    spiral_dir = 1.0

                t_x = max(50, min(WORLD_SIZE - 50, t_x))
                t_y = max(50, min(WORLD_SIZE - 50, t_y))

                seq.append([t_x + random.uniform(-1, 1), t_y + random.uniform(-1, 1)])

        # =============================================
        #  CIRCULAR (Dynamic Breathing Radius, matching real sim)
        # =============================================
        elif path_type == "Circular":
            if var_type == "offset":
                circle_cx = random.uniform(400, WORLD_SIZE - 400)
                circle_cy = random.uniform(400, WORLD_SIZE - 400)
            else:
                circle_cx, circle_cy = 1000.0, 1000.0

            circle_R = random.uniform(200.0, 800.0)
            target_circle_R = circle_R
            circle_hit_edge = False

            for _ in range(seq_length):
                # Smart Circle Physics (Dynamic Breathing Radius)
                if circle_R < target_circle_R:
                    circle_R = min(circle_R + 1.0, target_circle_R)
                elif circle_R > target_circle_R:
                    circle_R = max(circle_R - 1.0, target_circle_R)

                omega = speed / max(circle_R, 10.0)

                old_phase = t_phase
                t_phase += omega

                # Check for full 360 rotation
                if int(old_phase / (2 * math.pi)) < int(t_phase / (2 * math.pi)):
                    if not circle_hit_edge:
                        target_circle_R += 100.0  # Grow!
                    else:
                        target_circle_R = max(100.0, target_circle_R - 50.0)  # Shrink!
                    circle_hit_edge = False

                proposed_x = circle_cx + math.cos(t_phase) * circle_R
                proposed_y = circle_cy + math.sin(t_phase) * circle_R

                # Smooth Edge Sliding
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

                seq.append([t_x + random.uniform(-1, 1), t_y + random.uniform(-1, 1)])

        # =============================================
        #  FIGURE OF 8 & SINUSOIDAL (Velocity-based with bounces)
        # =============================================
        else:
            if var_type == "offset":
                t_x = random.uniform(300, WORLD_SIZE - 300)
                t_y = random.uniform(300, WORLD_SIZE - 300)
            else:
                t_x, t_y = 1000.0, 1000.0

            for _ in range(seq_length):
                omega = speed / 800.0
                t_phase += omega

                if path_type == "Figure of 8":
                    t_dx = math.cos(2 * t_phase) * speed * bounce_x
                    t_dy = math.cos(t_phase) * speed * bounce_y
                elif path_type == "Sinusoidal":
                    t_dx = speed * 0.8 * bounce_x
                    t_dy = math.cos(t_phase * 3.0) * (speed * 0.6) * bounce_y
                elif path_type == "Straight Line":
                    # For straight line, we just pick a random direction at the start and stick to it (bouncing off walls)
                    if _ == 0:
                        angle = random.uniform(0, 2 * math.pi)
                        self_t_dx = math.cos(angle) * speed
                        self_t_dy = math.sin(angle) * speed
                    t_dx = self_t_dx * bounce_x
                    t_dy = self_t_dy * bounce_y

                t_x += t_dx
                t_y += t_dy

                # Wall bounces
                if t_x < 100:
                    t_x = 100.0
                    bounce_x *= -1
                    t_dx *= -1
                elif t_x > WORLD_SIZE - 100:
                    t_x = float(WORLD_SIZE - 100)
                    bounce_x *= -1
                    t_dx *= -1
                if t_y < 100:
                    t_y = 100.0
                    bounce_y *= -1
                    t_dy *= -1
                elif t_y > WORLD_SIZE - 100:
                    t_y = float(WORLD_SIZE - 100)
                    bounce_y *= -1
                    t_dy *= -1

                seq.append([t_x + random.uniform(-1, 1), t_y + random.uniform(-1, 1)])

        dataset.append(seq)

    return np.array(dataset, dtype=np.float32)


if __name__ == "__main__":
    paths = ["Spiral", "Circular", "Figure of 8", "Sinusoidal", "Straight Line"]
    save_dir = os.path.dirname(os.path.abspath(__file__))

    for path in paths:
        print(f"Generating robust dataset for {path}...")
        data = generate_perfect_path(path, num_sequences=5000, seq_length=240)
        filename = f"trajectories_{path.replace(' ', '').lower()}.npy"
        np.save(os.path.join(save_dir, filename), data)
        print(f"Saved {filename}: {data.shape}")
