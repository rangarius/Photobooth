#!/usr/bin/env python3
import gphoto2 as gp
import io
import logging
import threading
import time
from PIL import Image


class GPhoto2Backend:
    def __init__(self):
        self._camera = None
        self._lock = threading.Lock()
        self._color_effect = None
        self._flip_h = False
        self._flip_v = False
        self._screen_w = 1024
        self._screen_h = 600
        self._preview_active = False
        self._preview_thread = None
        self._on_preview_frame = None
        self._connected = False
        self.on_disconnect = None  # callable() fired when consecutive errors declare a disconnect

    @property
    def is_connected(self):
        return self._connected

    def setup(self, config):
        self._screen_w = config.screen_w
        self._screen_h = config.screen_h
        self._flip_h = config.flip_screen_h
        self._flip_v = config.flip_screen_v

        for attempt in range(5):
            try:
                self._camera = gp.Camera()
                self._camera.init()
                break
            except gp.GPhoto2Error as e:
                logging.critical(f"Camera init error (attempt {attempt+1}/5): {e}")
                if attempt == 4:
                    raise
                time.sleep(1)

        # Enable liveview output to PC so capture_preview() works
        try:
            cam_config = self._camera.get_config()
            output = cam_config.get_child_by_name('output')
            output.set_value('PC')
            self._camera.set_config(cam_config)
        except Exception as e:
            logging.warning(f"Could not set output=PC: {e}")

        self._connected = True
        logging.debug("GPhoto2Backend: ready")

    def start_preview(self, on_frame_callback):
        """Start continuous liveview. Calls on_frame_callback(PIL.Image) per frame."""
        self._on_preview_frame = on_frame_callback
        self._preview_active = True
        self._preview_thread = threading.Thread(target=self._preview_loop, daemon=True)
        self._preview_thread.start()

    def stop_preview(self):
        self._preview_active = False
        if self._preview_thread:
            self._preview_thread.join(timeout=2)
            self._preview_thread = None

    def _preview_loop(self):
        consecutive_errors = 0
        while self._preview_active:
            try:
                with self._lock:
                    preview = self._camera.capture_preview()
                data = preview.get_data_and_size()
                img = Image.open(io.BytesIO(bytes(data))).convert('RGB')
                img = img.resize((self._screen_w, self._screen_h), Image.BILINEAR)
                img = self._apply_flips(img)
                img = self._apply_color_effect(img)
                if self._on_preview_frame:
                    self._on_preview_frame(img)
                consecutive_errors = 0
            except gp.GPhoto2Error as e:
                consecutive_errors += 1
                logging.warning(f"Preview frame error ({consecutive_errors}): {e}")
                if consecutive_errors >= 5:
                    logging.error("Camera lost — stopping preview and signaling disconnect")
                    self._connected = False
                    self._preview_active = False
                    if self.on_disconnect:
                        threading.Thread(target=self.on_disconnect, daemon=True).start()
                    return
                time.sleep(0.05)

    def capture(self, filename):
        """Trigger shutter, download JPEG to filename, apply color effect + flips."""
        with self._lock:
            file_path = self._camera.capture(gp.GP_CAPTURE_IMAGE)
            camera_file = self._camera.file_get(
                file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL
            )
            camera_file.save(filename)

        if self._color_effect in ('bw', 'sepia') or self._flip_h or self._flip_v:
            img = Image.open(filename).convert('RGB')
            img = self._apply_flips(img)
            img = self._apply_color_effect(img)
            img.save(filename, 'JPEG', quality=95)

        logging.debug(f"Captured: {filename}")

    def set_color_effect(self, effect):
        self._color_effect = effect

    def apply_settings(self, iso=None, awb_mode=None, exposure_mode=None,
                       shutterspeed=None, aperture=None,
                       flip_h=None, flip_v=None, **_ignored):
        if flip_h is not None:
            self._flip_h = flip_h
        if flip_v is not None:
            self._flip_v = flip_v

        camera_fields = {k: v for k, v in {
            'iso': iso,
            'whitebalance': awb_mode,
            'autoexposuremode': exposure_mode,
            'shutterspeed': None if shutterspeed in (None, 'auto') else shutterspeed,
            'aperture': None if aperture in (None, 'auto') else aperture,
        }.items() if v is not None}

        if not camera_fields:
            return

        # Stop preview while changing settings — gphoto2 returns -110 (I/O in
        # progress) if set_config() races with an active capture_preview() transfer.
        was_previewing = self._preview_active
        if was_previewing:
            self.stop_preview()
        try:
            cam_config = self._camera.get_config()
            for node_name, value in camera_fields.items():
                try:
                    node = cam_config.get_child_by_name(node_name)
                    node.set_value(str(value))
                    logging.debug(f"Camera: {node_name} = {value}")
                except Exception as e:
                    logging.warning(f"Camera set {node_name}={value} failed: {e}")
            # Retry set_config up to 3 times — -110 can occur if a previous USB
            # transfer (e.g. output=PC in setup()) hasn't fully completed yet.
            for attempt in range(3):
                try:
                    self._camera.set_config(cam_config)
                    break
                except gp.GPhoto2Error as e:
                    if e.code == -110 and attempt < 2:
                        time.sleep(0.3)
                    else:
                        logging.warning(f"apply_settings set_config failed: {e}")
                        break
        except Exception as e:
            logging.warning(f"apply_settings error: {e}")
        finally:
            if was_previewing and self._on_preview_frame:
                self.start_preview(self._on_preview_frame)

    def get_battery_level(self):
        """Return battery level as 0–100 int, or None if unavailable."""
        if not self._camera:
            return None
        try:
            with self._lock:
                cfg = self._camera.get_config()
            node = cfg.get_child_by_name('batterylevel')
            val = node.get_value()          # e.g. "100%", "67%", "33%"
            return int(str(val).strip().rstrip('%'))
        except Exception as e:
            logging.debug(f"get_battery_level failed: {e}")
            return None

    def reconnect(self, config):
        """Close current connection and re-run setup(). Raises on failure; caller should retry."""
        self.stop_preview()
        if self._camera:
            try:
                self._camera.exit()
            except Exception:
                pass
            self._camera = None
        self._connected = False
        self.setup(config)

    def close(self):
        self.stop_preview()
        self._connected = False
        if self._camera:
            try:
                self._camera.exit()
            except Exception:
                pass
            self._camera = None

    def _apply_flips(self, img):
        if self._flip_h:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if self._flip_v:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        return img

    def _apply_color_effect(self, img):
        if self._color_effect == 'bw':
            return img.convert('L').convert('RGB')
        elif self._color_effect == 'sepia':
            return self._sepia(img)
        return img

    def _sepia(self, img):
        try:
            import numpy as np
            arr = np.array(img, dtype=float)
            r = (arr[:,:,0]*0.393 + arr[:,:,1]*0.769 + arr[:,:,2]*0.189).clip(0, 255)
            g = (arr[:,:,0]*0.349 + arr[:,:,1]*0.686 + arr[:,:,2]*0.168).clip(0, 255)
            b = (arr[:,:,0]*0.272 + arr[:,:,1]*0.534 + arr[:,:,2]*0.131).clip(0, 255)
            return Image.fromarray(np.stack([r, g, b], axis=2).astype('uint8'))
        except ImportError:
            from PIL import ImageOps
            return ImageOps.colorize(img.convert('L'), '#704214', '#C0A882').convert('RGB')
