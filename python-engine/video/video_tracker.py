import cv2
import numpy as np


class VideoTracker:
    def __init__(self, init_cam_x, init_cam_y, cam_w, cam_h, world_size):
        self.cam_w = cam_w
        self.cam_h = cam_h
        self.world_size = world_size

        # Temporal smoothing to prevent jumping to spurious bright spots
        self.last_target = None
        self.lost_frames = 0
        self.gru_sequence = []

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
        self.kf.processNoiseCov = np.eye(6, dtype=np.float32) * 0.05
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 2.0

        initial_state = np.array(
            [[init_cam_x + cam_w//2], [init_cam_y + cam_h//2], [0], [0], [0], [0]], np.float32
        )
        self.kf.statePre = initial_state.copy()
        self.kf.statePost = initial_state.copy()

    def update(
        self, viewport_gray, cam_x, cam_y, target_path_mode, obstacles, env_params
    ):
        """
        viewport_gray: 640x480 crop of the video frame
        Returns: error_x, error_y, rmse, status_str, log_msg
        """
        prediction = self.kf.predict()
        pred_world_x = prediction[0, 0]
        pred_world_y = prediction[1, 0]

        # Apply substantial Gaussian Blur to ignore small noise dots and consolidate the beacon
        blurred = cv2.GaussianBlur(viewport_gray, (25, 25), 0)

        # Find the absolute brightest spot
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(blurred)

        log_msg = None
        status = "WAITING"

        # Assume the beacon is a highly bright source (intensity > 150)
        # If max_val drops below this, it means it went behind heavy fog/clouds
        if max_val > 150:
            target_x, target_y = max_loc
            world_target_x = cam_x + target_x
            world_target_y = cam_y + target_y

            if self.last_target is not None:
                dist = np.hypot(
                    target_x - self.last_target[0], target_y - self.last_target[1]
                )
                # If the brightest point jumps wildly within 1 frame (e.g. >150px jump),
                # it might be a spurious reflection. Coast for a few frames before trusting it.
                if dist > 200 and self.lost_frames < 10:
                    self.lost_frames += 1
                    status = "KALMAN COASTING"
                else:
                    self.last_target = (target_x, target_y)
                    self.lost_frames = 0
                    status = "TRACKING"
                    measurement = np.array([[np.float32(world_target_x)], [np.float32(world_target_y)]])
                    self.kf.correct(measurement)
            else:
                self.last_target = (target_x, target_y)
                self.lost_frames = 0
                status = "TRACKING"
                measurement = np.array([[np.float32(world_target_x)], [np.float32(world_target_y)]])
                self.kf.correct(measurement)
                
        else:
            self.lost_frames += 1
            status = "KALMAN COASTING"
            log_msg = f"Beacon lost in haze/clouds (max val: {int(max_val)})"

        if status == "KALMAN COASTING":
            # Generate linear projection sequence for UI drawing
            self.gru_sequence = []
            true_vx = self.kf.statePost[2, 0]
            true_vy = self.kf.statePost[3, 0]
            
            # Dampen acceleration during coasting
            self.kf.statePre[4, 0] = 0.0
            self.kf.statePre[5, 0] = 0.0
            self.kf.statePost[4, 0] = 0.0
            self.kf.statePost[5, 0] = 0.0
            
            curr_x = self.kf.statePre[0, 0]
            curr_y = self.kf.statePre[1, 0]
            
            for _ in range(50):
                curr_x += true_vx
                curr_y += true_vy
                self.gru_sequence.append([curr_x, curr_y])

            # Follow the immediate Kalman prediction
            error_x = pred_world_x - (cam_x + self.cam_w // 2)
            error_y = pred_world_y - (cam_y + self.cam_h // 2)
            rmse = np.hypot(error_x, error_y)
        else:
            self.gru_sequence = []
            error_x = target_x - (self.cam_w // 2)
            error_y = target_y - (self.cam_h // 2)
            rmse = np.hypot(error_x, error_y)

        return int(error_x), int(error_y), float(rmse), status, log_msg
