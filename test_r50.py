#!/usr/bin/env python3
"""
Canon R50 gphoto2 Compatibility Test
Testet alle Funktionen die das Photobooth braucht.
Ausgabe: Klares PASS/FAIL pro Test mit Hinweisen.
"""

import subprocess
import sys
import os
import time
import tempfile
from pathlib import Path

BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

results = []

def ok(msg):
    print(f"  {GREEN}✓ {msg}{RESET}")

def fail(msg):
    print(f"  {RED}✗ {msg}{RESET}")

def warn(msg):
    print(f"  {YELLOW}⚠ {msg}{RESET}")

def info(msg):
    print(f"    {msg}")

def header(msg):
    print(f"\n{BOLD}{'─'*55}{RESET}")
    print(f"{BOLD} {msg}{RESET}")
    print(f"{BOLD}{'─'*55}{RESET}")

def run(cmd, timeout=20):
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"

def record(name, passed, note=""):
    results.append((name, passed, note))


# ── Test 1: gphoto2 installiert? ─────────────────────────────────────────────
header("1 · gphoto2 Installation")
code, out, _ = run("gphoto2 --version")
if code == 0:
    ok(f"gphoto2 gefunden: {out.splitlines()[0]}")
    record("gphoto2 installiert", True)
else:
    fail("gphoto2 nicht gefunden → sudo apt install gphoto2")
    record("gphoto2 installiert", False, "apt install gphoto2")
    print(f"\n{RED}Abbruch: gphoto2 fehlt.{RESET}")
    sys.exit(1)

code, out, _ = run("python3 -c 'import gphoto2; print(gphoto2.__version__)'")
if code == 0:
    ok(f"python-gphoto2 Binding: v{out}")
    record("python-gphoto2", True)
else:
    warn("python-gphoto2 nicht installiert → pip install gphoto2")
    info("Testscript nutzt CLI-Fallback, Produktion braucht das Binding.")
    record("python-gphoto2", False, "pip install gphoto2")


# ── Test 2: Kamera erkannt? ───────────────────────────────────────────────────
header("2 · Kamera-Erkennung")
code, out, err = run("gphoto2 --auto-detect")
if code == 0 and "Canon" in out:
    ok("Canon Kamera gefunden:")
    for line in out.splitlines()[2:]:
        if line.strip():
            info(line)
    record("Kamera erkannt", True)
elif code == 0 and out:
    warn("Gerät gefunden, aber kein Canon:")
    info(out)
    record("Kamera erkannt", False, "Kein Canon erkannt")
else:
    fail("Keine Kamera gefunden. USB-Kabel prüfen, Kamera einschalten.")
    if err:
        info(f"Fehler: {err}")
    record("Kamera erkannt", False, "Keine Kamera an USB")
    print(f"\n{RED}Abbruch: Kamera nicht verbunden.{RESET}")
    sys.exit(1)


# ── Test 3: Kamera-Info & Modell ──────────────────────────────────────────────
header("3 · Kamera-Modell & Fähigkeiten")
code, out, _ = run("gphoto2 --get-config /main/status/cameramodel", timeout=10)
if code == 0:
    model = [l for l in out.splitlines() if "Current:" in l]
    if model:
        ok(f"Modell: {model[0].replace('Current:', '').strip()}")
    record("Modell lesbar", True)
else:
    warn("Modell nicht per Config lesbar (unkritisch)")
    record("Modell lesbar", False)

code, out, _ = run("gphoto2 --abilities", timeout=10)
if code == 0:
    abilities = {}
    for line in out.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            abilities[k.strip().lower()] = v.strip()

    capture_ok = abilities.get("capture choices", "")
    info(f"Capture Choices: {capture_ok}")

    if "image" in capture_ok.lower():
        ok("Image-Capture wird unterstützt")
        record("Capture-Fähigkeit", True)
    else:
        warn("Image-Capture nicht in Abilities gelistet")
        record("Capture-Fähigkeit", False, capture_ok)

    preview_ok = abilities.get("capture preview", "")
    info(f"Capture Preview: {preview_ok}")
    if "yes" in preview_ok.lower():
        ok("Preview wird unterstützt")
        record("Preview-Fähigkeit", True)
    else:
        warn(f"Preview-Support unklar: {preview_ok}")
        record("Preview-Fähigkeit", False, preview_ok)
