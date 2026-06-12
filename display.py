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
        self._overlay_version = 0    # incremented on add/remove
        self._lock = threading.Lock()
        self._running = True

        # Overlay composite cache — recomputed only when _overlay_version changes
        self._overlay_cache_version = -1
        self._overlay_composite = None  # RGBA PIL.Image or None

        # Keep framebuffer file handle open to avoid 30x/s open/close overhead
        self._fb_fd = None

        self._hide_cursor()
        self._write_black()

        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()
        logging.debug(f"DisplayManager: fb0 {self._fb_w}x{self._fb_h} {self._bits}bpp")

    # ── Public API ────────────────────────────────────────────────────────────

    def update_preview(self, pil_image):
        """Called from camera preview thread. Already RGB + correct size."""
        with self._lock:
            self._preview_frame = pil_image

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
            self._overlay_version += 1
        return oid

    def add_overlay(self, image_path, layer=3):
        """Load a PNG and register as overlay. Returns overlay_id or -1."""
        if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
            logging.warning(f"Overlay missing or empty: {image_path}")
            return -1
        try:
            img = Image.open(image_path).convert('RGBA')
            img = img.resize((self.screen_w, self.screen_h), Image.BILINEAR)
            with self._lock:
                oid = self._next_id
                self._next_id += 1
                self._overlays[oid] = (layer, img)
                self._overlay_version += 1
            return oid
        except Exception as e:
            logging.error(f"add_overlay error ({image_path}): {e}")
            return -1

    def remove_overlay(self, overlay_id):
        if overlay_id == -1:
            return
        with self._lock:
            if overlay_id in self._overlays:
                self._overlays.pop(overlay_id)
                self._overlay_version += 1

    def quit(self):
        self._running = False
        self._write_black()
        if self._fb_fd:
            try:
                self._fb_fd.close()
            except Exception:
                pass

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
            version = self._overlay_version
            overlays = sorted(self._overlays.values(), key=lambda x: x[0]) if version != self._overlay_cache_version else None

        # Rebuild overlay composite only when something changed
        if version != self._overlay_cache_version:
            if overlays:
                composite = Image.new('RGBA', (self.screen_w, self.screen_h), (0, 0, 0, 0))
                for _, overlay_img in overlays:
                    composite.paste(overlay_img, (0, 0), overlay_img)
                self._overlay_composite = composite
            else:
                self._overlay_composite = None
            self._overlay_cache_version = version

        # Fast path: preview only, no overlays
        if preview is not None and self._overlay_composite is None:
            canvas = preview
        elif preview is not None:
            canvas = preview.copy()
            canvas.paste(self._overlay_composite, (0, 0), self._overlay_composite)
        elif self._overlay_composite is not None:
            canvas = Image.new('RGB', (self.screen_w, self.screen_h), (0, 0, 0))
            canvas.paste(self._overlay_composite, (0, 0), self._overlay_composite)
        else:
            return  # nothing to render

        if self.screen_w != self._fb_w or self.screen_h != self._fb_h:
            canvas = canvas.resize((self._fb_w, self._fb_h), Image.BILINEAR)

        self._write_to_fb(canvas)

    # ── Framebuffer I/O ───────────────────────────────────────────────────────

    def _write_to_fb(self, img):
        data = self._encode(img)
        try:
            if self._fb_fd is None:
                self._fb_fd = open(self._fb_path, 'wb')
            self._fb_fd.seek(0)
            self._fb_fd.write(data)
            self._fb_fd.flush()
        except PermissionError:
            logging.error("Cannot write to /dev/fb0 — add user to 'video' group")
            self._running = False
        except Exception as e:
            logging.warning(f"FB write error: {e}")
            try:
                self._fb_fd.close()
            except Exception:
                pass
            self._fb_fd = None  # reopen next frame

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
