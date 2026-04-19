# Photobooth

Raspberry Pi–based photobooth with live preview, multi-shot countdown, template-driven photo cards, and direct printing to a Canon SELPHY CP1300. A Flask-based web UI (port `4010`) exposes full runtime configuration, layout editing, and screen/photo browsing so the booth can be managed from a phone or laptop on the same network.

## Credits / Fork attribution

- Fork of **[sebmueller/Photobooth](https://github.com/sebmueller/Photobooth)**.
- Original concept and hardware writeup: **[ericBcreator — Photo Booth powered by a Raspberry Pi](https://www.hackster.io/ericBcreator/photo-booth-powered-by-a-raspberry-pi-23b491)**.
- ImageMagick memory tuning reference: https://blog.bigbinary.com/2018/09/12/configuring-memory-allocation-in-imagemagick.html

---

## Hardware

| Component | Notes |
|---|---|
| Raspberry Pi 3 | RPi 4 works too |
| RaspiCam | uses `picamera` (legacy stack) |
| 10.1" HDMI display | 1024 × 600 |
| Canon SELPHY CP1300 | USB, driven via CUPS + Gutenprint |
| 2× Arcade buttons | GPIO 23 (left) + GPIO 24 (right), internal pull-ups |
| 5 V / 2–5 A PSU | |
| (optional) DS3231 RTC | I²C, address `0x68` |
| (optional) USB stick | auto-detected for photo copy |

---

## Architecture

### Runtime

`photobooth.py` runs a finite state machine (`transitions.Machine`) that drives the full capture → composite → print loop:

```
PowerOn → Start → CountdownPhoto → TakePhoto → ShowPhoto
          ↑                                      ↓ (Button1 retake / Button2 next / MaxPics)
          └── Restart ← PrintCard ← ShowCard ← CreateCard
                           │
                           ├── RefillPaper
                           └── RefillInk
```

- **PowerOn** — waits for the SELPHY to appear on USB (vendor id `0x04A9`) or as a CUPS printer.
- **Start** — shows the layout chooser; Button1 = layout 1, Button2 = layout 2.
- **CountdownPhoto → TakePhoto → ShowPhoto** — overlays screens `ScreenCountdown5..0`, captures via `picamera`, then shows the shot with "retake / next" prompt.
- **CreateCard** — composites shots into the chosen card template with Wand / ImageMagick.
- **PrintCard** — sends the card to CUPS, polls printer state; `error: 02/03` → `RefillPaper`, `error: 06` → `RefillInk`.
- **Restart** — closes and re-opens the camera to avoid the overlay memory leak.

Buttons are debounced in software (`0.5 s`), a 5-second hold of Button1 triggers `sudo poweroff`.

### Web server

`server.py` (`flask`, `flask-cors`) runs on port **4010** in a background thread started from `photobooth.py`. It can also be launched standalone (`python3 server.py`) without RPi hardware — a mock `Photobooth` class is used so the UI/API can be developed on macOS/Linux.

Authentication: HTTP Basic, enabled only when `webserver_user` and `webserver_password` are both set in `config.ini`.

Flask secret key is auto-generated to `.flask_secret` on first run.

#### JSON API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | `{"photobox": "true"}` identity ping |
| GET/POST | `/config` | read / patch global config (in-memory) |
| GET | `/config/save` | persist config to `config.ini` |
| GET | `/layouts` | list both card layouts |
| POST | `/layout/edit/<id>` | patch a layout (`1` or `2`) |
| GET | `/layout/save` | persist `Templates/<current>/card.ini` |
| POST | `/camera/apply` | live-apply camera settings (iso, awb, flips) without restart |
| GET | `/status` | FSM state + resolution + print flag |
| GET | `/systemImage/<name>` | fetch a screen overlay by filename |
| POST | `/upload/systemImage` | replace a screen image (base64 body) |
| GET | `/photos` | list photos in `Photos/` |
| GET | `/photo/<name>` | fetch a photo (auth) |
| GET | `/restart` | re-run `on_enter_PowerOn` |

#### UI (Jinja templates in `web_templates/`)

| Path | Page |
|---|---|
| `/ui` | Dashboard — FSM state, resolutions, print flag, restart button |
| `/ui/config` | Global config (paths, resolutions, GPIO pins, web auth) |
| `/ui/camera` | Camera settings (AWB mode, AWB gains, ISO, hflip/vflip) |
| `/ui/layouts` | Layout list |
| `/ui/layouts/editor/<n>` | Per-picture position/rotate/resize/color editor |
| `/ui/screens` | Browse and replace overlay PNGs |
| `/ui/photos` | Browse captured photos |

### Config / templates

- **`config.ini`** — global settings (resolution, GPIO, camera, paths, web auth). Sections: `Debug`, `Paths`, `InOut`, `Resolution`, `Screens`, `Camera`, `WebServer`.
- **`Templates/<name>/card.ini`** — two `[Layout1]` / `[Layout2]` sections, each describing `piccount`, `cardtemplate`, per-picture `resize_image_x/y_N`, `position_image_x/y_N`, `rotate_image_N`, `color_image_N` (`color` / `bw` / `sepia`), and `layout_in_foreground` (whether the PNG template is composited above or below the photos).
- **`Screens/`** — every overlay the booth shows (logo, countdown 0..5, "take photo N", wait, print, "change ink/paper", etc.). Replaceable from `/ui/screens`.
- **`Photos/`** — raw captures + rendered cards, filenames prefixed with the session timestamp.
- `config_parser.py` exposes `ConfigParser`, `TemplateParser`, and `Config` — both read and write are round-trip safe through `configparser`.

---

## Install (Raspbian)

> The booth was originally built against **Raspbian Stretch (2019-04-08)** — that image is still the reference for the `picamera` legacy stack. On Bullseye/Bookworm you must either keep the legacy camera stack enabled (`sudo raspi-config` → *Legacy Camera*) or port to `picamera2`.

### System packages

```bash
sudo apt-get update
sudo apt-get install cups python3-dev python3-pip imagemagick \
    python3-cups python3-picamera python3-rpi.gpio git \
    libusb-1.0 libcups2-dev python3-usb python3-pil.imagetk
```

If `RPi.GPIO` import fails, force a reinstall: `sudo pip3 install RPi.GPIO`.

### Python packages

```bash
pip3 install -r requirements.txt
# extras used by photobooth.py itself (not in requirements.txt):
sudo pip3 install pyudev psutil transitions Wand
```

### `raspi-config`

- *Boot Options* → *Desktop/CLI* → **Console Autologin**
- *Interfacing Options* → **Camera**, **SSH**, **I²C** enable
- *Advanced Options* → **Memory Split** = 256 MB, overscan as needed

### Display (1024 × 600)

Append to `/boot/config.txt`:

```
hdmi_cvt=1024 600 60 3 0 0 0
hdmi_group=2
hdmi_mode=87
dispmanx_offline=1
```

References:
- https://www.raspberrypi.org/forums/viewtopic.php?t=14914
- https://github.com/raspberrypi/userland/issues/232

### Gutenprint 5.3 (required for SELPHY CP1300)

Add the Debian `sid` source temporarily:

```bash
sudo nano /etc/apt/sources.list   # add:
#   deb     [trusted=yes] http://ftp.us.debian.org/debian sid main
#   deb-src [trusted=yes] http://ftp.us.debian.org/debian sid main
sudo apt-get update
sudo apt-get -t sid install printer-driver-gutenprint
sudo reboot
# then comment those lines out again
```

Reference: https://www.raspberrypi.org/forums/viewtopic.php?t=219763

### CUPS + printer

```bash
sudo nano /etc/cups/cupsd.conf
# - change `Listen localhost:631` → `Port 631`
# - add `Allow @LOCAL` inside Location /, /admin, /admin/conf
sudo usermod -aG lpadmin pi
sudo service cups restart
```

Browse to `http://<pi-ip>:631/admin`, log in as `pi`, **Add Printer** → *Canon SELPHY CP1300* → *Set Default Options* → *Printer Features Common* → **Borderless = Yes**.

### Autostart + quiet boot

```bash
sudo nano /etc/rc.local   # before `exit 0`:
#   sudo python3 /home/pi/Photobooth/photobooth.py &

sudo nano /boot/cmdline.txt   # change `tty1` → `console=tty3`, append:
#   quiet splash loglevel=0 logo.nologo vt.global_cursor_default=0
```

### Optional — DS3231 RTC

```bash
sudo nano /etc/modules           # add: i2c-bcm2708
sudo apt-get install i2c-tools
sudo i2cdetect -y 1              # expect 0x68
echo 'dtoverlay=i2c-rtc,ds3231' | sudo tee -a /boot/config.txt
sudo apt-get -y remove fake-hwclock
sudo update-rc.d -f fake-hwclock remove
sudo systemctl disable fake-hwclock
# then comment out the `if [ -e /run/systemd/system ]; exit 0; fi` block in
# /lib/udev/hwclock-set, and:
sudo hwclock -w
```

Guide (PDF): https://cdn-learn.adafruit.com/downloads/pdf/adding-a-real-time-clock-to-raspberry-pi.pdf

### Optional — Samba share + USB automount

Config snippets are in the git history of this file — add a `[PhotoBooth]` share pointing at `/home/pi`, install `usbmount`, and change `MountFlags=slave` → `shared` in `/lib/systemd/system/systemd-udevd.service` so the auto-mount is visible to the booth process.

---

## Running

### On the Pi

```bash
./run                   # same as: python3 photobooth.py
```

This starts the state machine **and** the web server (background thread on `0.0.0.0:4010`).

### Just the web UI (dev machine, no hardware)

```bash
python3 server.py
# http://localhost:4010/ui
```

A stub `Photobooth` class is used; layout + config editing still work against the live files.

---

## Repository layout

```
photobooth.py          # FSM + GPIO + camera + print loop (main)
server.py              # Flask app (JSON API + /ui, runs on :4010)
config_parser.py       # ConfigParser, TemplateParser, Config dataclass
photoCard_new.py       # PhotoCard / PictureOnCard (used by config_parser)
photoCard.py           # legacy variant (still imported by photobooth.py)
config.ini             # global config
requirements.txt       # Flask stack + Wand
run                    # tiny bash shim
web_templates/         # Jinja2 templates for /ui/*
Screens/               # overlay PNGs (countdown, logo, prompts, ...)
Templates/<event>/     # per-event card templates + card.ini
Photos/                # captured shots + rendered cards
Log/                   # timestamped debug logs (created on first run)
Media/                 # demo images for the layout preview screen
```

---

## Credits for stock assets

- Cooltext logos: https://de.cooltext.com/Logo-Design-Outline?Font=11391