else:
    warn("--abilities nicht aufrufbar")
    record("Abilities", False)


# ── Test 4: Capture (das kritische!) ─────────────────────────────────────────
header("4 · Foto-Aufnahme (kritischster Test!)")
info("Hinweis: Kamera muss in Modus M oder Av sein, kein Sleep-Modus.")

tmpdir = tempfile.mkdtemp()
capture_file = os.path.join(tmpdir, "test_capture.jpg")

info("Versuche --capture-image-and-download ...")
t0 = time.time()
code, out, err = run(
    f"gphoto2 --capture-image-and-download --filename '{capture_file}' --force-overwrite",
    timeout=30
)
elapsed = time.time() - t0

if code == 0 and os.path.exists(capture_file):
    size = os.path.getsize(capture_file)
    ok(f"Capture erfolgreich! Datei: {size//1024} KB in {elapsed:.1f}s")
    record("Capture --capture-image-and-download", True)
else:
    fail(f"--capture-image-and-download fehlgeschlagen (code={code}, {elapsed:.1f}s)")
    if err:
        info(f"stderr: {err[:200]}")
    record("Capture --capture-image-and-download", False, err[:100])

    # Fallback: --trigger-capture
    info("\nFallback: --trigger-capture + --get-all-files ...")
    time.sleep(1)
    code2, _, err2 = run("gphoto2 --trigger-capture", timeout=15)
    if code2 == 0:
        ok("--trigger-capture ausgeführt (Foto wurde auf Karte gespeichert)")
        warn("Download müsste separat erfolgen — für Photobooth aufwendiger")
        record("Capture --trigger-capture", True, "Foto nur auf Kamera, kein direkter Download")
    else:
        fail(f"--trigger-capture auch fehlgeschlagen: {err2[:100]}")
        record("Capture --trigger-capture", False, err2[:100])


# ── Test 5: Liveview / Preview ────────────────────────────────────────────────
header("5 · Liveview Preview (für Display)")
info("Hole 5 Preview-Frames und messe Durchsatz ...")

preview_file = os.path.join(tmpdir, "preview.jpg")
frame_times = []
frame_sizes = []

for i in range(5):
    t0 = time.time()
    code, _, err = run(
        f"gphoto2 --capture-preview --filename '{preview_file}' --force-overwrite",
        timeout=10
    )
    dt = time.time() - t0
    if code == 0 and os.path.exists(preview_file):
        sz = os.path.getsize(preview_file)
        frame_times.append(dt)
        frame_sizes.append(sz)
        print(f"    Frame {i+1}: {dt*1000:.0f}ms, {sz//1024}KB", end="\r")
    else:
        fail(f"Preview-Frame {i+1} fehlgeschlagen: {err[:80]}")
        break

print()

if frame_times:
    avg_ms = sum(frame_times) / len(frame_times) * 1000
    fps = 1000 / avg_ms
    avg_kb = sum(frame_sizes) / len(frame_sizes) / 1024
    ok(f"{len(frame_times)} Frames: ∅{avg_ms:.0f}ms/Frame → ~{fps:.1f}fps möglich")
    ok(f"Frame-Größe: ∅{avg_kb:.0f}KB")

    if fps >= 10:
        ok("Preview-Performance: ausreichend für Photobooth (≥10fps)")
        record("Preview Performance", True, f"~{fps:.0f}fps")
    elif fps >= 5:
        warn(f"Preview etwas langsam ({fps:.1f}fps) — nutzbar aber nicht ideal")
        record("Preview Performance", True, f"~{fps:.0f}fps (langsam)")
    else:
        warn(f"Preview sehr langsam ({fps:.1f}fps) — HDMI Capture Card wäre besser")
        record("Preview Performance", False, f"~{fps:.0f}fps")
