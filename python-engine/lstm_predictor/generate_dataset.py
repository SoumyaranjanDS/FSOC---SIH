import numpy as np
import os


def generate_spiral(length, noise_level):
    path = []
    r = 10.0
    phase = np.random.uniform(0, 2 * np.pi)
    cx, cy = np.random.uniform(500, 1500), np.random.uniform(500, 1500)
    for _ in range(length):
        r += 0.5
        phase += 0.1
        x = cx + r * np.cos(phase) + np.random.normal(0, noise_level)
        y = cy + r * np.sin(phase) + np.random.normal(0, noise_level)
        path.append([x, y])
    return np.array(path, dtype=np.float32)


def generate_circle(length, noise_level):
    path = []
    r = np.random.uniform(100, 400)
    phase = np.random.uniform(0, 2 * np.pi)
    cx, cy = np.random.uniform(500, 1500), np.random.uniform(500, 1500)
    for _ in range(length):
        phase += 0.05
        x = cx + r * np.cos(phase) + np.random.normal(0, noise_level)
        y = cy + r * np.sin(phase) + np.random.normal(0, noise_level)
        path.append([x, y])
    return np.array(path, dtype=np.float32)


def generate_figure8(length, noise_level):
    path = []
    r = np.random.uniform(200, 500)
    phase = np.random.uniform(0, 2 * np.pi)
    cx, cy = np.random.uniform(500, 1500), np.random.uniform(500, 1500)
    for _ in range(length):
        phase += 0.05
        x = cx + r * np.sin(phase) + np.random.normal(0, noise_level)
        y = cy + r * np.sin(phase) * np.cos(phase) + np.random.normal(0, noise_level)
        path.append([x, y])
    return np.array(path, dtype=np.float32)


def generate_sine(length, noise_level):
    path = []
    phase = np.random.uniform(0, 2 * np.pi)
    x = np.random.uniform(500, 1000)
    y = np.random.uniform(500, 1500)
    dx = np.random.uniform(5, 15)
    amp = np.random.uniform(50, 200)
    for _ in range(length):
        phase += 0.1
        x += dx
        current_y = y + amp * np.sin(phase) + np.random.normal(0, noise_level)
        path.append([x, current_y])
    return np.array(path, dtype=np.float32)


if __name__ == "__main__":
    print("Generating 10,000 synthetic paths for NLP-style LSTM training...")

    num_samples = 10000
    seq_length = 60  # 30 frames history + 30 frames future

    dataset = []

    for i in range(num_samples):
        # Pick a random path type
        path_type = np.random.choice(["spiral", "circle", "figure8", "sine"])
        noise = np.random.uniform(0.5, 2.0)

        if path_type == "spiral":
            path = generate_spiral(seq_length, noise)
        elif path_type == "circle":
            path = generate_circle(seq_length, noise)
        elif path_type == "figure8":
            path = generate_figure8(seq_length, noise)
        else:
            path = generate_sine(seq_length, noise)

        dataset.append(path)

        if (i + 1) % 2000 == 0:
            print(f"Generated {i+1} / {num_samples} paths...")

    dataset = np.array(dataset)  # Shape: (10000, 60, 2)

    # Save the dataset
    os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)
    save_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "trajectories.npy"
    )
    np.save(save_path, dataset)
    print(f"Dataset saved to {save_path}. Shape: {dataset.shape}")
