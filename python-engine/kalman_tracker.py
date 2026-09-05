import cv2
import numpy as np
import math
import torch
import os
from lstm_predictor.train_lstm import DirectTrajectoryPredictor


class KalmanTracker:
    """
    AI Tracker using a Physics-Aware Kalman Filter with LSTM-based NLP Prediction.
    
    Re-Acquisition Strategy:
    - When the target is lost behind an obstacle, the LSTM predicts a curved path.
    - The tracker scans the predicted path to find where the target will EXIT the obstacle.
    
    Target Interception (Collision Course) Strategy:
    - When no obstacles are present, the camera does not just slowly chase the prediction.
    - It calculates the optimal interception point where the camera's travel time equals the target's travel time.
    - The camera flies directly to this point, cutting the corner to catch the target faster!
    """

    def __init__(self, initial_world_x, initial_world_y, cam_width=640, cam_height=480, world_size=2000):
        self.cam_width = cam_width
        self.cam_height = cam_height
        self.world_size = world_size

        # --- KALMAN FILTER (6D State: [x, y, dx, dy, ddx, ddy]) ---
        self.kf = cv2.KalmanFilter(6, 2)

        self.kf.measurementMatrix = np.array(
            [[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0]], np.float32
        )

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

        initial_state = np.array(
            [[initial_world_x], [initial_world_y], [0], [0], [0], [0]], np.float32
        )
        self.kf.statePre = initial_state.copy()
        self.kf.statePost = initial_state.copy()

        self.lost_frames = 0
        self.was_lost = False
        
        # --- MEASUREMENT HISTORY ---
        self.history_length = 150
        self.measurement_history = []
        
        # --- NLP SEQUENCE PREDICTOR (LSTM) ---
        self.lstm_models = {}
        self.lstm_sequence = []
        self.lstm_full_buffer = []
        self.current_path_key = ""
        
        # --- RE-ACQUISITION / INTERCEPTION ---
        self.reacq_point = None
        self.reacq_active = False
        
        try:
            model_dir = os.path.join(os.path.dirname(__file__), "lstm_predictor")
            paths = ["spiral", "circular", "figureof8", "sinusoidal", "straightline"]
            
            for path in paths:
                model_path = os.path.join(model_dir, f"lstm_{path}.pth")
                if os.path.exists(model_path):
                    model = DirectTrajectoryPredictor()
                    model.load_state_dict(torch.load(model_path))
                    model.eval()
                    self.lstm_models[path] = model
            print(f"[KalmanTracker] Loaded {len(self.lstm_models)} NLP Sequence Predictors!")
        except Exception as e:
            print(f"[KalmanTracker] Error loading LSTM models: {e}")

    # ------------------------------------------------------------------
    #  LSTM PREDICTION HELPER
    # ------------------------------------------------------------------
    def _generate_lstm_prediction(self, history_points, path_key):
        """Generate 120 future frames using the LSTM."""
        if path_key not in self.lstm_models or len(history_points) < 2:
            return []
        
        model = self.lstm_models[path_key]
        
        hist_list = list(history_points)
        while len(hist_list) < 120:
            hist_list.insert(0, hist_list[0])
        
        history_np = np.array(hist_list[-120:], dtype=np.float32)
        origin = history_np[-1].copy()
        
        history_rel = (history_np - origin) / 200.0
        history_tensor = torch.tensor(history_rel).unsqueeze(0)
        
        with torch.no_grad():
            prediction_tensor = model(history_tensor)
            
        prediction_rel = prediction_tensor.squeeze(0).numpy()
        prediction_abs = (prediction_rel * 200.0) + origin
        
        # Apply a Moving Average filter to smooth out jitter (window=7)
        smoothed_abs = np.copy(prediction_abs)
        window = 7
        for i in range(len(smoothed_abs)):
            start = max(0, i - window // 2)
            end = min(len(smoothed_abs), i + window // 2 + 1)
            smoothed_abs[i] = np.mean(prediction_abs[start:end], axis=0)
            
        prediction_abs = smoothed_abs
        
        # Enforce physical boundaries
        margin = 50
        prediction_abs[:, 0] = np.clip(prediction_abs[:, 0], margin, self.world_size - margin)
        prediction_abs[:, 1] = np.clip(prediction_abs[:, 1], margin, self.world_size - margin)
        
        # Return only a short-horizon prediction (15 frames = 0.5 seconds)
        return prediction_abs.tolist()[:15]

    # ------------------------------------------------------------------
    #  CLOUD RE-ACQUISITION FINDER
    # ------------------------------------------------------------------
    def _find_reacquisition_point(self, predicted_path, obstacles):
        if not obstacles or not predicted_path:
            return None
        
        for point in predicted_path:
            px, py = point[0], point[1]
            inside_any = False
            for obs in obstacles:
                obs_cx = obs["x"] + obs["w"] / 2.0
                obs_cy = obs["y"] + obs["h"] / 2.0
                rx = obs["w"] / 2.0
                ry = obs["h"] / 2.0
                
                if rx > 0 and ry > 0:
                    dx = (px - obs_cx) / rx
                    dy = (py - obs_cy) / ry
                    if (dx * dx + dy * dy) <= 1.0:
                        inside_any = True
                        break
            
            if not inside_any:
                return (px, py)
        
        last = predicted_path[-1]
        return (last[0], last[1])

    # ------------------------------------------------------------------
    #  TARGET INTERCEPTION (COLLISION COURSE) FINDER
    # ------------------------------------------------------------------
    def _find_interception_point(self, predicted_path, cam_x, cam_y):
        """
        Finds the optimal point to intercept the target.
        Camera max speed is ~25 px/frame.
        We find the first predicted point where camera travel time <= target travel time.
        """
        if not predicted_path:
            return None
            
        cam_center_x = cam_x + self.cam_width // 2
        cam_center_y = cam_y + self.cam_height // 2
        cam_max_speed = 35.0
        
        for frame_idx, point in enumerate(predicted_path):
            # How many frames until target reaches this point?
            target_time = frame_idx + 1 
            
            # How many frames for camera to reach this point?
            dist = math.hypot(point[0] - cam_center_x, point[1] - cam_center_y)
            camera_time = dist / cam_max_speed
            
            if camera_time <= target_time and frame_idx >= 10:
                # We can intercept here! And we have a minimum 10-frame lead (carrot on a stick)
                return (point[0], point[1])
                
        # If camera can never reach it in time (e.g. really far away), just aim at the last point
        last = predicted_path[-1]
        return (last[0], last[1])

    # ------------------------------------------------------------------
    #  MAIN UPDATE LOOP
    # ------------------------------------------------------------------

    def update(self, frame, cam_x, cam_y, current_path="Random", obstacles=None):
        if obstacles is None:
            obstacles = []
            
        prediction = self.kf.predict()
        pred_world_x = prediction[0, 0]
        pred_world_y = prediction[1, 0]

        # ----------------------------------------------------------
        #  ROBUST COMPUTER VISION PIPELINE (Noise & Weather filtering)
        # ----------------------------------------------------------
        # 1. Salt & Pepper / High-Frequency Noise Filter
        blurred = cv2.medianBlur(frame, 5)
        # 2. Gaussian Noise Filter
        blurred = cv2.GaussianBlur(blurred, (5, 5), 0)

        # 3. Dynamic Auto-Exposure (for Fog, Haze, Low Light)
        # We use the 99th percentile instead of max to ignore isolated 255 noise spikes
        percentile_val = np.percentile(blurred, 99)
        if percentile_val < 50:
            thresh_val = 200 # Fallback if image is completely blacked out
        else:
            thresh_val = max(50, int(percentile_val * 0.70)) 
            
        _, thresh = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY)

        # 4. Morphological Opening (Removes Rain Streaks and tiny leftover static)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        # 5. Smart Contour Filtering & Confidence Scoring
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        valid_contours = []
        best_contour = None
        max_area = 0
        
        for c in contours:
            area = cv2.contourArea(c)
            # The target beacon is around 10x10 to 20x20 pixels (Area 100 to 400).
            # We strictly enforce 15 to 1000 pixels to eliminate noise.
            if 15 < area < 1000:
                valid_contours.append(c)
                if area > max_area:
                    max_area = area
                    best_contour = c

        error_x = 0
        error_y = 0
        log_msg = None
        
        confidence = 0.0
        if best_contour is not None:
            # Simple confidence metric based on area (closer to 100-400 is better)
            if 50 < max_area < 500:
                confidence = 0.95
            else:
                confidence = 0.60
        
        # State Machine Logic
        if confidence > 0.8:
            status_str = "TRACKING"
        elif confidence > 0.4:
            status_str = "DISTURBED"
        else:
            status_str = "LOST"

        if status_str in ["TRACKING", "DISTURBED"] and best_contour is not None:
            M = cv2.moments(best_contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])

                world_cx = cam_x + cx
                world_cy = cam_y + cy

                measurement = np.array([[np.float32(world_cx)], [np.float32(world_cy)]])
                
                # If DISTURBED, trust the Kalman model more than the noisy camera measurement
                if status_str == "DISTURBED":
                    self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 5.0
                else:
                    self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 1e-1
                    
                self.kf.correct(measurement)

                error_x = world_cx - (cam_x + self.cam_width // 2)
                error_y = world_cy - (cam_y + self.cam_height // 2)

                self.lost_frames = 0
                
                self.measurement_history.append((world_cx, world_cy))
                if len(self.measurement_history) > self.history_length:
                    self.measurement_history.pop(0)

                if self.was_lost:
                    log_msg = f"[KalmanTracker] Target RE-ACQUIRED from Coasting (Confidence: {confidence:.2f})"
                    self.was_lost = False
                    self.lstm_sequence = []
                    self.lstm_full_buffer = []
                    self.reacq_point = None
                    self.reacq_active = False

        # ----------------------------------------------------------
        #  COASTING WITH INTERCEPTION & RE-ACQUISITION
        # ----------------------------------------------------------
        if status_str == "LOST":
            self.lost_frames += 1
            self.was_lost = True
            
            path_key = current_path.lower().replace(" ", "").replace("of", "")
            path_map = {
                "circular": "circular",
                "spiral": "spiral",
                "figure8": "figureof8",
                "figureof8": "figureof8",
                "sinusoidal": "sinusoidal",
            }
            path_key = path_map.get(path_key, "")
            
            # === FIRST FRAME OF LOSS ===
            if self.lost_frames == 1:
                self.current_path_key = path_key
                
                if path_key in self.lstm_models and len(self.measurement_history) >= 2:
                    self.lstm_sequence = self._generate_lstm_prediction(
                        self.measurement_history, path_key
                    )
                    self.lstm_full_buffer = list(self.measurement_history[-120:]) + self.lstm_sequence.copy()
                    
                    if obstacles and len(obstacles) > 0:
                        self.reacq_point = self._find_reacquisition_point(self.lstm_sequence, obstacles)
                        self.reacq_active = True
                        log_msg = f"[KalmanTracker] Target LOST behind cloud! Camera moving directly to exit point."
                    else:
                        self.reacq_active = False
                        # We will calculate interception point dynamically every frame
                        log_msg = f"[KalmanTracker] Target LOST (no cloud)! Initiating Target Interception (Collision Course)..."
                    
                elif len(self.measurement_history) >= 2:
                    # Linear fallback
                    recent = self.measurement_history[-40:] if len(self.measurement_history) >= 40 else self.measurement_history
                    p_old = recent[0]
                    p_new = recent[-1]
                    dt = len(recent) - 1
                    true_vx = (p_new[0] - p_old[0]) / float(dt)
                    true_vy = (p_new[1] - p_old[1]) / float(dt)
                    
                    self.kf.statePre[2, 0] = true_vx
                    self.kf.statePre[3, 0] = true_vy
                    self.kf.statePost[2, 0] = true_vx
                    self.kf.statePost[3, 0] = true_vy
                    
                    log_msg = f"[KalmanTracker] Target LOST! Linear Coasting at ({true_vx:.1f}, {true_vy:.1f}) px/frame"

            # === ROLLING PREDICTION ===
            if self.lstm_sequence and len(self.lstm_sequence) < 30 and self.current_path_key in self.lstm_models:
                tail_history = self.lstm_full_buffer[-120:]
                new_prediction = self._generate_lstm_prediction(tail_history, self.current_path_key)
                if new_prediction:
                    self.lstm_sequence.extend(new_prediction)
                    self.lstm_full_buffer.extend(new_prediction)
                    if len(self.lstm_full_buffer) > 500:
                        self.lstm_full_buffer = self.lstm_full_buffer[-300:]

            # FORCE ZERO ACCELERATION
            self.kf.statePre[4, 0] = 0.0
            self.kf.statePre[5, 0] = 0.0
            self.kf.statePost[4, 0] = 0.0
            self.kf.statePost[5, 0] = 0.0

            # === DETERMINE WHERE TO POINT THE CAMERA ===
            if self.lstm_sequence and len(self.lstm_sequence) > 0:
                # Pop the next ghost particle position
                next_point = self.lstm_sequence.pop(0)
                pred_world_x = next_point[0]
                pred_world_y = next_point[1]
                
                # Sync Kalman state to current ghost position
                nlp_vx = pred_world_x - self.kf.statePre[0, 0]
                nlp_vy = pred_world_y - self.kf.statePre[1, 0]
                
                self.kf.statePre[0, 0] = pred_world_x
                self.kf.statePre[1, 0] = pred_world_y
                self.kf.statePre[2, 0] = nlp_vx
                self.kf.statePre[3, 0] = nlp_vy
                self.kf.statePost[0, 0] = pred_world_x
                self.kf.statePost[1, 0] = pred_world_y
                self.kf.statePost[2, 0] = nlp_vx
                self.kf.statePost[3, 0] = nlp_vy
                
                if self.reacq_active and self.reacq_point is not None:
                    # Cloud Exit Pointing
                    error_x = int(self.reacq_point[0] - (cam_x + self.cam_width // 2))
                    error_y = int(self.reacq_point[1] - (cam_y + self.cam_height // 2))
                else:
                    # TARGET INTERCEPTION (No Clouds)
                    intercept_pt = self._find_interception_point(self.lstm_sequence, cam_x, cam_y)
                    if intercept_pt:
                        # Report the interception point for the UI to draw
                        self.reacq_point = intercept_pt
                        error_x = int(intercept_pt[0] - (cam_x + self.cam_width // 2))
                        error_y = int(intercept_pt[1] - (cam_y + self.cam_height // 2))
                    else:
                        error_x = int(pred_world_x - (cam_x + self.cam_width // 2))
                        error_y = int(pred_world_y - (cam_y + self.cam_height // 2))
            else:
                # Kalman linear coasting
                margin = 100
                if self.kf.statePre[0, 0] < margin:
                    self.kf.statePre[0, 0] = 2 * margin - self.kf.statePre[0, 0]
                    self.kf.statePre[2, 0] *= -1
                elif self.kf.statePre[0, 0] > self.world_size - margin:
                    self.kf.statePre[0, 0] = 2 * (self.world_size - margin) - self.kf.statePre[0, 0]
                    self.kf.statePre[2, 0] *= -1

                if self.kf.statePre[1, 0] < margin:
                    self.kf.statePre[1, 0] = 2 * margin - self.kf.statePre[1, 0]
                    self.kf.statePre[3, 0] *= -1
                elif self.kf.statePre[1, 0] > self.world_size - margin:
                    self.kf.statePre[1, 0] = 2 * (self.world_size - margin) - self.kf.statePre[1, 0]
                    self.kf.statePre[3, 0] *= -1
                
                self.kf.statePost[0, 0] = self.kf.statePre[0, 0]
                self.kf.statePost[1, 0] = self.kf.statePre[1, 0]
                self.kf.statePost[2, 0] = self.kf.statePre[2, 0]
                self.kf.statePost[3, 0] = self.kf.statePre[3, 0]
                
                pred_world_x = self.kf.statePre[0, 0]
                pred_world_y = self.kf.statePre[1, 0]
                
                error_x = int(pred_world_x - (cam_x + self.cam_width // 2))
                error_y = int(pred_world_y - (cam_y + self.cam_height // 2))
            
            status_str = "KALMAN COASTING"

        rmse = math.sqrt(error_x**2 + error_y**2)
        return error_x, error_y, round(rmse, 2), status_str, log_msg
