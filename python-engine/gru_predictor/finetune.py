import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from train_gru import GRUPredictor

script_dir = os.path.dirname(os.path.abspath(__file__))
dataset_dir = os.path.join(os.path.dirname(script_dir), "lstm_predictor")

paths_to_finetune = ["figureof8", "spiral"]

for path in paths_to_finetune:
    print(f"\n======================================")
    print(f"Fine-Tuning GRU Model for: {path}")
    print(f"======================================")

    data_path = os.path.join(dataset_dir, f"trajectories_{path}.npy")
    if not os.path.exists(data_path):
        print(f"Dataset {data_path} not found. Skipping...")
        continue

    data = np.load(data_path)
    X = data[:, :120, :]
    Y = data[:, 120:135, :]

    X_rel = np.zeros_like(X)
    Y_rel = np.zeros_like(Y)

    for i in range(len(X)):
        origin = X[i, -1, :].copy()
        X_rel[i] = X[i] - origin
        Y_rel[i] = Y[i] - origin

    scale_factor = 200.0
    X_norm = X_rel / scale_factor
    Y_norm = Y_rel / scale_factor

    X_tensor = torch.tensor(X_norm, dtype=torch.float32)
    Y_tensor = torch.tensor(Y_norm, dtype=torch.float32)

    dataset = torch.utils.data.TensorDataset(X_tensor, Y_tensor)
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=64, shuffle=True)

    model = GRUPredictor()
    model_save_path = os.path.join(script_dir, f"gru_{path}.pth")
    if os.path.exists(model_save_path):
        model.load_state_dict(torch.load(model_save_path))
        print(f"Loaded existing weights for {path}!")

    criterion = nn.MSELoss()
    # Fine-tuning learning rate (smaller)
    optimizer = optim.Adam(model.parameters(), lr=0.0003)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)

    epochs = 40  # 40 extra epochs
    for epoch in range(epochs):
        epoch_loss = 0.0
        for batch_X, batch_Y in dataloader:
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_Y)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()

        scheduler.step()
        avg_loss = epoch_loss / len(dataloader)
        print(
            f"Epoch {epoch+1}/{epochs} | Loss: {avg_loss:.5f} | LR: {scheduler.get_last_lr()[0]:.6f}"
        )

    torch.save(model.state_dict(), model_save_path)
    print(f"Fine-tuned model saved to {model_save_path}")
