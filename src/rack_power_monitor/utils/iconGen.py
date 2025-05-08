import os
from PIL import Image, ImageDraw

# Create directories if they don't exist
os.makedirs("resources/icons", exist_ok=True)

# Create a simple power icon
img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Draw a lightning bolt shape
points = [(32, 10), (20, 35), (30, 35), (20, 54), (44, 28), (34, 28), (44, 10)]
draw.polygon(points, fill=(0, 120, 212))  # Microsoft blue color

# Save as .ico
img.save('resources/icons/power_icon.ico')

print("Power icon created at resources/icons/power_icon.ico")