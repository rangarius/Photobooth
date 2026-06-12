#!/bin/bash
set -e

echo "================================================"
echo " Photobooth Setup — Canon R50 / Raspberry Pi"
echo "================================================"
echo ""

# ── System-Pakete ────────────────────────────────────────────────────────────
echo "[1/4] System-Pakete installieren..."
sudo apt update
sudo apt install -y \
    gphoto2 \
    libgphoto2-dev \
    imagemagick \
    cups \
    python3-pip \
    python3-numpy \
    libsdl2-2.0-0 \
    w3m \
    vim \
    mc

echo ""

# ── Python-Pakete ────────────────────────────────────────────────────────────
echo "[2/4] Python-Pakete installieren..."
pip3 install --break-system-packages \
    gphoto2 \
    pygame \
    Pillow \
    Wand \
    Flask \
    flask-cors \
    transitions \
    RPi.GPIO \
    pyusb \
    pyudev \
    psutil \
    python-cups

echo ""

# ── Nutzer-Gruppen ───────────────────────────────────────────────────────────
echo "[3/4] Nutzer-Gruppen einrichten..."
sudo usermod -aG lp,video,input "$(whoami)"
echo "  Nutzer $(whoami) zu Gruppen lp, video, input hinzugefügt"

echo ""

# ── CUPS konfigurieren ───────────────────────────────────────────────────────
echo "[4/4] CUPS starten und aktivieren..."
sudo systemctl enable cups
sudo systemctl start cups

echo ""
echo "================================================"
echo " Installation abgeschlossen!"
echo ""
echo " Nächste Schritte:"
echo "   1. Neu einloggen (Gruppen-Änderungen wirksam)"
echo "   2. Drucker in CUPS einrichten: http://localhost:631"
echo "   3. Canon R50 per USB anschließen"
echo "   4. python3 photobooth.py"
echo "================================================"
