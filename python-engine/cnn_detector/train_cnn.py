import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import cv2
import os
import random
from cnn_model import BeaconCNN

def generate_synthetic_data(num_samples=5000):
    # Generates 32x32 patches. 
    # Half are positives (beacon), half are negatives (noise/background)
    X = []
    y = []
    
    for _ in range(num_samples):
        # 1. Base Background (Dark)
        img = np.ones((32, 32), dtype=np.uint8) * random.randint(0, 50)
        
        is_positive = random.choice([True, False])
        
        if is_positive:
            # Draw a beacon (bright circle)
            radius = random.randint(2, 6)
            cx = random.randint(radius + 2, 32 - radius - 2)
            cy = random.randint(radius + 2, 32 - radius - 2)
            intensity = random.randint(150, 255)
            cv2.circle(img, (cx, cy), radius, intensity, -1)
            
            # Motion Blur (Camera Jitter)
            if random.random() > 0.5:
                kernel_size = random.choice([3, 5])
                kernel = np.zeros((kernel_size, kernel_size))
                # Horizontal or vertical blur
                if random.random() > 0.5:
                    kernel[int((kernel_size-1)/2), :] = np.ones(kernel_size)
                else:
                    kernel[:, int((kernel_size-1)/2)] = np.ones(kernel_size)
                kernel /= kernel_size
                img = cv2.filter2D(img, -1, kernel)
                
            # Add a slight blur to simulate optical bloom
            img = cv2.GaussianBlur(img, (3, 3), 0)
            y.append(1.0)
        else:
            # Negative examples
            neg_type = random.randint(0, 3)
            if neg_type == 0:
                # Just noise
                pass
            elif neg_type == 1:
                # A line / streak (like rain)
                cv2.line(img, (random.randint(0,32), random.randint(0,32)), 
                              (random.randint(0,32), random.randint(0,32)), 
                              random.randint(100, 255), 1)
            elif neg_type == 2:
                # Sun glare / huge blob (too large to be the beacon)
                cv2.circle(img, (16, 16), random.randint(15, 25), random.randint(100, 200), -1)
                img = cv2.GaussianBlur(img, (7, 7), 0)
            elif neg_type == 3:
                # Haze/Fog (wash out the whole background with high intensity but no structure)
                img = np.ones((32, 32), dtype=np.uint8) * random.randint(150, 230)
            y.append(0.0)
            
        # Add random noise to all images
        noise = np.random.normal(0, random.randint(5, 25), (32, 32))
        img = np.clip(img + noise, 0, 255).astype(np.uint8)
        
        # Normalize to 0-1
        img_norm = img.astype(np.float32) / 255.0
        X.append(img_norm)
        
    # Reshape for PyTorch: (batch_size, channels, H, W)
    X = np.array(X).reshape(-1, 1, 32, 32)
    y = np.array(y).reshape(-1, 1)
    
    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("Generating Synthetic Dataset...")
    X_train, y_train = generate_synthetic_data(10000)
    
    dataset = torch.utils.data.TensorDataset(X_train, y_train)
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=64, shuffle=True)
    
    model = BeaconCNN()
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    epochs = 15
    print("Training CNN Detector...")
    for epoch in range(epochs):
        epoch_loss = 0.0
        correct = 0
        total = 0
        for batch_X, batch_Y in dataloader:
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_Y)
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item()
            
            predicted = (outputs > 0.5).float()
            total += batch_Y.size(0)
            correct += (predicted == batch_Y).sum().item()
            
        acc = 100 * correct / total
        print(f"Epoch {epoch+1}/{epochs} | Loss: {epoch_loss/len(dataloader):.4f} | Accuracy: {acc:.2f}%")
        
    save_path = os.path.join(script_dir, "cnn_beacon.pth")
    torch.save(model.state_dict(), save_path)
    print(f"CNN Model saved to {save_path}")
