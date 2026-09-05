import torch
import numpy as np
import matplotlib.pyplot as plt
import math
from train_lstm import DirectTrajectoryPredictor
import os
import random

def test_circular_full():
    model_path = "lstm_circular.pth"
    if not os.path.exists(model_path):
        print(f"Model {model_path} not found. Train first!")
        return
        
    model = DirectTrajectoryPredictor(history_length=120, future_length=120)
    model.load_state_dict(torch.load(model_path))
    model.eval()

    t_phase = 0.0
    TARGET_MAX_SPEED = 15.0
    WORLD_SIZE = 2000
    
    circle_cx, circle_cy = 1000.0, 1000.0
    circle_R = 300.0
    target_circle_R = circle_R
    circle_hit_edge = False
    
    true_path = []
    for _ in range(800):
        if circle_R < target_circle_R:
            circle_R = min(circle_R + 1.0, target_circle_R)
        elif circle_R > target_circle_R:
            circle_R = max(circle_R - 1.0, target_circle_R)
            
        omega = TARGET_MAX_SPEED / max(circle_R, 10.0)
        
        old_phase = t_phase
        t_phase += omega
        
        if int(old_phase / (2*math.pi)) < int(t_phase / (2*math.pi)):
            if not circle_hit_edge:
                target_circle_R += 100.0
            else:
                target_circle_R = max(100.0, target_circle_R - 50.0)
            circle_hit_edge = False
        
        proposed_x = circle_cx + math.cos(t_phase) * circle_R
        proposed_y = circle_cy + math.sin(t_phase) * circle_R
        
        if proposed_x < 100:
            circle_cx += (100 - proposed_x)
            circle_hit_edge = True
        elif proposed_x > WORLD_SIZE - 100:
            circle_cx -= (proposed_x - (WORLD_SIZE - 100))
            circle_hit_edge = True
            
        if proposed_y < 100:
            circle_cy += (100 - proposed_y)
            circle_hit_edge = True
        elif proposed_y > WORLD_SIZE - 100:
            circle_cy -= (proposed_y - (WORLD_SIZE - 100))
            circle_hit_edge = True
            
        t_x = circle_cx + math.cos(t_phase) * circle_R
        t_y = circle_cy + math.sin(t_phase) * circle_R
        
        true_path.append([t_x, t_y])
        
    true_path = np.array(true_path, dtype=np.float32)
    
    plt.figure(figsize=(12, 10))
    plt.plot(true_path[:, 0], true_path[:, 1], 'g-', linewidth=1.5, alpha=0.6, label='True Path')
    
    colors = ['r', 'b', 'm', 'c']
    for i, start_idx in enumerate([0, 150, 300, 500]):
        history = true_path[start_idx : start_idx + 120]
        actual_future = true_path[start_idx + 120 : start_idx + 240]
        origin = history[-1].copy()
        
        history_rel = (history - origin) / 200.0
        history_tensor = torch.tensor(history_rel, dtype=torch.float32).unsqueeze(0)
        
        with torch.no_grad():
            pred_tensor = model(history_tensor)
            
        pred_rel = pred_tensor.squeeze(0).numpy()
        pred_abs = (pred_rel * 200.0) + origin
        
        plt.plot(history[:, 0], history[:, 1], colors[i]+'-', linewidth=3, alpha=0.4, label=f'History {i+1}')
        plt.plot(pred_abs[:, 0], pred_abs[:, 1], colors[i]+'--', linewidth=2, label=f'Prediction {i+1}')
        if len(actual_future) > 0:
            plt.plot(actual_future[:, 0], actual_future[:, 1], colors[i]+':', linewidth=1, alpha=0.3, label=f'Actual Future {i+1}')
        plt.scatter(origin[0], origin[1], c='k', s=80, marker='x', zorder=5)

    plt.legend(loc='upper right', fontsize=8)
    plt.title("Circular — LSTM Prediction vs Actual")
    plt.xlabel("X (pixels)")
    plt.ylabel("Y (pixels)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("visualize_circular.png", dpi=150)
    print("Saved visualize_circular.png")

if __name__ == "__main__":
    test_circular_full()
