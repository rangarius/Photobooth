#!/usr/bin/env python3
"""
Framebuffer-based display manager.
Writes directly to /dev/fb0 — no X11 or pygame required.
Supports 16-bit RGB565 and 32-bit RGBA framebuffers.
"""

import os
import logging
import threading
import time
import numpy as np
from PIL import Image


class DisplayManager:

    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._fb_path = '/dev/fb0'
        self._bits = self._read_bits_per_pixel()
        self._fb_w, self._fb_h = self._read_fb_size()

        self._preview_frame = None   # PIL.Image, updated by preview thread
        self._overlays = {}          # id -> (layer, PIL.Image)
        self._next_id = 0
        self._lock = threading.Lock()
        self._running = True

        # hide terminal cursor and clear console over framebuffer
        self._hide_cursor()
        # blank screen on start
        self._write_black()

        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()
        logging.debug(f"DisplayManager: fb0 {self._fb_w}x{self._fb_h} {self._bits}bpp")

    # ── Public API ────────────────────────────────────────────────────────────

    def update_preview(self, pil_image):
        """Called from camera preview thread. Thread-safe."""
        img = pil_image.convert('RGB').resize((self.screen_w, self.screen_h), Image.LANCZOS)
        with self._lock:
            self._preview_frame = img

    def show_message(self, text, color=(255, 255, 255)):
        """Render centered text on black and register as overlay. Returns overlay_id."""
        from PIL import ImageDraw, ImageFont
        img = Image.new('RGBA', (self.screen_w, self.screen_h), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
        ]
        font = ImageFont.load_default()
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, 42)
                except Exception:
                    pass
                break
        bbox = draw.multiline_textbbox((0, 0), text, font=font, align='center')
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (self.screen_w - tw) // 2
        y = (self.screen_h - th) // 2
        draw.multiline_text((x, y), text, font=font, fill=color, align='center')
        with self._lock:
            oid = self._next_id
            self._next_id += 1
            self._overlays[oid] = (10, img)
        return oid

    def add_overlay(self, image_path, layer=3):
        """Load a PNG and register as overlay. Returns overlay_id or -1."""
        if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
            logging.warning(f"Overlay missing or empty: {image_path}")
            return -1
        try:
            img = Image.open(image_path).convert('RGBA')
            img = img.resize((self.screen_w, self.screen_h), Image.LANCZOS)
            with self._lock:
                oid = self._next_id
                self._next_id += 1
                self._overlays[oid] = (layer, img)
            return oid
        except Exception as e:
            logging.error(f"add_overlay error ({image_path}): {e}")
            return -1

    def remove_overlay(self, overlay_id):
        if overlay_id == -1:
            return
        with self._lock:
            self._overlays.pop(overlay_id, None)

    def quit(self):
        self._running = False
        self._write_black()

    # ── Render loop ───────────────────────────────────────────────────────────

    def _render_loop(self):
        interval = 1 / 30
        while self._running:
            t0 = time.time()
            try:
                self._render_frame()
            except Exception as e:
                logging.warning(f"Render error: {e}")
            elapsed = time.time() - t0
            sleep = interval - elapsed
            if sleep > 0:
                time.sleep(sleep)

    def _render_frame(self):
        with self._lock:
            preview = self._preview_frame
            overlays = sorted(self._overlays.values(), key=lambda x: x[0])

        # composite: black → preview → overlays (by layer)
        canvas = Image.new('RGB', (self.screen_w, self.screen_h), (0, 0, 0))
        if preview:
            canvas.paste(preview)
        for _, overlay_img in overlays:
            canvas.paste(overlay_img, (0, 0), overlay_img)  # uses RGBA mask

        if self.screen_w != self._fb_w or self.screen_h != self._fb_h:
            canvas = canvas.resize((self._fb_w, self._fb_h), Image.LANCZOS)

        self._write_to_fb(canvas)

    # ── Framebuffer I/O ───────────────────────────────────────────────────────

    def _write_to_fb(self, img):
        data = self._encode(img)
        try:
            with open(self._fb_path, 'wb') as fb:
                fb.write(data)
        except PermissionError:
            logging.error("Cannot write to /dev/fb0 — add user to 'video' group")
            self._running = False

    def _encode(self, img):
        if self._bits == 16:
            arr = np.array(img.convert('RGB'), dtype=np.uint16)
            r = (arr[:, :, 0] >> 3).astype(np.uint16)
            g = (arr[:, :, 1] >> 2).astype(np.uint16)
            b = (arr[:, :, 2] >> 3).astype(np.uint16)
            rgb565 = (r << 11) | (g << 5) | b
            return rgb565.astype('<u2').tobytes()
        else:
            return img.convert('RGBA').tobytes()

    def _write_black(self):
        try:
            black = Image.new('RGB', (self._fb_w, self._fb_h), (0, 0, 0))
            with open(self._fb_path, 'wb') as fb:
                fb.write(self._encode(black))
        except Exception:
            pass

    # ── sysfs helpers ─────────────────────────────────────────────────────────

    def _hide_cursor(self):
        for tty in ('/dev/tty1', '/dev/tty'):
            try:
                with open(tty, 'wb') as t:
                    t.write(b'\033[?25l')  # hide cursor
                    t.write(b'\033[2J')    # clear screen
                return
            except Exception:
                continue

    def _read_bits_per_pixel(self):
        try:
            with open('/sys/class/graphics/fb0/bits_per_pixel') as f:
                return int(f.read().strip())
        except Exception:
            return 16

    def _read_fb_size(self):
        try:
            with open('/sys/class/graphics/fb0/virtual_size') as f:
                w, h = f.read().strip().split(',')
                return int(w), int(h)
        except Exception:
            return self.screen_w, self.screen_h
