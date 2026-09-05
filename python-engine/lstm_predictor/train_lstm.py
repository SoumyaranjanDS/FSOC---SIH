import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import os

class TrajectoryPredictor(nn.Module):
    def __init__(self, input_size=2, hidden_size=64, num_layers=2, output_size=2):
        super(TrajectoryPredictor, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        # x shape: (batch_size, seq_len, input_size)
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        
        # out shape: (batch_size, seq_len, hidden_size)
        out, _ = self.lstm(x, (h0, c0))
        
        # We want to predict the next 30 frames. 
        # But this is a Seq2Seq problem. We'll take the output of the LSTM 
        # and pass it through the FC layer to get predictions for all time steps.
        # Actually, for predicting a future sequence from a past sequence, 
        # an encoder-decoder is best. But for simplicity and speed, we can use 
        # a direct mapping if we just want to output the next 30 frames from the last hidden state.
        
        # Let's use the last hidden state to predict 30 future steps (60 floats)
        pass

# Since predicting 30 future frames directly from the last hidden state requires reshaping,
# let's write a simpler direct FC approach attached to the LSTM
class DirectTrajectoryPredictor(nn.Module):
    def __init__(self, history_length=120, future_length=120):
        super(DirectTrajectoryPredictor, self).__init__()
        self.history_length = history_length
        self.future_length = future_length
        self.lstm = nn.LSTM(input_size=2, hidden_size=128, num_layers=2, batch_first=True)
        # The LSTM outputs a hidden state of size 128 for the final time step
        self.fc1 = nn.Linear(128, 256)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(256, future_length * 2) # Output 120 frames of (x,y)

    def forward(self, x):
        out, (hn, cn) = self.lstm(x)
        # Take the hidden state of the last layer
        last_hidden = hn[-1, :, :]
        
        x = self.relu(self.fc1(last_hidden))
        x = self.fc2(x)
        
        # Reshape to (batch_size, future_len, 2)
        return x.view(-1, self.future_length, 2)


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    paths_to_train = ["straightline"]
    
    for path in paths_to_train:
        print(f"\n======================================")
        print(f"Training Model for: {path}")
        print(f"======================================")
        
        data_path = os.path.join(script_dir, f"trajectories_{path}.npy")
        if not os.path.exists(data_path):
            print(f"Dataset {data_path} not found. Skipping...")
            continue
            
        data = np.load(data_path)
        # The data was generated with seq_length=240
        X = data[:, :120, :]
        Y = data[:, 120:, :]
        
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
        
        model = DirectTrajectoryPredictor()
        criterion = nn.MSELoss()
        optimizer = optim.Adam(model.parameters(), lr=0.001)
        scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)
        
        epochs = 30
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
            print(f"Epoch {epoch+1}/{epochs} | Loss: {avg_loss:.5f} | LR: {scheduler.get_last_lr()[0]:.6f}")
            
        model_save_path = os.path.join(script_dir, f"lstm_{path.lower()}.pth")
        torch.save(model.state_dict(), model_save_path)
        print(f"Model saved to {model_save_path}")
