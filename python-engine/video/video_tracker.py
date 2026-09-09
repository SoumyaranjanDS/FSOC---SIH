import cv2
import numpy as np


class VideoTracker:
    def __init__(self, init_cam_x, init_cam_y, cam_w, cam_h, world_size):
        self.cam_w = cam_w
        self.cam_h = cam_h

        # Temporal smoothing to prevent jumping to spurious bright spots
        self.last_target = None
        self.lost_frames = 0

    def update(
        self, viewport_gray, cam_x, cam_y, target_path_mode, obstacles, env_params
    ):
        """
        viewport_gray: 640x480 crop of the video frame
        Returns: error_x, error_y, rmse, status_str, log_msg
        """
        # Apply substantial Gaussian Blur to ignore small noise dots and consolidate the beacon
        blurred = cv2.GaussianBlur(viewport_gray, (25, 25), 0)

        # Find the absolute brightest spot
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(blurred)

        log_msg = None
        status = "WAITING"

        # Assume the beacon is a highly bright source (intensity > 200)
        # If max_val drops below this, it means it went behind heavy fog/clouds
        if max_val > 150:
            target_x, target_y = max_loc

            if self.last_target is not None:
                dist = np.hypot(
                    target_x - self.last_target[0], target_y - self.last_target[1]
                )
                # If the brightest point jumps wildly within 1 frame (e.g. >150px jump),
                # it might be a spurious reflection or a new bright object entering frame.
                # Coast for a few frames before trusting it.
                if dist > 200 and self.lost_frames < 10:
                    target_x, target_y = self.last_target
                    self.lost_frames += 1
                    status = "KALMAN COASTING"  # Keep terminology consistent with UI
                else:
                    self.last_target = (target_x, target_y)
                    self.lost_frames = 0
                    status = "TRACKING"
            else:
                self.last_target = (target_x, target_y)
                self.lost_frames = 0
                status = "TRACKING"

            error_x = target_x - (self.cam_w // 2)
            error_y = target_y - (self.cam_h // 2)
            rmse = np.hypot(error_x, error_y)

            return error_x, error_y, rmse, status, log_msg

        else:
            self.lost_frames += 1
            if self.last_target is not None:
                # If lost, report error based on last known position
                error_x = self.last_target[0] - (self.cam_w // 2)
                error_y = self.last_target[1] - (self.cam_h // 2)
                rmse = np.hypot(error_x, error_y)
            else:
                error_x, error_y, rmse = 0.0, 0.0, 0.0

            status = "PREDICTING"
            log_msg = f"Beacon lost in haze/clouds (max val: {int(max_val)})"
            return error_x, error_y, rmse, status, log_msg
