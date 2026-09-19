from scipy.optimize import linear_sum_assignment
import math
import numpy as np
import torch
import cv2
from kalman_tracker import SingleTrack

class KalmanTracker:
    def __init__(self, initial_world_x, initial_world_y, cam_width=640, cam_height=480, world_size=2000, video_mode=False):
        self.cam_width = cam_width
        self.cam_height = cam_height
        self.world_size = world_size
        self.video_mode = video_mode
        self.tracks = [SingleTrack(initial_world_x, initial_world_y, cam_width, cam_height, world_size, video_mode)]
        
    def update(self, frame, cam_x, cam_y, current_path="random", env_params=None):
        if env_params is None:
            env_params = {}
            
        t0 = self.tracks[0]
        
        # 1. Preprocess and Detect all possible beacons
        thresh, enhanced = t0._adaptive_preprocess(frame, env_params)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        atmospheric = env_params.get("atmospheric", "Clear")
        if atmospheric == "Rain":
            area_min, area_max = 30, 600
        else:
            area_min, area_max = 15, 1000
            
        use_enhanced_crop = atmospheric in ("Fog", "Haze")
        
        detections = []
        for c in contours:
            area = cv2.contourArea(c)
            if area_min < area < area_max:
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    conf = 0.0
                    if t0.cnn_model is not None:
                        x_min = max(0, cx - 16)
                        y_min = max(0, cy - 16)
                        x_max = min(self.cam_width, cx + 16)
                        y_max = min(self.cam_height, cy + 16)
                        src = enhanced if use_enhanced_crop else frame
                        crop = src[y_min:y_max, x_min:x_max]
                        if crop.shape[0] > 0 and crop.shape[1] > 0:
                            if crop.shape != (32, 32):
                                crop = cv2.resize(crop, (32, 32))
                            crop_norm = crop.astype(np.float32) / 255.0
                            crop_tensor = torch.tensor(crop_norm).unsqueeze(0).unsqueeze(0)
                            with torch.no_grad():
                                conf = t0.cnn_model(crop_tensor).item()
                    
                    if t0.cnn_model is None or conf < 0.1:
                        if use_enhanced_crop and conf < 0.1:
                            conf = 0.55
                        else:
                            conf = 0.95 if 50 < area < 500 else 0.60
                            
                    world_cx = cam_x + cx
                    world_cy = cam_y + cy
                    detections.append({'cx': cx, 'cy': cy, 'world_cx': world_cx, 'world_cy': world_cy, 'conf': conf, 'contour': c})

        # 2. Hungarian Matching
        cost_matrix = []
        for track in self.tracks:
            track_pred_x = track.kf.statePre[0, 0]
            track_pred_y = track.kf.statePre[1, 0]
            row = []
            for det in detections:
                dist = math.hypot(track_pred_x - det['world_cx'], track_pred_y - det['world_cy'])
                row.append(dist)
            cost_matrix.append(row)
            
        track_assignments = {i: None for i in range(len(self.tracks))}
        if cost_matrix and cost_matrix[0]:
            cost_matrix_np = np.array(cost_matrix)
            row_inds, col_inds = linear_sum_assignment(cost_matrix_np)
            for r, c in zip(row_inds, col_inds):
                if cost_matrix_np[r, c] < 500:  # Distance threshold
                    track_assignments[r] = detections[c]
                    
        # 3. Update all tracks
        for i, track in enumerate(self.tracks):
            det = track_assignments[i]
            matched = None
            if det is not None:
                matched = (det['cx'], det['cy'], det['conf'], det['contour'])
            
            # Use a dummy variable since single track returns multiple
            t_ex, t_ey, t_rmse, t_status, t_log = track.update(frame, cam_x, cam_y, current_path, env_params=env_params, matched_detection=matched)
            track._last_error_x = t_ex
            track._last_error_y = t_ey
            track.last_rmse = t_rmse
            track.status_str = t_status
            track.last_log = t_log
            
        # 4. Determine primary output for PTZ camera
        if len(self.tracks) == 1:
            t = self.tracks[0]
            return getattr(t, '_last_error_x', 0), getattr(t, '_last_error_y', 0), getattr(t, 'last_rmse', 0.0), getattr(t, 'status_str', 'TRACKING'), getattr(t, 'last_log', None)
        else:
            active_tracks = [t for t in self.tracks if getattr(t, 'status_str', 'TRACKING') in ["TRACKING", "DISTURBED"]]
            if len(active_tracks) == 2:
                t1, t2 = active_tracks[0], active_tracks[1]
                dist = math.hypot(t1.kf.statePost[0, 0] - t2.kf.statePost[0, 0],
                                  t1.kf.statePost[1, 0] - t2.kf.statePost[1, 0])
                if dist > 500:
                    # Target separated wider than FOV, prioritize highest confidence
                    best = max(active_tracks, key=lambda t: getattr(t, 'confidence', 0.0))
                    return getattr(best, '_last_error_x', 0), getattr(best, '_last_error_y', 0), getattr(best, 'last_rmse', 0.0), getattr(best, 'status_str', 'TRACKING'), getattr(best, 'last_log', None)
                else:
                    # Track midpoint
                    mid_x = (t1.kf.statePost[0, 0] + t2.kf.statePost[0, 0]) / 2.0
                    mid_y = (t1.kf.statePost[1, 0] + t2.kf.statePost[1, 0]) / 2.0
                    e_x = mid_x - (cam_x + self.cam_width // 2)
                    e_y = mid_y - (cam_y + self.cam_height // 2)
                    avg_conf = (getattr(t1, 'confidence', 0.0) + getattr(t2, 'confidence', 0.0)) / 2.0
                    return int(e_x), int(e_y), avg_conf, "TRACKING (DUAL)", None
            elif len(active_tracks) == 1:
                t = active_tracks[0]
                return getattr(t, '_last_error_x', 0), getattr(t, '_last_error_y', 0), getattr(t, 'last_rmse', 0.0), getattr(t, 'status_str', 'TRACKING'), getattr(t, 'last_log', None)
            else:
                # Both lost, follow the first one
                t = self.tracks[0]
                return getattr(t, '_last_error_x', 0), getattr(t, '_last_error_y', 0), getattr(t, 'last_rmse', 0.0), "LOST (DUAL)", None
                
    def add_track(self, x, y):
        self.tracks.append(SingleTrack(x, y, self.cam_width, self.cam_height, self.world_size, self.video_mode))

    def remove_track(self):
        if len(self.tracks) > 1:
            self.tracks.pop()
