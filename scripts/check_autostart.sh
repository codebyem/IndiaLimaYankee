#!/bin/bash
# Diagnose-Skript: Prüft ob Autostart korrekt konfiguriert ist

echo "======================================"
echo "  Flight Desk - Autostart Diagnose"
echo "======================================"
echo ""

OK=true

# 1. Systemd-Service vorhanden?
echo "[1] Systemd-Service..."
if systemctl list-unit-files | grep -q aviation-dashboard; then
    echo "    ✓ aviation-dashboard.service vorhanden"
else
    echo "    ✗ Service NICHT installiert!"
    echo "      → Führe aus: bash install_service.sh"
    OK=false
fi

# 2. Service aktiviert (autostart on boot)?
echo "[2] Service autostart enabled..."
if systemctl is-enabled --quiet aviation-dashboard 2>/dev/null; then
    echo "    ✓ Service ist beim Boot aktiviert"
else
    echo "    ✗ Service NICHT für autostart aktiviert!"
    echo "      → Führe aus: sudo systemctl enable aviation-dashboard"
    OK=false
fi

# 3. Service läuft gerade?
echo "[3] Service läuft aktuell..."
if systemctl is-active --quiet aviation-dashboard 2>/dev/null; then
    echo "    ✓ Service läuft"
else
    echo "    ✗ Service läuft NICHT!"
    echo "      → Status prüfen: sudo systemctl status aviation-dashboard"
    echo "      → Logs prüfen: sudo journalctl -u aviation-dashboard -n 30"
    OK=false
fi

# 4. Dashboard erreichbar?
echo "[4] Dashboard erreichbar (localhost:5000)..."
if curl -s --max-time 3 http://localhost:5000 > /dev/null 2>&1; then
    echo "    ✓ Dashboard antwortet auf http://localhost:5000"
else
    echo "    ✗ Dashboard NICHT erreichbar!"
    echo "      → Prüfe ob Service läuft und auf Port 5000 hört"
    OK=false
fi

# 5. LXDE-Autostart-Datei vorhanden?
echo "[5] Desktop-Autostart..."
AUTOSTART_FILE="$HOME/.config/lxsession/LXDE-pi/autostart"
if [ -f "$AUTOSTART_FILE" ]; then
    echo "    ✓ Autostart-Datei vorhanden: $AUTOSTART_FILE"
    if grep -q "start_dashboard" "$AUTOSTART_FILE"; then
        echo "    ✓ start_dashboard.sh ist konfiguriert"
    else
        echo "    ✗ start_dashboard.sh NICHT in autostart!"
        echo "      → Führe aus: bash scripts/install_autostart.sh"
        OK=false
    fi
else
    echo "    ✗ Autostart-Datei NICHT vorhanden!"
    echo "      → Führe aus: bash scripts/install_autostart.sh"
    OK=false
fi

# 6. start_dashboard.sh vorhanden und ausführbar?
echo "[6] Start-Skript..."
START_SCRIPT="$HOME/start_dashboard.sh"
if [ -f "$START_SCRIPT" ]; then
    if [ -x "$START_SCRIPT" ]; then
        echo "    ✓ $START_SCRIPT vorhanden und ausführbar"
    else
        echo "    ✗ $START_SCRIPT nicht ausführbar!"
        echo "      → Führe aus: chmod +x $START_SCRIPT"
        OK=false
    fi
else
    echo "    ✗ $START_SCRIPT NICHT vorhanden!"
    echo "      → Führe aus: bash scripts/install_autostart.sh"
    OK=false
fi

# 7. Chromium installiert?
echo "[7] Chromium..."
CHROMIUM_BIN=""
for bin in chromium-browser chromium; do
    if command -v "$bin" &>/dev/null; then
        CHROMIUM_BIN="$bin"
        break
    fi
done
if [ -n "$CHROMIUM_BIN" ]; then
    echo "    ✓ Chromium gefunden: $(which $CHROMIUM_BIN)"
else
    echo "    ✗ Chromium NICHT installiert!"
    echo "      → Installieren mit: sudo apt-get install -y chromium-browser"
    OK=false
fi

# 8. Auto-Login konfiguriert?
echo "[8] Auto-Login..."
if grep -q "autologin" /etc/lightdm/lightdm.conf 2>/dev/null || \
   grep -q "autologin" /etc/lightdm/lightdm.conf.d/*.conf 2>/dev/null || \
   grep -q "autologin-user" /etc/lightdm/lightdm.conf 2>/dev/null; then
    echo "    ✓ Auto-Login scheint konfiguriert"
else
    echo "    ! Auto-Login möglicherweise NICHT konfiguriert"
    echo "      → Aktivieren mit: sudo raspi-config"
    echo "        System Options → Boot / Auto Login → Desktop Autologin"
fi

# Zusammenfassung
echo ""
echo "======================================"
if $OK; then
    echo "  ERGEBNIS: Alles sieht gut aus!"
    echo "  Das Dashboard sollte beim nächsten Boot automatisch starten."
else
    echo "  ERGEBNIS: Probleme gefunden (siehe oben)"
    echo "  Behebe die markierten Punkte und starte neu: sudo reboot"
fi
echo "======================================"
