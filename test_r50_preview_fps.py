#!/usr/bin/env python3
"""Test gphoto2 Liveview FPS mit persistenter Kameraverbindung."""

import gphoto2 as gp
import time, io
from PIL import Image

print("Verbinde mit Kamera ...")
camera = gp.Camera()
camera.init()
print("Verbunden.\n")

times = []
for i in range(10):
    t0 = time.time()
    preview = camera.capture_preview()
    file_data = preview.get_data_and_size()
    img = Image.open(io.BytesIO(bytes(file_data)))
    dt = time.time() - t0
    times.append(dt)
    print(f"Frame {i+1:2d}: {dt*1000:.0f}ms  {img.size}")

avg = sum(times) / len(times)
print(f"\n∅ {avg*1000:.0f}ms/Frame → {1/avg:.1f}fps")
camera.exit()
