#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Detect the real user even when the script is run via sudo
CURRENT_USER="${SUDO_USER:-$(whoami)}"

echo "================================================"
echo " Photobooth Setup — Canon R50 / Raspberry Pi"
echo "================================================"
echo ""
echo "  Verzeichnis: $SCRIPT_DIR"
echo "  Nutzer:      $CURRENT_USER"
echo ""

# Boot-Pfad: Bookworm = /boot/firmware/, älter = /boot/
if [ -f /boot/firmware/config.txt ]; then
    BOOT_CONFIG="/boot/firmware/config.txt"
    BOOT_CMDLINE="/boot/firmware/cmdline.txt"
else
    BOOT_CONFIG="/boot/config.txt"
    BOOT_CMDLINE="/boot/cmdline.txt"
fi

# ── 1. System-Update ─────────────────────────────────────────────────────────
echo "[1/8] System aktualisieren..."
sudo apt-get update
sudo apt-get upgrade -y
echo ""

# ── 2. System-Pakete ─────────────────────────────────────────────────────────
echo "[2/8] System-Pakete installieren..."
sudo apt-get install -y \
    git \
    gphoto2 \
    libgphoto2-dev \
    imagemagick \
    cups \
    printer-driver-gutenprint \
    python3-pip \
    python3-dev \
    python3-numpy \
    python3-cups \
    python3-rpi.gpio \
    libcups2-dev \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-ttf-dev \
    hostapd \
    dnsmasq \
    w3m \
    vim \
    mc
echo ""

# ── 3. Python-Pakete ─────────────────────────────────────────────────────────
echo "[3/8] Python-Pakete installieren..."
pip3 install --break-system-packages \
    gphoto2 \
    pygame \
    Pillow \
    Wand \
    Flask \
    flask-cors \
    transitions \
    pyusb \
    pyudev \
    psutil
echo ""

# ── 4. CUPS konfigurieren ─────────────────────────────────────────────────────
echo "[4/8] CUPS konfigurieren..."
sudo systemctl enable cups
sudo systemctl start cups

# Listen localhost:631 → Port 631 (für Zugriff aus dem LAN)
sudo sed -i 's/^Listen localhost:631/Port 631/' /etc/cups/cupsd.conf

# Allow @LOCAL in allen Location-Blöcken eintragen
sudo python3 - <<'EOF'
import re

with open('/etc/cups/cupsd.conf', 'r') as f:
    content = f.read()

def add_allow(match):
    block = match.group(0)
    if 'Allow @LOCAL' not in block:
        block = re.sub(r'(Order allow,deny)', r'\1\n  Allow @LOCAL', block)
    return block

content = re.sub(r'<Location[^>]*>.*?</Location>', add_allow, content, flags=re.DOTALL)

with open('/etc/cups/cupsd.conf', 'w') as f:
    f.write(content)

print("  cupsd.conf: Port 631 + Allow @LOCAL gesetzt")
EOF

sudo systemctl restart cups

# Nutzer-Gruppen — NACH CUPS (lpadmin-Gruppe wird von cups-Paket angelegt)
echo "[5/8] Nutzer-Gruppen einrichten..."
sudo groupadd -f lpadmin   # -f = kein Fehler wenn Gruppe schon existiert
sudo usermod -aG lp,lpadmin,video,input,plugdev,gpio "$CURRENT_USER"
echo "  $CURRENT_USER → lp, lpadmin, video, input, plugdev, gpio"
echo ""

# ── 6. ImageMagick Policy (Wand braucht höhere Limits) ────────────────────────
echo "[6/8] ImageMagick Policy anpassen..."
IM_POLICY=""
for p in /etc/ImageMagick-6/policy.xml /etc/ImageMagick-7/policy.xml; do
    [ -f "$p" ] && IM_POLICY="$p" && break
done

if [ -n "$IM_POLICY" ]; then
    sudo sed -i 's/<policy domain="resource" name="memory" value="[^"]*"/<policy domain="resource" name="memory" value="512MiB"/' "$IM_POLICY"
    sudo sed -i 's/<policy domain="resource" name="disk" value="[^"]*"/<policy domain="resource" name="disk" value="2GiB"/' "$IM_POLICY"
    echo "  $IM_POLICY: memory=512MiB, disk=2GiB"
