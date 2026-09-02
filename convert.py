import imageio
import os

input_path = os.path.join(os.path.dirname(__file__), 'lesson2_disturbances.mp4')
output_path = os.path.join(os.path.dirname(__file__), 'lesson2_whatsapp.mp4')

print("Converting video to H.264 for WhatsApp compatibility...")
reader = imageio.get_reader(input_path)
fps = reader.get_meta_data()['fps']

# Use libx264 which is universally supported by WhatsApp/Apple/Web
writer = imageio.get_writer(output_path, fps=fps, codec='libx264', macro_block_size=None)
for frame in reader:
    writer.append_data(frame)
writer.close()
print(f"Conversion complete! File saved to: {output_path}")
