# Photobooth

Raspberry Pi–based photobooth with live preview, multi-shot countdown, template-driven photo cards, and direct printing to a Canon SELPHY CP1300. A Flask web UI (port `4010`) provides full runtime configuration, layout editing, and photo browsing from any device on the network.

**Fork of [sebmueller/Photobooth](https://github.com/sebmueller/Photobooth)** — original concept by [ericBcreator](https://www.hackster.io/ericBcreator/photo-booth-powered-by-a-raspberry-pi-23b491).

---

## Hardware

| Component | Notes |
|---|---|
| Raspberry Pi 3/4/5 | |
| Canon EOS R50 | USB, controlled via gphoto2 |
| 10.1" HDMI display | 1024 × 600, auto-detected via EDID |
| Canon SELPHY CP1300 | USB, driven via CUPS + Gutenprint |
| 2× Arcade buttons | GPIO 23 (left) + GPIO 24 (right) |
| 5 V / 2 A PSU | |
| (optional) DS3231 RTC | I²C at `0x68` |

---

## Install

Clone the repo onto a fresh **Raspbian Bookworm** image, then run:

```bash
git clone https://github.com/sebmueller/Photobooth /home/pi/Photobooth
cd /home/pi/Photobooth
chmod +x install.sh
./install.sh
```

`install.sh` does everything non-interactive in one pass:

1. `apt-get upgrade` + system packages (gphoto2, CUPS, Gutenprint, ImageMagick, SDL2, …)
2. Python packages via pip
3. User added to groups: `lp`, `lpadmin`, `video`, `input`, `plugdev`
4. CUPS configured: `Port 631`, `Allow @LOCAL`, service enabled
5. ImageMagick memory limits raised (512 MiB RAM, 2 GiB disk)
6. Autostart as a **Systemd service** (`photobooth.service`), enabled at boot
7. Quiet boot (`console=tty3 quiet splash …`) written to `cmdline.txt`

After the script finishes:

```bash
sudo reboot
```

### After reboot — add the printer

Browse to `http://<pi-ip>:631/admin`, log in as `pi`, then:

- **Add Printer** → *Canon SELPHY CP1300*
- **Set Default Options** → *Printer Features Common* → **Borderless = Yes**

### Camera

Connect the Canon R50 via USB and set the camera to **PC Connection → PTP** (not MTP).

The booth detects the camera on startup. If the camera is not connected yet, a **"Bitte Kamera anschließen"** message is shown on the display and the app retries automatically every 5 seconds — no restart needed.

---

## Architecture

### State machine (`photobooth.py`)

```
PowerOn → Start → CountdownPhoto → TakePhoto → ShowPhoto
  ↑                                               ↓ (Button1 retake / Button2 next / MaxPics)
  └─── Restart ←── PrintCard ←── ShowCard ←── CreateCard
                       │
                       ├── RefillPaper
                       └── RefillInk
```

- **PowerOn** — waits for the SELPHY (USB vendor `0x04A9` or any CUPS printer).
- **Start** — shows layout chooser; Button1 = layout 1, Button2 = layout 2.
- **CountdownPhoto → TakePhoto** — overlays `ScreenCountdown5..0`, then captures via gphoto2.
- **ShowPhoto** — shows the last shot with retake / next prompt.
- **CreateCard** — composites shots into the chosen template with Wand/ImageMagick.
- **PrintCard** — sends card to CUPS; `error: 02/03` → `RefillPaper`, `error: 06` → `RefillInk`.
- **Restart** — closes and re-opens the camera, returns to PowerOn.

Buttons are polled in a background thread (debounce `0.5 s`). Holding Button1 for 5 s triggers `sudo poweroff`.

### Camera backend (`camera_backend.py`)

`GPhoto2Backend` wraps `python-gphoto2`:

- `setup()` — initialises the camera, sets `output=PC` for live view
- `start_preview(callback)` — streams JPEG frames from `capture_preview()` to the display at ~30 fps
- `capture(filename)` — triggers shutter, downloads the full-res JPEG, applies flips/color effects
- `apply_settings()` — live-changes ISO, white balance, flip axes without restart

### Display (`display.py`)

`DisplayManager` writes directly to `/dev/fb0` (no X11, no pygame):

- 30 fps render loop: composites camera preview + ordered PNG overlays onto the framebuffer
- Supports 16-bit RGB565 and 32-bit RGBA framebuffers
- `show_message(text)` — renders centered text on black, useful for status screens

### Web server (`server.py`)

Flask + Flask-CORS on port **4010**, started in a background thread by `photobooth.py`. Can also run standalone (`python3 server.py`) on a dev machine — a mock `Photobooth` class serves the UI without hardware.

HTTP Basic auth activates when `webserver_user` + `webserver_password` are set in `config.ini`.

#### JSON API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | identity ping |
| GET/POST | `/config` | read / patch global config |
| GET | `/config/save` | persist to `config.ini` |
| GET | `/layouts` | list both card layouts |
| POST | `/layout/edit/<id>` | patch layout `1` or `2` |
| GET | `/layout/save` | persist `card.ini` |
| POST | `/camera/apply` | live-apply camera settings |
| GET | `/status` | FSM state + resolution + print flag |
| GET | `/systemImage/<name>` | fetch a screen overlay PNG |
| POST | `/upload/systemImage` | replace a screen PNG (base64 body) |
| GET | `/photos` | list captured photos |
| GET | `/photo/<name>` | fetch a photo |
| GET | `/restart` | re-run PowerOn check |
| GET | `/button/<n>` | simulate button press (`1` or `2`) — useful for testing without physical buttons |

#### Web UI

| Path | Page |
|---|---|
| `/ui` | Dashboard |
| `/ui/config` | Global config |
| `/ui/camera` | Camera settings |
| `/ui/layouts` | Layout list |
| `/ui/layouts/editor/<n>` | Per-picture editor |
| `/ui/screens` | Browse/replace overlay PNGs |
| `/ui/photos` | Browse photos |

---

## Configuration

**`config.ini`** — global settings:

| Section | Key settings |
|---|---|
| `[Paths]` | `photo_path`, `screen_path`, `template_path` |
| `[InOut]` | `pin_button_left = 23`, `pin_button_right = 24` |
| `[Resolution]` | `screen_w = 1024`, `screen_h = 600`, `flip_screen_h/v` |
| `[Camera]` | `camera_awb_mode`, `camera_iso` |
| `[WebServer]` | `webserver_user`, `webserver_password` |
| `[Debug]` | `print = True/False` (enables/disables printing) |

**`Templates/<name>/card.ini`** — two `[Layout1]` / `[Layout2]` sections with `piccount`, `cardtemplate`, and per-picture `resize_image_x/y_N`, `position_image_x/y_N`, `rotate_image_N`, `color_image_N` (`color` / `bw` / `sepia`).

---

## Running

```bash
# On the Pi (managed by Systemd automatically)
sudo systemctl status photobooth
sudo journalctl -u photobooth -f      # live logs

# Manual start
python3 photobooth.py

# Web UI only (dev machine, no hardware)
python3 server.py
# → http://localhost:4010/ui
```

---

## Repository layout

```
photobooth.py          # FSM + GPIO + camera + print loop
camera_backend.py      # GPhoto2Backend (Canon R50 via gphoto2)
display.py             # DisplayManager (framebuffer, no X11)
server.py              # Flask app (JSON API + /ui)
config_parser.py       # ConfigParser, TemplateParser, Config dataclass
photoCard_new.py       # PhotoCard / PictureOnCard
config.ini             # global config
install.sh             # full setup script for fresh Raspbian Bookworm
requirements.txt       # Flask stack + Wand
Screens/               # overlay PNGs (countdown, logo, prompts, …)
Templates/<event>/     # per-event card template + card.ini
Photos/                # captured shots + rendered cards
Log/                   # timestamped debug logs
Media/                 # demo images for layout preview
```

---

## Optional — DS3231 RTC

```bash
echo 'i2c-bcm2708' | sudo tee -a /etc/modules
sudo apt-get install i2c-tools
sudo i2cdetect -y 1                           # expect 0x68
echo 'dtoverlay=i2c-rtc,ds3231' | sudo tee -a /boot/firmware/config.txt
sudo reboot
sudo apt-get -y remove fake-hwclock
sudo update-rc.d -f fake-hwclock remove
sudo systemctl disable fake-hwclock
# comment out the `if [ -e /run/systemd/system ]` block in /lib/udev/hwclock-set
sudo hwclock -w
```