else
    echo "  Kein policy.xml gefunden, übersprungen"
fi
echo ""

# ── 7. Autostart + Quiet Boot ─────────────────────────────────────────────────
echo "[7/8] WiFi-AP-Fallback einrichten..."

# Fallback-Script: wartet 30s auf WiFi-Verbindung, öffnet sonst eigenen AP
sudo tee /usr/local/bin/photobooth-wifi.sh > /dev/null <<'WIFIEOF'
#!/bin/bash
AP_SSID="Photobooth"
AP_PASS="photobooth"
TIMEOUT=30

for i in $(seq 1 $TIMEOUT); do
    if nmcli -t -f TYPE,STATE dev 2>/dev/null | grep -q "wifi:connected"; then
        exit 0
    fi
    sleep 1
done

# Kein WiFi gefunden — AP-Verbindung anlegen (einmalig) und starten
if ! nmcli con show photobooth-ap &>/dev/null; then
    nmcli con add type wifi ifname wlan0 con-name photobooth-ap autoconnect no \
        ssid "$AP_SSID" mode ap \
        wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$AP_PASS" \
        ipv4.method shared
fi
nmcli con up photobooth-ap
WIFIEOF
sudo chmod +x /usr/local/bin/photobooth-wifi.sh

# Systemd-Service für WiFi-Fallback
sudo tee /etc/systemd/system/photobooth-wifi.service > /dev/null <<'WIFISVCEOF'
[Unit]
Description=Photobooth WiFi fallback AP
After=NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/photobooth-wifi.sh

[Install]
WantedBy=multi-user.target
WIFISVCEOF

sudo systemctl daemon-reload
sudo systemctl enable photobooth-wifi.service
echo "  WiFi-Fallback aktiviert (SSID: Photobooth, Passwort: photobooth)"
echo ""

# ── 8. Autostart + Quiet Boot ─────────────────────────────────────────────────
echo "[8/8] Autostart + Quiet Boot einrichten..."

# Systemd-Service (zuverlässiger als rc.local auf modernem Raspbian)
# Ensure project directory is owned by the real user (not root)
sudo chown -R "$CURRENT_USER":"$CURRENT_USER" "$SCRIPT_DIR"

sudo tee /etc/systemd/system/photobooth.service > /dev/null <<SVCEOF
[Unit]
Description=Photobooth
After=multi-user.target

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/photobooth.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload
sudo systemctl enable photobooth.service
echo "  Systemd-Service photobooth.service aktiviert (User=$CURRENT_USER)"

# Quiet Boot
if ! grep -q 'quiet splash' "$BOOT_CMDLINE"; then
    sudo sed -i 's/console=tty1/console=tty3/' "$BOOT_CMDLINE"
    sudo sed -i 's/$/ quiet splash loglevel=0 logo.nologo vt.global_cursor_default=0/' "$BOOT_CMDLINE"
    echo "  Quiet Boot in $BOOT_CMDLINE aktiviert"
else
    echo "  Quiet Boot bereits konfiguriert, übersprungen"
fi
echo ""

echo "================================================"
echo " Installation abgeschlossen!"
echo ""
echo " Nächste Schritte:"
echo "   1. sudo reboot  (Gruppen + Boot-Config wirksam)"
echo ""
echo "   Nach dem Neustart:"
echo "   2. Drucker einrichten: http://localhost:631/admin"
echo "      → Drucker hinzufügen → Canon SELPHY CP1300"
echo "      → Standardeinstellungen → Borderless = Yes"
echo "   3. Canon R50 per USB anschließen"
echo "   4. sudo systemctl status photobooth  (startet automatisch)"
echo ""
echo "   WiFi-Fallback:"
echo "   Falls kein bekanntes WLAN erreichbar ist, öffnet der Pi"
echo "   nach 30s einen eigenen Hotspot:"
echo "     SSID:     Photobooth"
echo "     Passwort: photobooth"
echo "     Pi-IP:    192.168.4.1"
echo "================================================"
