import cv2
import numpy as np
import math
import torch
import os
import sys

# Import models directly from their respective packages
from gru_predictor.train_gru import GRUPredictor
from cnn_detector.cnn_model import BeaconCNN


class KalmanTracker:
    """
    AI Tracker using a Physics-Aware Kalman Filter with GRU-based NLP Prediction and CNN Detection.

    Environment-Adaptive Pipeline:
    - CV pre-processing automatically adapts to Fog, Rain, Low Light, Haze, Noise, and Jitter.
    - Kalman process/measurement noise is tuned per environment so the filter reacts correctly.
    - GRU lookahead shrinks under Platform Motion to avoid stale predictions.
    - Path-aware smoothing preserves sharp turns on Spiral/Figure-8.
    - Platform motion compensation subtracts camera-base drift from the motor error.
    - Status overlay is burned into the camera feed for visual debugging.

    Re-Acquisition Strategy:
    - When the target is lost behind an obstacle, the GRU predicts a curved path.
    - The tracker scans the predicted path to find where the target will EXIT the obstacle.

    Target Interception (Collision Course) Strategy:
    - When no obstacles are present, the camera does not just slowly chase the prediction.
    - It calculates the optimal interception point where the camera's travel time equals
      the target's travel time and flies directly to this point (corner-cutting).
    """

    # -------------------------------------------------------------------------
    #  ENVIRONMENT PARAMETER TABLES (from PDF SIH-26169 + physical reasoning)
    # -------------------------------------------------------------------------
    # Process noise Q — how erratically can the beacon move per frame?
    _Q_TABLE = {
        "Clear": 0.01,
        "Haze": 0.025,
        "Fog": 0.05,
        "Low light": 0.02,
        "Rain": 0.04,
    }
    # Base measurement noise R — how much do we trust the camera detection?
    _R_TABLE = {
        "Clear": 0.1,
        "Haze": 2.0,
        "Fog": 5.0,
        "Low light": 3.0,
        "Rain": 4.0,
    }
    # Noise-type extra measurement uncertainty
    _NOISE_R_EXTRA = {
        "None": 0.0,
        "Gaussian": 3.0,
        "Salt & Pepper": 2.0,
        "Poisson": 2.5,
    }

    def __init__(
        self,
        initial_world_x,
        initial_world_y,
        cam_width=640,
        cam_height=480,
        world_size=2000,
        video_mode=False,
    ):
        self.cam_width = cam_width
        self.cam_height = cam_height
        self.world_size = world_size
        self.video_mode = video_mode

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

        self.kf.processNoiseCov = np.eye(6, dtype=np.float32) * 0.01

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

        # --- PLATFORM MOTION COMPENSATION ---
        self._prev_cam_x = float(initial_world_x) - cam_width // 2
        self._prev_cam_y = float(initial_world_y) - cam_height // 2

        # --- CNN DETECTOR ---
        self.cnn_model = None
        if not self.video_mode:
            try:
                cnn_path = os.path.join(
                os.path.dirname(__file__), "cnn_detector", "cnn_beacon.pth"
            )
                if os.path.exists(cnn_path):
                    self.cnn_model = BeaconCNN()
                    self.cnn_model.load_state_dict(torch.load(cnn_path))
                    self.cnn_model.eval()
                    print("[KalmanTracker] Loaded CNN Detector successfully!")
            except Exception as e:
                print(f"[KalmanTracker] Error loading CNN: {e}")

        # --- GRU SEQUENCE PREDICTOR ---
        self.gru_models = {}
        self.gru_sequence = []
        self.gru_full_buffer = []
        self.current_path_key = ""

        # --- RE-ACQUISITION / INTERCEPTION ---
        self.reacq_point = None
        self.reacq_active = False

        try:
            model_dir = os.path.join(os.path.dirname(__file__), "gru_predictor")
            paths = [
                "random",
                "spiral",
                "circular",
                "figureof8",
                "sinusoidal",
                "straightline",
            ]

            for path in paths:
                model_path = os.path.join(model_dir, f"gru_{path}.pth")
                if os.path.exists(model_path):
                    model = GRUPredictor()
                    model.load_state_dict(torch.load(model_path))
                    model.eval()
                    self.gru_models[path] = model
            print(f"[KalmanTracker] Loaded {len(self.gru_models)} GRU Predictors!")
        except Exception as e:
            print(f"[KalmanTracker] Error loading GRU models: {e}")

    # ------------------------------------------------------------------
    #  ADAPTIVE CV PRE-PROCESSING
    # ------------------------------------------------------------------
    def _adaptive_preprocess(self, frame, env_params):
        """
        Returns a thresholded binary mask, adapting blur, CLAHE, and threshold
        based on the active disturbance environment.
        """
        atmospheric = env_params.get("atmospheric", "Clear")
        noise_type = env_params.get("noise_type", "None")
        noise_std = env_params.get("noise_std", 20)

        # ---- Step 1: Noise-type specific de-noising ----
        if noise_type == "Salt & Pepper":
            ksize = 7 if noise_std > 30 else 5
            filtered = cv2.medianBlur(frame, ksize)
        elif noise_type in ("Gaussian", "Poisson"):
            sigma = max(1, noise_std // 10)
            ksize = 9 if noise_std > 30 else 5
            filtered = cv2.GaussianBlur(frame, (ksize, ksize), sigma)
        else:
            filtered = cv2.medianBlur(frame, 3)

        # ---- Step 2: Atmospheric-specific enhancement ----
        if atmospheric in ("Fog", "Haze"):
            # Top-hat background subtraction: removes the uniform fog/haze baseline
            # so the bright beacon stands out as a residual bright spot.
            # A large structuring element (bigger than the beacon=10px) captures
            # the local background level; subtracting it leaves only blobs brighter
            # than their immediate surroundings — i.e., the beacon.
            bg_ksize = (
                51 if atmospheric == "Fog" else 41
            )  # larger = more aggressive fog removal
            background = cv2.GaussianBlur(filtered, (bg_ksize, bg_ksize), 0)
            # Ensure no underflow (subtract carefully)
            filtered = cv2.subtract(filtered, background)
            # Now scale up the residual so threshold still works sensibly
            filtered = cv2.convertScaleAbs(filtered, alpha=4.0, beta=0)

        elif atmospheric == "Low light":
            filtered = cv2.equalizeHist(filtered)
            lut = np.array(
                [min(255, int(((i / 255.0) ** (1.0 / 2.2)) * 255)) for i in range(256)],
                dtype=np.uint8,
            )
            filtered = cv2.LUT(filtered, lut)

        elif atmospheric == "Rain":
            close_k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 7))
            filtered = cv2.morphologyEx(filtered, cv2.MORPH_CLOSE, close_k)
            filtered = cv2.GaussianBlur(filtered, (5, 5), 0)

        # ---- Step 3: Dynamic thresholding ----
        pct = np.percentile(filtered, 99)
        if pct < 20:
            thresh_val = 180
        else:
            fractions = {
                "Clear": 0.80,
                "Haze": 0.55,  # after top-hat, residual is small — use lower fraction
                "Fog": 0.45,  # after top-hat, residual is even smaller
                "Low light": 0.55,
                "Rain": 0.72,
            }
            frac = fractions.get(atmospheric, 0.70)
            thresh_val = max(15, int(pct * frac))

        _, thresh = cv2.threshold(filtered, thresh_val, 255, cv2.THRESH_BINARY)

        # ---- Step 4: Morphological cleanup ----
        if atmospheric == "Rain":
            erode_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, erode_k)
            thresh = cv2.erode(thresh, erode_k, iterations=1)
        else:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        # Return both the binary mask AND the enhanced float image for CNN cropping
        return thresh, filtered

    # ------------------------------------------------------------------
    #  ADAPTIVE KALMAN NOISE PARAMS
    # ------------------------------------------------------------------
    def _get_kalman_params(self, env_params, confidence_str):
        """
        Returns (Q, R_track, R_disturbed) noise covariances tuned per environment.
        """
        atmospheric = env_params.get("atmospheric", "Clear")
        noise_type = env_params.get("noise_type", "None")
        noise_std = env_params.get("noise_std", 20)
        platform_motion = env_params.get("platform_motion", "None")
        camera_jitter = env_params.get("camera_jitter", 0)

        Q = self._Q_TABLE.get(atmospheric, 0.03)
        R = self._R_TABLE.get(atmospheric, 0.5)

        R += self._NOISE_R_EXTRA.get(noise_type, 0.0)
        if noise_type != "None":
            R += (noise_std / 50.0) * 2.0

        if camera_jitter > 0:
            R += (camera_jitter**2) / 100.0

        if platform_motion != "None":
            Q += 0.05
            R += 2.0

        R_disturbed = R * 10.0

        return float(Q), float(R), float(R_disturbed)

    # ------------------------------------------------------------------
    #  ADAPTIVE GRU LOOKAHEAD
    # ------------------------------------------------------------------
    def _get_lookahead(self, env_params, path_key):
        """
        Returns how many frames ahead the camera should aim.
        """
        platform_motion = env_params.get("platform_motion", "None")
        atmospheric = env_params.get("atmospheric", "Clear")

        if platform_motion != "None":
            return 8
        elif atmospheric in ("Fog", "Low light"):
            return 12
        else:
            return 15

    # ------------------------------------------------------------------
    #  PLATFORM MOTION COMPENSATION
    # ------------------------------------------------------------------
    def _compensate_platform_motion(self, cam_x, cam_y, error_x, error_y, env_params):
        """
        Per PDF SIH-26169: 'The PTZ controller shall compensate for platform motion
        to stabilise the line of sight.'

        IMPORTANT: Only active when platform_motion != 'None'.
        When platform motion is disabled, intentional camera pan/tilt movements must
        NOT be compensated — they are the controller output, not disturbances.
        Compensating them would create a positive-feedback oscillation (jitter).
        """
        platform_motion = env_params.get("platform_motion", "None")

        if platform_motion == "None":
            # No platform motion: update prev and pass error through unchanged.
            # We must still update prev so it stays current for when platform
            # motion is toggled on mid-simulation.
            self._prev_cam_x = float(cam_x)
            self._prev_cam_y = float(cam_y)
            return int(error_x), int(error_y)

        # Platform is moving: compute drift BEFORE updating prev
        drift_x = cam_x - self._prev_cam_x
        drift_y = cam_y - self._prev_cam_y
        self._prev_cam_x = float(cam_x)
        self._prev_cam_y = float(cam_y)
        compensated_x = int(error_x - drift_x)
        compensated_y = int(error_y - drift_y)
        return compensated_x, compensated_y

    # ------------------------------------------------------------------
    #  STATUS OVERLAY
    # ------------------------------------------------------------------
    def _draw_overlay(self, frame, status_str, env_params, confidence):
        """Burns a status badge and environment mode onto the camera feed."""
        atmospheric = env_params.get("atmospheric", "Clear")
        noise_type = env_params.get("noise_type", "None")
        platform_motion = env_params.get("platform_motion", "None")

        colour_map = {
            "TRACKING": (0, 255, 0),
            "DISTURBED": (0, 170, 255),
            "LOST": (0, 0, 255),
            "KALMAN COASTING": (255, 0, 255),
        }
        colour = colour_map.get(status_str, (200, 200, 200))

        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], 52), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        cv2.putText(
            frame,
            f"STATUS: {status_str}",
            (6, 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            colour,
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"CONF: {confidence:.2f}",
            (6, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (200, 200, 200),
            1,
            cv2.LINE_AA,
        )

        env_parts = []
        if atmospheric != "Clear":
            env_parts.append(atmospheric.upper())
        if noise_type != "None":
            env_parts.append(noise_type.upper())
        if platform_motion != "None":
            env_parts.append(f"PLAT:{platform_motion.upper()}")
        env_label = " | ".join(env_parts) if env_parts else "CLEAR"

        cv2.putText(
            frame,
            f"ENV: {env_label}",
            (6, 46),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (0, 200, 255),
            1,
            cv2.LINE_AA,
        )

        return frame

    # ------------------------------------------------------------------
    #  GRU PREDICTION HELPER
    # ------------------------------------------------------------------
    def _generate_gru_prediction(self, history_points, path_key, smooth_window=5):
        """Generate 15 future frames using the GRU."""
        if path_key not in self.gru_models or len(history_points) < 2:
            return []

        model = self.gru_models[path_key]

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

        # Path-aware smoothing
        smoothed_abs = np.copy(prediction_abs)
        for i in range(len(smoothed_abs)):
            start = max(0, i - smooth_window // 2)
            end = min(len(smoothed_abs), i + smooth_window // 2 + 1)
            smoothed_abs[i] = np.mean(prediction_abs[start:end], axis=0)
        prediction_abs = smoothed_abs

        margin = 50
        prediction_abs[:, 0] = np.clip(
            prediction_abs[:, 0], margin, self.world_size - margin
        )
        prediction_abs[:, 1] = np.clip(
            prediction_abs[:, 1], margin, self.world_size - margin
        )

        return prediction_abs.tolist()

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

        lookahead_idx = min(15, len(predicted_path) - 1)
        target_pt = predicted_path[lookahead_idx]
        return (target_pt[0], target_pt[1])

    # ------------------------------------------------------------------
    #  TARGET INTERCEPTION (COLLISION COURSE) FINDER
    # ------------------------------------------------------------------
    def _find_interception_point(self, predicted_path, cam_x, cam_y, lookahead=15):
        """
        Points the camera to the adaptive-lookahead position for maximum corner-cutting.
        """
        if not predicted_path:
            return None

        lookahead_idx = min(lookahead, len(predicted_path) - 1)
        target_pt = predicted_path[lookahead_idx]
        return (target_pt[0], target_pt[1])

    # ------------------------------------------------------------------
    #  MAIN UPDATE LOOP
    # ------------------------------------------------------------------
    def update(
        self,
        frame,
        cam_x,
        cam_y,
        current_path="Random",
        obstacles=None,
        env_params=None,
    ):
        if obstacles is None:
            obstacles = []
        if env_params is None:
            env_params = {}

        # ---- Adaptive Kalman noise setup ----
        Q, R_base, R_disturbed = self._get_kalman_params(env_params, "TRACKING")
        self.kf.processNoiseCov = np.eye(6, dtype=np.float32) * Q

        prediction = self.kf.predict()
        pred_world_x = prediction[0, 0]
        pred_world_y = prediction[1, 0]

        # ----------------------------------------------------------
        #  ROBUST COMPUTER VISION PIPELINE (Environment-Adaptive)
        # ----------------------------------------------------------
        best_contour = None
        max_area = 0
        best_confidence = 0.0

        if self.video_mode:
            # ── Kalman-gated brightness search ─────────────────────────────────────
            # IMPORTANT: This entire block is video_mode only.
            # The simulation else-branch below is completely unaffected.
            #
            # Problem with old approach: raw global minMaxLoc grabbed whatever pixel
            # was brightest in the whole frame — when target hides behind an obstacle,
            # any other bright region would steal the lock and Kalman coasting never
            # activated.
            #
            # Fix: only search for bright pixels within a radius of where the Kalman
            # filter predicts the target should be. If nothing qualifies → confidence
            # stays 0.0 → the existing LOST / KALMAN COASTING path activates.

            if not hasattr(self, "target_brightness"):
                self.target_brightness = 100.0  # Absolute minimum baseline

            no_history = len(self.measurement_history) == 0

            if no_history:
                # ── First-ever acquisition ─────────────────────────────────────────
                blurred = cv2.GaussianBlur(frame, (25, 25), 0)
                _, max_val, _, max_loc = cv2.minMaxLoc(blurred)
                if max_val > 100:  # Absolute minimum
                    best_confidence = 0.95
                    tx, ty = max_loc
                    best_contour = np.array(
                        [[[tx, ty]], [[tx + 1, ty]], [[tx + 1, ty + 1]], [[tx, ty + 1]]],
                        dtype=np.int32,
                    )
                    self.target_brightness = max_val
            else:
                last_world_x, last_world_y = self.measurement_history[-1]
                
                if self.lost_frames == 0:
                    # ── Normal operation: Kalman-gated ROI search ──────────────────────
                    GATE_RADIUS = 60  # Tight gate to avoid background noise when tracking
                    
                    pred_vp_x = int(pred_world_x - cam_x)
                    pred_vp_y = int(pred_world_y - cam_y)
                    
                    rx1 = max(0, pred_vp_x - GATE_RADIUS)
                    ry1 = max(0, pred_vp_y - GATE_RADIUS)
                    rx2 = min(self.cam_width,  pred_vp_x + GATE_RADIUS)
                    ry2 = min(self.cam_height, pred_vp_y + GATE_RADIUS)

                    if rx2 > rx1 and ry2 > ry1:
                        blurred = cv2.GaussianBlur(frame, (25, 25), 0)
                        roi = blurred[ry1:ry2, rx1:rx2]
                        _, max_val, _, local_loc = cv2.minMaxLoc(roi)

                        # Must match expected beacon brightness (at least 70%)
                        if max_val > (self.target_brightness * 0.7) and max_val > 50:
                            best_confidence = 0.95
                            tx = rx1 + local_loc[0]
                            ty = ry1 + local_loc[1]
                            best_contour = np.array(
                                [[[tx, ty]], [[tx + 1, ty]], [[tx + 1, ty + 1]], [[tx, ty + 1]]],
                                dtype=np.int32,
                            )
                            # Update running average of beacon brightness
                            self.target_brightness = 0.8 * self.target_brightness + 0.2 * max_val
                else:
                    # ── Coasting: Full-viewport search with proximity guard ────────────
                    # During coasting, the Kalman prediction drifts. We search the whole 
                    # viewport but reject candidates too far from the last known position.
                    MAX_REACQ_DIST = 450  # world-px from last known
                    
                    blurred = cv2.GaussianBlur(frame, (25, 25), 0)
                    _, max_val, _, max_loc = cv2.minMaxLoc(blurred)
                    
                    # Stricter brightness check for re-acquisition to ignore background
                    if max_val > (self.target_brightness * 0.75) and max_val > 50:
                        tx, ty = max_loc
                        detected_world_x = cam_x + tx
                        detected_world_y = cam_y + ty
                        
                        dist_to_last = math.sqrt(
                            (detected_world_x - last_world_x) ** 2
                            + (detected_world_y - last_world_y) ** 2
                        )
                        
                        # Re-acquire only if it's within a reasonable distance of where we lost it
                        if dist_to_last <= MAX_REACQ_DIST:
                            best_confidence = 0.95
                            best_contour = np.array(
                                [[[tx, ty]], [[tx + 1, ty]], [[tx + 1, ty + 1]], [[tx, ty + 1]]],
                                dtype=np.int32,
                            )
                            self.target_brightness = 0.8 * self.target_brightness + 0.2 * max_val
        else:
            thresh, enhanced = self._adaptive_preprocess(frame, env_params)

            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            atmospheric = env_params.get("atmospheric", "Clear")
            if atmospheric == "Rain":
                area_min, area_max = 30, 600
            else:
                area_min, area_max = 15, 1000

            # In degraded atmospheres (Fog/Haze), the CNN was trained on clear images
            # and will score fog-blended crops near zero. Use the enhanced (background-
            # subtracted) image for CNN crops so the beacon is visible to the network.
            # If CNN still can't score anything above threshold, fall back to area heuristic.
            use_enhanced_crop = atmospheric in ("Fog", "Haze")

            for c in contours:
                area = cv2.contourArea(c)
                if area_min < area < area_max:
                    M = cv2.moments(c)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])

                        if self.cnn_model is not None:
                            x_min = max(0, cx - 16)
                            y_min = max(0, cy - 16)
                            x_max = min(self.cam_width, cx + 16)
                            y_max = min(self.cam_height, cy + 16)

                            # Crop from enhanced image in fog/haze so CNN sees the beacon
                            src = enhanced if use_enhanced_crop else frame
                            crop = src[y_min:y_max, x_min:x_max]
                            if crop.shape[0] > 0 and crop.shape[1] > 0:
                                if crop.shape != (32, 32):
                                    crop = cv2.resize(crop, (32, 32))
                                crop_norm = crop.astype(np.float32) / 255.0
                                crop_tensor = (
                                    torch.tensor(crop_norm).unsqueeze(0).unsqueeze(0)
                                )

                                with torch.no_grad():
                                    conf = self.cnn_model(crop_tensor).item()

                                if conf > best_confidence:
                                    best_confidence = conf
                                    best_contour = c

                        # Area fallback: if CNN is missing, or if CNN still gives nothing useful in fog,
                        # pick the largest valid blob (beacon is the only bright residual
                        # after background subtraction, so this is reliable).
                        if self.cnn_model is None or best_confidence < 0.1:
                            if use_enhanced_crop and best_confidence < 0.1:
                                if area > max_area:
                                    max_area = area
                                    best_contour = c
                                    # Assign synthetic confidence — lower than clear tracking
                                    # but above LOST threshold so Kalman stays engaged.
                                    best_confidence = 0.55
                            else:
                                if area > max_area:
                                    max_area = area
                                    best_contour = c
                                    best_confidence = 0.95 if 50 < max_area < 500 else 0.60

        error_x = 0
        error_y = 0
        log_msg = None
        confidence = best_confidence

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

                if status_str == "DISTURBED":
                    self.kf.measurementNoiseCov = (
                        np.eye(2, dtype=np.float32) * R_disturbed
                    )
                else:
                    self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * R_base

                self.kf.correct(measurement)

                raw_error_x = world_cx - (cam_x + self.cam_width // 2)
                raw_error_y = world_cy - (cam_y + self.cam_height // 2)
                error_x, error_y = self._compensate_platform_motion(
                    cam_x, cam_y, raw_error_x, raw_error_y, env_params
                )

                self.lost_frames = 0

                self.measurement_history.append((world_cx, world_cy))
                if len(self.measurement_history) > self.history_length:
                    self.measurement_history.pop(0)

                if self.was_lost:
                    log_msg = f"[KalmanTracker] Target RE-ACQUIRED from Coasting (Confidence: {confidence:.2f})"
                    self.was_lost = False
                    self.gru_sequence = []
                    self.gru_full_buffer = []
                    self.reacq_point = None
                    self.reacq_active = False
        else:
            self._prev_cam_x = float(cam_x)
            self._prev_cam_y = float(cam_y)

        # ----------------------------------------------------------
        #  COASTING WITH INTERCEPTION & RE-ACQUISITION
        # ----------------------------------------------------------
        if status_str == "LOST":
            self.lost_frames += 1
            self.was_lost = True

            path_key = current_path.lower().replace(" ", "").replace("of", "")
            path_map = {
                "random": "random",
                "circular": "circular",
                "spiral": "spiral",
                "figure8": "figureof8",
                "figureof8": "figureof8",
                "sinusoidal": "sinusoidal",
                "straightline": "straightline",
            }
            path_key = path_map.get(path_key, "")

            # Path-aware smoothing: sharp-turn paths need tighter window
            smooth_window = 3 if path_key in ("spiral", "figureof8") else 5

            # Adaptive lookahead
            lookahead = self._get_lookahead(env_params, path_key)

            # === FIRST FRAME OF LOSS ===
            if self.lost_frames == 1:
                self.current_path_key = path_key

                if path_key in self.gru_models and len(self.measurement_history) >= 2:
                    self.gru_sequence = self._generate_gru_prediction(
                        self.measurement_history, path_key, smooth_window
                    )
                    self.gru_full_buffer = (
                        list(self.measurement_history[-120:]) + self.gru_sequence.copy()
                    )

                    if obstacles and len(obstacles) > 0:
                        self.reacq_point = self._find_reacquisition_point(
                            self.gru_sequence, obstacles
                        )
                        self.reacq_active = True
                        log_msg = "[KalmanTracker] Target LOST behind cloud! Camera moving directly to exit point."
                    else:
                        self.reacq_active = False
                        log_msg = "[KalmanTracker] Target LOST (no cloud)! Initiating Target Interception (Collision Course)..."

                elif len(self.measurement_history) >= 2:
                    recent = (
                        self.measurement_history[-40:]
                        if len(self.measurement_history) >= 40
                        else self.measurement_history
                    )
                    p_old = recent[0]
                    p_new = recent[-1]
                    dt = len(recent) - 1
                    true_vx = (p_new[0] - p_old[0]) / float(dt)
                    true_vy = (p_new[1] - p_old[1]) / float(dt)

                    self.kf.statePre[2, 0] = true_vx
                    self.kf.statePre[3, 0] = true_vy
                    self.kf.statePost[2, 0] = true_vx
                    self.kf.statePost[3, 0] = true_vy

                    # Generate a pure li near physics prediction for the UI to draw
                    self.gru_sequence = []
                    curr_x = self.kf.statePost[0, 0]
                    curr_y = self.kf.statePost[1, 0]
                    for _ in range(50):
                        curr_x += true_vx
                        curr_y += true_vy
                        self.gru_sequence.append([curr_x, curr_y])

                    self.gru_full_buffer = (
                        list(self.measurement_history[-120:]) + self.gru_sequence.copy()
                    )
                    self.reacq_active = False

                    log_msg = f"[KalmanTracker] Target LOST! Linear Coasting at ({true_vx:.1f}, {true_vy:.1f}) px/frame"

            # === ROLLING PREDICTION ===
            if self.gru_sequence and len(self.gru_sequence) < 30:
                if self.current_path_key in self.gru_models:
                    sw = 3 if self.current_path_key in ("spiral", "figureof8") else 5
                    tail_history = self.gru_full_buffer[-120:]
                    new_prediction = self._generate_gru_prediction(
                        tail_history, self.current_path_key, sw
                    )
                    if new_prediction:
                        self.gru_sequence.extend(new_prediction)
                        self.gru_full_buffer.extend(new_prediction)
                else:
                    # Rolling Linear Replenishment
                    true_vx = self.kf.statePost[2, 0]
                    true_vy = self.kf.statePost[3, 0]
                    last_pt = self.gru_sequence[-1]
                    curr_x, curr_y = last_pt[0], last_pt[1]
                    new_prediction = []
                    for _ in range(20):
                        curr_x += true_vx
                        curr_y += true_vy
                        new_prediction.append([curr_x, curr_y])
                    self.gru_sequence.extend(new_prediction)
                    self.gru_full_buffer.extend(new_prediction)

                if len(self.gru_full_buffer) > 500:
                    self.gru_full_buffer = self.gru_full_buffer[-300:]

            # FORCE ZERO ACCELERATION
            self.kf.statePre[4, 0] = 0.0
            self.kf.statePre[5, 0] = 0.0
            self.kf.statePost[4, 0] = 0.0
            self.kf.statePost[5, 0] = 0.0

            # === DETERMINE WHERE TO POINT THE CAMERA ===
            if self.gru_sequence and len(self.gru_sequence) > 0:
                next_point = self.gru_sequence.pop(0)
                pred_world_x = next_point[0]
                pred_world_y = next_point[1]

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

                if self.reacq_active:
                    if obstacles and len(obstacles) > 0:
                        new_pt = self._find_reacquisition_point(
                            self.gru_sequence, obstacles
                        )
                        if new_pt:
                            self.reacq_point = new_pt

                    if self.reacq_point is not None:
                        raw_error_x = int(
                            self.reacq_point[0] - (cam_x + self.cam_width // 2)
                        )
                        raw_error_y = int(
                            self.reacq_point[1] - (cam_y + self.cam_height // 2)
                        )
                    else:
                        raw_error_x = int(pred_world_x - (cam_x + self.cam_width // 2))
                        raw_error_y = int(pred_world_y - (cam_y + self.cam_height // 2))
                else:
                    intercept_pt = self._find_interception_point(
                        self.gru_sequence, cam_x, cam_y, lookahead
                    )
                    if intercept_pt:
                        self.reacq_point = intercept_pt
                        raw_error_x = int(
                            intercept_pt[0] - (cam_x + self.cam_width // 2)
                        )
                        raw_error_y = int(
                            intercept_pt[1] - (cam_y + self.cam_height // 2)
                        )
                    else:
                        raw_error_x = int(pred_world_x - (cam_x + self.cam_width // 2))
                        raw_error_y = int(pred_world_y - (cam_y + self.cam_height // 2))

                error_x, error_y = self._compensate_platform_motion(
                    cam_x, cam_y, raw_error_x, raw_error_y, env_params
                )

            else:
                # Kalman linear coasting with boundary bounce
                margin = 100
                if self.kf.statePre[0, 0] < margin:
                    self.kf.statePre[0, 0] = 2 * margin - self.kf.statePre[0, 0]
                    self.kf.statePre[2, 0] *= -1
                elif self.kf.statePre[0, 0] > self.world_size - margin:
                    self.kf.statePre[0, 0] = (
                        2 * (self.world_size - margin) - self.kf.statePre[0, 0]
                    )
                    self.kf.statePre[2, 0] *= -1

                if self.kf.statePre[1, 0] < margin:
                    self.kf.statePre[1, 0] = 2 * margin - self.kf.statePre[1, 0]
                    self.kf.statePre[3, 0] *= -1
                elif self.kf.statePre[1, 0] > self.world_size - margin:
                    self.kf.statePre[1, 0] = (
                        2 * (self.world_size - margin) - self.kf.statePre[1, 0]
                    )
                    self.kf.statePre[3, 0] *= -1

                self.kf.statePost[0, 0] = self.kf.statePre[0, 0]
                self.kf.statePost[1, 0] = self.kf.statePre[1, 0]
                self.kf.statePost[2, 0] = self.kf.statePre[2, 0]
                self.kf.statePost[3, 0] = self.kf.statePre[3, 0]

                pred_world_x = self.kf.statePre[0, 0]
                pred_world_y = self.kf.statePre[1, 0]

                raw_error_x = int(pred_world_x - (cam_x + self.cam_width // 2))
                raw_error_y = int(pred_world_y - (cam_y + self.cam_height // 2))
                error_x, error_y = self._compensate_platform_motion(
                    cam_x, cam_y, raw_error_x, raw_error_y, env_params
                )

            status_str = "KALMAN COASTING"

        # Burn status overlay onto the frame for visual debugging
        self._draw_overlay(frame, status_str, env_params, confidence)

        rmse = math.sqrt(error_x**2 + error_y**2)
        return error_x, error_y, round(rmse, 2), status_str, log_msg
