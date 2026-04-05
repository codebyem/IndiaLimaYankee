#!/bin/bash
# Installation Script für Flight Desk Autostart + Boot Animation

set -e

echo "Flight Desk - Installing Boot & Autostart"
echo "=============================================="
echo ""

# Get paths dynamically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
START_SCRIPT="$HOME/start_dashboard.sh"

# 1. Boot-Script ins System kopieren
echo "Installing boot animation..."
sudo cp "$PROJECT_DIR/boot_scripts/boot.sh" /usr/local/bin/boot.sh
sudo chmod +x /usr/local/bin/boot.sh
echo "✓ Boot animation installed to /usr/local/bin/boot.sh"

# 2. Dashboard-Start-Script ins Home kopieren
echo "Installing dashboard start script..."
cp "$SCRIPT_DIR/start_dashboard.sh" "$START_SCRIPT"
chmod +x "$START_SCRIPT"
echo "✓ Dashboard start script installed to $START_SCRIPT"

# 3. Autostart-Verzeichnis erstellen
echo "Creating autostart directory..."
mkdir -p ~/.config/lxsession/LXDE-pi/

# 4. Autostart-Datei erstellen mit korrektem Pfad
echo "Configuring autostart..."
cat > ~/.config/lxsession/LXDE-pi/autostart << EOF
@xset s off
@xset -dpms
@xset s noblank

# Boot Animation + Dashboard im Vollbild-Terminal
@lxterminal --command="bash -c '${START_SCRIPT}; exec bash'"
EOF

echo "✓ Autostart configured at ~/.config/lxsession/LXDE-pi/autostart"
echo ""
echo "=========================================="
echo "Installation complete!"
echo ""
echo "WICHTIG: Für automatischen Start beim Booten muss"
echo "Auto-Login aktiviert sein:"
echo ""
echo "  sudo raspi-config"
echo "  → System Options → Boot / Auto Login"
echo "  → Desktop Autologin"
echo ""
echo "Danach neu starten: sudo reboot"
echo ""
echo "Diagnose-Skript zum Testen: $SCRIPT_DIR/check_autostart.sh"
echo ""
echo "Um Autostart zu deaktivieren:"
echo "  rm ~/.config/lxsession/LXDE-pi/autostart"
echo ""
