import cv2
import numpy as np
import os

WIDTH, HEIGHT = 800, 400
FPS = 30
TOTAL_FRAMES = FPS * 8  # 8 seconds of video

# True Target state (moving horizontally across the screen)
target_x = 50.0
target_y = 200.0
target_vx = 100.0  # Moves right at 100 pixels per second
target_vy = 0.0

# Tracker State (This is our rudimentary "Kalman Filter" concept)
pred_x, pred_y = target_x, target_y
est_vx, est_vy = 100.0, 0.0  # Assume we already know roughly how fast it's going
gate_radius = 50  # We will only look for targets within 50 pixels of our prediction!

output_path = os.path.join(os.path.dirname(__file__), 'lesson2_disturbances.mp4')
out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), FPS, (WIDTH, HEIGHT))

print("Running Tracking Simulation with Clutter and Obstacles...")

for frame_idx in range(TOTAL_FRAMES):
    # --- 1. SIMULATE THE WORLD ---
    world = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    
    # Move the actual target
    target_x += target_vx / FPS
    target_y += target_vy / FPS
    
    # Draw the true target (White beacon)
    cv2.circle(world, (int(target_x), int(target_y)), 8, (255, 255, 255), -1)
    
    # Add Clutter! (Random false targets/stars/streetlamps)
    # We spawn 10 random bright dots every single frame to try and confuse the tracker
    for _ in range(10):
        rx = np.random.randint(0, WIDTH)
        ry = np.random.randint(0, HEIGHT)
        cv2.circle(world, (rx, ry), 6, (200, 200, 200), -1)
        
    # Draw an Obstacle (A giant dark gray building in the middle)
    # If the target is behind this box, we paint over it to hide it!
    cv2.rectangle(world, (300, 100), (500, 300), (50, 50, 50), -1)
    if 300 < target_x < 500:
        cv2.rectangle(world, (300, 100), (500, 300), (50, 50, 50), -1) 
        
    # --- 2. VISION AND TRACKING ALGORITHM ---
    gray = cv2.cvtColor(world, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # PREDICTION PHASE: Coasting using our last known velocity
    pred_x += est_vx / FPS
    pred_y += est_vy / FPS
    
    best_match = None
    min_dist = float('inf')
    
    # DATA ASSOCIATION & GATING: Look at every bright dot on screen
    for c in contours:
        M = cv2.moments(c)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Calculate how far this dot is from where we PREDICTED the beacon would be
            dist = np.sqrt((cx - pred_x)**2 + (cy - pred_y)**2)
            
            # GATING: Ignore it entirely if it's outside our search radius!
            if dist < gate_radius and dist < min_dist:
                min_dist = dist
                best_match = (cx, cy)
                
    # UPDATE PHASE
    if best_match is not None:
        # We found a dot inside our gate! Update our prediction to snap to reality.
        measured_x, measured_y = best_match
        
        alpha = 0.5
        beta = 0.1
        
        # Calculate error
        err_x = measured_x - pred_x
        err_y = measured_y - pred_y
        
        # Update our estimated velocity
        est_vx += err_x * beta * FPS 
        est_vy += err_y * beta * FPS
        
        # Snap prediction towards measurement
        pred_x += err_x * alpha
        pred_y += err_y * alpha
        
        cv2.putText(world, "STATUS: TRACKING", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.drawMarker(world, (int(pred_x), int(pred_y)), (0, 255, 0), cv2.MARKER_CROSS, 20, 2)
    else:
        # OCCLUSION: We see absolutely nothing inside our gate.
        # But we don't panic! We just draw a circle where we predict it is based on velocity.
        cv2.putText(world, "STATUS: OCCLUDED (PREDICTING)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
        cv2.circle(world, (int(pred_x), int(pred_y)), 10, (0, 165, 255), 2)

    # Draw the search gate (The dark green circle)
    # This visually proves we are ignoring all the other white dots on screen!
    cv2.circle(world, (int(pred_x), int(pred_y)), gate_radius, (0, 100, 0), 1)

    out.write(world)

out.release()
print(f"Simulation complete. Video saved to {output_path}")
