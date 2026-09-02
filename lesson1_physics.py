import numpy as np
import matplotlib.pyplot as plt
import os

print("Generating Physics Simulation...")

# 1. TIME (The Engine)
# Let's simulate 10 seconds of flight at 30 frames per second (300 data points total)
# np.linspace gives us an array of evenly spaced numbers from 0 to 10
time_sec = np.linspace(0, 10, 300)

# 2. THE IDEAL PATH (The Math)
# A simple circle is boring. Let's make the drone fly in a Figure-8 (Lissajous curve).
# X oscillates slowly, Y oscillates twice as fast to create the 8-shape.
x_ideal = 500 + 300 * np.sin(time_sec)
y_ideal = 500 + 300 * np.sin(2 * time_sec)

# 3. DISTURBANCE (The Real World is Messy)
# A real drone vibrates due to wind and motors.
# We use NumPy to generate "Gaussian Noise" (random shaking).
# np.random.normal(mean=0, standard_deviation=15 pixels, size=300)
wind_x = np.random.normal(0, 15, len(time_sec))
wind_y = np.random.normal(0, 15, len(time_sec))

# 4. THE ACTUAL PATH
# We simply add the random wind to our perfect mathematical path
x_actual = x_ideal + wind_x
y_actual = y_ideal + wind_y

# 5. VISUALIZE IT (Using Matplotlib)
plt.figure(figsize=(8, 8))

# Plot the smooth ideal path as a blue dashed line
plt.plot(
    x_ideal,
    y_ideal,
    label="Ideal Drone Path",
    color="blue",
    linewidth=2,
    linestyle="--",
)

# Plot the messy, actual path as red dots
plt.scatter(
    x_actual,
    y_actual,
    label="Actual Beacon Position (with wind)",
    color="red",
    s=15,
    alpha=0.7,
)

plt.title("FSOC Target Trajectory Simulation")
plt.xlabel("X Coordinate (Pixels)")
plt.ylabel("Y Coordinate (Pixels)")
plt.legend()
plt.grid(True)

# Save the plot
output_path = os.path.join(os.path.dirname(__file__), "trajectory.png")
plt.savefig(output_path)
print(f"Done! Plot saved to {output_path}")