else:
    fail("Kein einziger Preview-Frame empfangen")
    record("Preview Performance", False, "Kein Frame")


# ── Test 6: Kamera-Einstellungen lesen/schreiben ──────────────────────────────
header("6 · Kamera-Einstellungen (ISO, Blende, WB)")
settings_to_check = [
    ("/main/imgsettings/iso", "ISO"),
    ("/main/imgsettings/whitebalance", "Weißabgleich"),
    ("/main/capturesettings/aperture", "Blende"),
    ("/main/capturesettings/shutterspeed", "Verschlusszeit"),
    ("/main/capturesettings/focusmode", "Fokus-Modus"),
]

readable = []
for path, label in settings_to_check:
    code, out, _ = run(f"gphoto2 --get-config '{path}'", timeout=8)
    if code == 0:
        current = [l for l in out.splitlines() if "Current:" in l]
        val = current[0].replace("Current:", "").strip() if current else "?"
        ok(f"{label}: {val}")
        readable.append(label)
    else:
        warn(f"{label} nicht lesbar ({path})")

record("Einstellungen lesbar", len(readable) >= 3, f"{len(readable)}/{len(settings_to_check)}")


# ── Test 7: USB-Modus (UVC Webcam) ───────────────────────────────────────────
header("7 · UVC Webcam-Modus (Alternativ-Preview)")
code, out, _ = run("ls /dev/video*")
if code == 0:
    devices = out.strip().splitlines()
    ok(f"Video-Geräte gefunden: {', '.join(devices)}")
    info("R50 könnte als /dev/videoX sichtbar sein wenn in Webcam-Modus")
    record("V4L2 Gerät vorhanden", True, ", ".join(devices))
else:
    warn("Keine /dev/video* Geräte — R50 ist nicht im UVC-Modus")
    info("Kamera-Menü: USB-Modus → 'PC-Verbindung' statt 'EOS Webcam'")
    record("V4L2 Gerät vorhanden", False)


# ── Zusammenfassung ───────────────────────────────────────────────────────────
header("ERGEBNIS")

passed = [(n, note) for n, p, note in results if p]
failed = [(n, note) for n, p, note in results if not p]

print(f"\n{GREEN}{BOLD}PASS ({len(passed)}){RESET}")
for name, _ in passed:
    print(f"  {GREEN}✓{RESET} {name}")

if failed:
    print(f"\n{RED}{BOLD}FAIL ({len(failed)}){RESET}")
    for name, note in failed:
        note_str = f" → {note}" if note else ""
        print(f"  {RED}✗{RESET} {name}{YELLOW}{note_str}{RESET}")

capture_passed = any(n for n, p, _ in results if "Capture" in n and p)
preview_passed = any(p for n, p, _ in results if "Preview" in n)

print()
if capture_passed and preview_passed:
    print(f"{GREEN}{BOLD}→ R50 mit gphoto2 voll nutzbar. Umbau kann starten.{RESET}")
elif preview_passed and not capture_passed:
    print(f"{YELLOW}{BOLD}→ Preview OK, aber Capture hat Probleme.{RESET}")
    print(f"{YELLOW}  Optionen: Kameramodus wechseln (M/Av), libgphoto2 updaten,{RESET}")
    print(f"{YELLOW}  oder Hybrid-Ansatz (UVC Preview + externem Trigger).{RESET}")
elif capture_passed and not preview_passed:
    print(f"{YELLOW}{BOLD}→ Capture OK, Preview schwach. HDMI Capture Card empfohlen.{RESET}")
else:
    print(f"{RED}{BOLD}→ Grundlegende Probleme. Bitte Ausgabe oben prüfen.{RESET}")

# Aufräumen
import shutil
shutil.rmtree(tmpdir, ignore_errors=True)
print()
