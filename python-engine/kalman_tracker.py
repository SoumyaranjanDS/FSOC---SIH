import cv2
import numpy as np
import math


class KalmanTracker:
    """
    AI Tracker using a Physics-Aware Kalman Filter.
    When the target is lost, the Kalman Filter coasts on its predicted trajectory.
    If the prediction hits the physical simulation boundaries, we manually
    invert the velocity matrix inside the Kalman Filter to make it bounce!
    """

    def __init__(self, initial_world_x, initial_world_y, cam_width=640, cam_height=480, world_size=2000):
        """
        Initializes the AI Tracker with a Kalman Filter.
        """
        self.cam_width = cam_width
        self.cam_height = cam_height
        self.world_size = world_size

        # --- KALMAN FILTER (6D State: [x, y, dx, dy, ddx, ddy]) ---
        self.kf = cv2.KalmanFilter(6, 2)

        # Measurement matrix: we only measure [x, y]
        self.kf.measurementMatrix = np.array(
            [[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0]], np.float32
        )

        # Transition matrix: x = x + dx + 0.5*ddx, dx = dx + ddx
        self.kf.transitionMatrix = np.array(
            [
                [1, 0, 1, 0, 0.5, 0],
                [0, 1, 0, 1, 0, 0.5],
                [0, 0, 1, 0, 1, 0],
                [0, 0, 0, 1, 0, 1],
                [0, 0, 0, 0, 1, 0],
                [0, 0, 0, 0, 0, 1],
            ],
            np.float32,
        )

        self.kf.processNoiseCov = np.eye(6, dtype=np.float32) * 0.03

        # Set starting position (prevents initial velocity spikes)
        initial_state = np.array(
            [[initial_world_x], [initial_world_y], [0], [0], [0], [0]], np.float32
        )
        self.kf.statePre = initial_state.copy()
        self.kf.statePost = initial_state.copy()

        self.lost_frames = 0
        self.was_lost = False
        
        # --- MEASUREMENT HISTORY (for true velocity computation) ---
        self.history_length = 20
        self.measurement_history = []  # List of (x, y) tuples, last 20 actual measurements

    # ------------------------------------------------------------------
    #  MAIN UPDATE LOOP
    # ------------------------------------------------------------------

    def update(self, frame, cam_x, cam_y):
        """
        Takes a raw image frame and the current camera encoder positions (cam_x, cam_y).
        Returns the calculated error (error_x, error_y), RMSE, tracking status, and log message.
        """
        # 1. Kalman Prediction (Where do we THINK the beacon is?)
        # We always call predict to move the internal state forward.
        prediction = self.kf.predict()
        pred_world_x = prediction[0, 0]
        pred_world_y = prediction[1, 0]

        # 2. Computer Vision: Thresholding and Contours
        _, thresh = cv2.threshold(frame, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        status_str = "LOST"
        error_x = 0
        error_y = 0
        log_msg = None

        if len(contours) > 0:
            c = max(contours, key=cv2.contourArea)
            M = cv2.moments(c)
            if M["m00"] != 0:
                # Raw camera coordinates
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])

                # Convert to Absolute World Coordinates for the Kalman Filter
                world_cx = cam_x + cx
                world_cy = cam_y + cy

                # Correct the Kalman Filter with the true measurement
                measurement = np.array([[np.float32(world_cx)], [np.float32(world_cy)]])
                self.kf.correct(measurement)

                # Calculate the error using the true measurement
                error_x = world_cx - (cam_x + self.cam_width // 2)
                error_y = world_cy - (cam_y + self.cam_height // 2)

                status_str = "TRACKING"
                self.lost_frames = 0
                
                # Record this measurement in the history buffer
                self.measurement_history.append((world_cx, world_cy))
                if len(self.measurement_history) > self.history_length:
                    self.measurement_history.pop(0)

                if self.was_lost:
                    log_msg = "[KalmanTracker] Target RE-ACQUIRED from Coasting!"
                    self.was_lost = False

        # ----------------------------------------------------------
        #  PHYSICS-AWARE KALMAN COASTING
        # ----------------------------------------------------------
        if status_str == "LOST":
            self.lost_frames += 1
            self.was_lost = True
            
            # If this is the very first frame of loss, we will override the Kalman's 
            # velocity with our highly-accurate 20-frame historical true velocity.
            # This ensures the coasting trajectory is perfectly smooth.
            if self.lost_frames == 1 and len(self.measurement_history) >= 2:
                p_old = self.measurement_history[0]
                p_new = self.measurement_history[-1]
                dt = len(self.measurement_history) - 1
                true_vx = (p_new[0] - p_old[0]) / float(dt)
                true_vy = (p_new[1] - p_old[1]) / float(dt)
                
                # Inject the true velocity into the Kalman Filter state
                self.kf.statePre[2, 0] = true_vx
                self.kf.statePre[3, 0] = true_vy
                self.kf.statePost[2, 0] = true_vx
                self.kf.statePost[3, 0] = true_vy
                
                log_msg = f"[KalmanTracker] Target LOST! Coasting at exact vector: ({true_vx:.1f}, {true_vy:.1f}) px/frame"

            # FORCE ZERO ACCELERATION DURING COASTING
            # If we don't zero out the acceleration state (ddx, ddy), the Kalman Filter 
            # will continue to apply the last known chaotic acceleration every frame,
            # causing the coasting trajectory to curve out of control!
            self.kf.statePre[4, 0] = 0.0
            self.kf.statePre[5, 0] = 0.0
            self.kf.statePost[4, 0] = 0.0
            self.kf.statePost[5, 0] = 0.0

            # --- WALL BOUNCE PHYSICS ---
            # If the Kalman Filter's state predicts it has crossed the physical boundaries,
            # we must mathematically force the state matrix to bounce.
            margin = 100
            
            # X-axis Bounces
            if self.kf.statePre[0, 0] < margin:
                self.kf.statePre[0, 0] = 2 * margin - self.kf.statePre[0, 0]
                self.kf.statePre[2, 0] *= -1  # Invert X velocity
            elif self.kf.statePre[0, 0] > self.world_size - margin:
                self.kf.statePre[0, 0] = 2 * (self.world_size - margin) - self.kf.statePre[0, 0]
                self.kf.statePre[2, 0] *= -1

            # Y-axis Bounces
            if self.kf.statePre[1, 0] < margin:
                self.kf.statePre[1, 0] = 2 * margin - self.kf.statePre[1, 0]
                self.kf.statePre[3, 0] *= -1  # Invert Y velocity
            elif self.kf.statePre[1, 0] > self.world_size - margin:
                self.kf.statePre[1, 0] = 2 * (self.world_size - margin) - self.kf.statePre[1, 0]
                self.kf.statePre[3, 0] *= -1
            
            # Synchronize Post state to Pre state so the bounce becomes permanent in the filter
            self.kf.statePost[0, 0] = self.kf.statePre[0, 0]
            self.kf.statePost[1, 0] = self.kf.statePre[1, 0]
            self.kf.statePost[2, 0] = self.kf.statePre[2, 0]
            self.kf.statePost[3, 0] = self.kf.statePre[3, 0]
            
            # The newly corrected prediction
            pred_world_x = self.kf.statePre[0, 0]
            pred_world_y = self.kf.statePre[1, 0]
            
            error_x = int(pred_world_x - (cam_x + self.cam_width // 2))
            error_y = int(pred_world_y - (cam_y + self.cam_height // 2))
            
            status_str = "KALMAN COASTING"

        # Calculate RMSE (Root Mean Square Error)
        rmse = math.sqrt(error_x**2 + error_y**2)

        return error_x, error_y, round(rmse, 2), status_str, log_msg
