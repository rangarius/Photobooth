#!/usr/bin/env python3
import os
import logging
import threading
import pygame
from PIL import Image


class DisplayManager:
    """
    pygame-based display that replaces picamera's hardware overlay system.
    Runs its own render thread at 30fps. Preview frames and overlays are
    passed in from other threads via thread-safe methods.
    """

    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._preview_data = None     # (bytes, (w,h)) — updated by preview thread
        self._overlays = {}           # id -> (layer, bytes, (w,h))
        self._next_id = 0
        self._lock = threading.Lock()
        self._running = True

        pygame.init()
        pygame.mouse.set_visible(False)
        self._screen = pygame.display.set_mode(
            (screen_w, screen_h), pygame.FULLSCREEN | pygame.NOFRAME
        )
        pygame.display.set_caption('Photobooth')
        self._screen.fill((0, 0, 0))
        pygame.display.flip()

        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()

    def _render_loop(self):
        clock = pygame.time.Clock()
        while self._running:
            for event in pygame.event.get():
                pass  # keep event queue drained

            with self._lock:
                preview = self._preview_data
                overlays = sorted(self._overlays.values(), key=lambda x: x[0])

            self._screen.fill((0, 0, 0))

            if preview:
                data, size = preview
                try:
                    surf = pygame.image.fromstring(data, size, 'RGB')
                    self._screen.blit(surf, (0, 0))
                except Exception as e:
                    logging.warning(f"Preview render error: {e}")

            for layer, data, size in overlays:
                try:
                    surf = pygame.image.fromstring(data, size, 'RGBA').convert_alpha()
                    self._screen.blit(surf, (0, 0))
                except Exception as e:
                    logging.warning(f"Overlay render error: {e}")

            pygame.display.flip()
            clock.tick(30)

    def update_preview(self, pil_image):
        """Called from camera preview thread. Stores frame for next render tick."""
        img = pil_image.convert('RGB')
        data = img.tobytes()
        with self._lock:
            self._preview_data = (data, img.size)

    def add_overlay(self, image_path, layer=3):
        """
        Load a PNG and register it as a screen overlay.
        Returns overlay_id (pass to remove_overlay) or -1 on error.
        """
        if not os.path.exists(image_path):
            logging.warning(f"Overlay not found: {image_path}")
            return -1
        try:
            img = Image.open(image_path).convert('RGBA')
            img = img.resize((self.screen_w, self.screen_h), Image.LANCZOS)
            data = img.tobytes()
            with self._lock:
                oid = self._next_id
                self._next_id += 1
                self._overlays[oid] = (layer, data, img.size)
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
        pygame.quit()
