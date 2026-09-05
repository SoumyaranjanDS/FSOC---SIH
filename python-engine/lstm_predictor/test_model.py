import torch
import numpy as np
from train_lstm import DirectTrajectoryPredictor
import matplotlib.pyplot as plt

model = DirectTrajectoryPredictor()
model.load_state_dict(torch.load('trajectory_lstm.pth'))
model.eval()

data = np.load('trajectories.npy')
sample = data[0] # first sequence
history = sample[:30]
future = sample[30:]

origin = history[-1].copy()
history_rel = (history - origin) / 200.0
x_t = torch.tensor(history_rel, dtype=torch.float32).unsqueeze(0)
y_pred = model(x_t).squeeze(0).detach().numpy()
y_pred = (y_pred * 200.0) + origin

print("Actual future 0-3:")
print(future[:3])
print("Predicted future 0-3:")
print(y_pred[:3])

error = np.mean(np.sqrt(np.sum((future - y_pred)**2, axis=1)))
print(f"Average Pixel Error across 30 frames: {error:.2f}")
