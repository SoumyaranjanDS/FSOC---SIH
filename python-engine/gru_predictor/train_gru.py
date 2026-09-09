import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import os


class GRUPredictor(nn.Module):
    def __init__(self, history_length=120, future_length=15):
        super(GRUPredictor, self).__init__()
        self.history_length = history_length
        self.future_length = future_length

        # Using GRU instead of LSTM
        self.gru = nn.GRU(input_size=2, hidden_size=128, num_layers=2, batch_first=True)
        self.fc1 = nn.Linear(128, 256)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(256, future_length * 2)  # Output 15 frames of (x,y)

    def forward(self, x):
        # GRU returns output, h_n
        out, hn = self.gru(x)
        # Take the hidden state of the last layer
        last_hidden = hn[-1, :, :]

        x = self.relu(self.fc1(last_hidden))
        x = self.fc2(x)

        # Reshape to (batch_size, future_len, 2)
        return x.view(-1, self.future_length, 2)


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # We will reuse the datasets generated for the LSTM
    dataset_dir = os.path.join(os.path.dirname(script_dir), "lstm_predictor")
    paths_to_train = ["random", "straightline", "circular", "spiral", "figureof8", "sinusoidal"]

    for path in paths_to_train:
        print(f"\n======================================")
        print(f"Training GRU Model for: {path}")
        print(f"======================================")

        data_path = os.path.join(dataset_dir, f"trajectories_{path}.npy")
        if not os.path.exists(data_path):
            print(f"Dataset {data_path} not found. Skipping...")
            continue

        data = np.load(data_path)
        # The data was generated with seq_length=240
        X = data[:, :120, :]
        # We only want to predict 15 frames into the future for our short-horizon occlusion strategy
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
        criterion = nn.MSELoss()
        optimizer = optim.Adam(model.parameters(), lr=0.001)
        scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)

        epochs = 20
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

        model_save_path = os.path.join(script_dir, f"gru_{path.lower()}.pth")
        torch.save(model.state_dict(), model_save_path)
        print(f"Model saved to {model_save_path}")
