import cv2
import numpy as np
import os

def generate_video(output_path="test_kalman.mp4", width=2000, height=2000, fps=30, duration=10):
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = fps * duration
    
    # Beacon parameters
    start_x, start_y = 200, 1000
    end_x, end_y = 1800, 1000
    beacon_size = 10
    
    # Obstacle parameters
    obs_x1, obs_y1 = 900, 800
    obs_x2, obs_y2 = 1100, 1200

    print(f"Generating {duration}s video at {fps}fps...")

    for i in range(total_frames):
        # Create a dark landscape background (noise)
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Add some slight static noise to make it look like a real noisy sensor
        noise = np.random.randint(0, 30, (height, width, 3), dtype=np.uint8)
        frame = cv2.add(frame, noise)

        # Calculate beacon position (linear interpolation)
        progress = i / total_frames
        bx = int(start_x + (end_x - start_x) * progress)
        by = int(start_y + (end_y - start_y) * progress)

        # Draw the glowing beacon
        cv2.circle(frame, (bx, by), beacon_size + 5, (200, 200, 200), -1)  # glow
        cv2.circle(frame, (bx, by), beacon_size, (255, 255, 255), -1)      # core

        # Draw the Obstacle (Opaque grey cloud/structure that hides the beacon)
        cv2.rectangle(frame, (obs_x1, obs_y1), (obs_x2, obs_y2), (50, 50, 50), -1)

        # Optional: Add simulated rain/atmospheric noise over everything
        if i % 2 == 0:
            for _ in range(300):
                rx = np.random.randint(0, width)
                ry = np.random.randint(0, height)
                cv2.line(frame, (rx, ry), (rx - 5, ry + 20), (100, 100, 100), 1)

        out.write(frame)
        
        if i % 30 == 0:
            print(f"Rendered {i}/{total_frames} frames...")

    out.release()
    print(f"Saved {output_path} successfully!")

if __name__ == "__main__":
    import sys
    # Save it to the user's desktop or current dir
    out_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(out_dir, "test_kalman.mp4")
    generate_video(output_file)
