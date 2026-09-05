import torch
import numpy as np
import matplotlib.pyplot as plt
import math
from train_lstm import DirectTrajectoryPredictor
import os

def test_spiral_full():
    model_path = "lstm_spiral.pth"
    if not os.path.exists(model_path):
        print(f"Model {model_path} not found. Train first!")
        return
        
    model = DirectTrajectoryPredictor(history_length=120, future_length=120)
    model.load_state_dict(torch.load(model_path))
    model.eval()

    t_phase = 0.0
    TARGET_MAX_SPEED = 15.0
    WORLD_SIZE = 2000
    
    cx, cy = WORLD_SIZE // 2, WORLD_SIZE // 2
    spiral_r = 10.0
    spiral_dir = 1.0
    
    true_path = []
    for _ in range(800):
        if spiral_r < 10.0:
            spiral_r = 10.0
        omega = TARGET_MAX_SPEED / spiral_r
        t_phase += omega
        
        # Expansion: radius grows/shrinks by speed * 0.15 per frame
        expansion_speed = TARGET_MAX_SPEED * 0.15 * spiral_dir
        spiral_r += expansion_speed
        
        # Position-based (EXACTLY matching real sim)
        t_x = cx + math.cos(t_phase) * spiral_r
        t_y = cy + math.sin(t_phase) * spiral_r
        
        # Edge reversal (EXACTLY matching real sim)
        if t_x < 100 or t_x > WORLD_SIZE - 100 or t_y < 100 or t_y > WORLD_SIZE - 100:
            spiral_dir = -1.0  # spiral inward
        if spiral_r <= 20.0 and spiral_dir == -1.0:
            spiral_dir = 1.0   # spiral outward again
        
        true_path.append([t_x, t_y])
        
    true_path = np.array(true_path, dtype=np.float32)
    
    plt.figure(figsize=(12, 10))
    plt.plot(true_path[:, 0], true_path[:, 1], 'g-', linewidth=1.5, alpha=0.6, label='True Path')
    
    # Predict from 4 different points along the trajectory
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
    plt.title("Spiral — LSTM Prediction vs Actual")
    plt.xlabel("X (pixels)")
    plt.ylabel("Y (pixels)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("visualize_spiral.png", dpi=150)
    print("Saved visualize_spiral.png")

if __name__ == "__main__":
    test_spiral_full()
