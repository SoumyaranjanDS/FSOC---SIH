import cv2
import numpy as np
import time
from kalman_tracker import KalmanTracker

def main():
    print("Starting Live Webcam Virtual PTZ Mode...")
    
    # Attempt to open webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    # Try to set high resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    
    # Read first frame to get actual resolution
    ret, frame = cap.read()
    if not ret:
        print("Error: Could not read frame from webcam.")
        return
        
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Webcam initialized at {actual_width}x{actual_height}")
    
    # Virtual PTZ Configuration
    PTZ_WIDTH = 640
    PTZ_HEIGHT = 480
    
    # Initialize Camera position at the center
    cam_x = (actual_width // 2) - (PTZ_WIDTH // 2)
    cam_y = (actual_height // 2) - (PTZ_HEIGHT // 2)
    
    # Initialize Kalman Tracker
    # Note: We pass actual_width/height as world bounds
    tracker = KalmanTracker(
        initial_world_x=actual_width // 2,
        initial_world_y=actual_height // 2,
        cam_width=PTZ_WIDTH,
        cam_height=PTZ_HEIGHT,
        world_size=max(actual_width, actual_height),
        video_mode=True
    )
    
    # PTZ Motor Simulation Constants
    MAX_SPEED = 30.0
    
    print("--------------------------------------------------")
    print("Controls:")
    print("  Use a flashlight or bright light source in front of the camera.")
    print("  The Virtual PTZ (640x480 crop) will track it.")
    print("  Press 'q' to quit.")
    print("--------------------------------------------------")
    
    env_params = {
        "atmospheric": "Clear",
        "noise_type": "None"
    }

    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Flip horizontally for mirror effect (more intuitive for webcam)
        frame = cv2.flip(frame, 1)

        # 1. EXTRACT VIEWPORT (Virtual PTZ Crop)
        # Ensure camera is within bounds
        cam_x = max(0, min(cam_x, actual_width - PTZ_WIDTH))
        cam_y = max(0, min(cam_y, actual_height - PTZ_HEIGHT))
        
        viewport = frame[cam_y:cam_y+PTZ_HEIGHT, cam_x:cam_x+PTZ_WIDTH].copy()

        # 2. RUN KALMAN TRACKER
        error_x, error_y, status_str, confidence = tracker.update(
            viewport, 
            cam_x, 
            cam_y, 
            current_path="random", 
            env_params=env_params
        )

        # 3. MOTOR PHYSICS (Simulate PTZ movement)
        dx = max(-MAX_SPEED, min(MAX_SPEED, error_x * 0.1))
        dy = max(-MAX_SPEED, min(MAX_SPEED, error_y * 0.1))
        
        # Deadband to prevent jitter
        if abs(dx) < 1.0: dx = 0
        if abs(dy) < 1.0: dy = 0

        cam_x += int(dx)
        cam_y += int(dy)

        # 4. RENDER UI OVERLAYS
        # Draw a crosshair in the center of the PTZ view
        cv2.drawMarker(
            viewport, 
            (PTZ_WIDTH // 2, PTZ_HEIGHT // 2), 
            (0, 255, 0), 
            cv2.MARKER_CROSS, 20, 2
        )
        
        # Display the PTZ crop
        cv2.imshow("FSOC Virtual PTZ", viewport)
        
        # Also display the full frame with a rectangle showing where the PTZ camera is looking
        mini_map = cv2.resize(frame, (actual_width // 2, actual_height // 2))
        mm_cx = cam_x // 2
        mm_cy = cam_y // 2
        mm_cw = PTZ_WIDTH // 2
        mm_ch = PTZ_HEIGHT // 2
        cv2.rectangle(mini_map, (mm_cx, mm_cy), (mm_cx + mm_cw, mm_cy + mm_ch), (0, 255, 0), 2)
        cv2.imshow("Full Environment (Mini Map)", mini_map)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
