#!/bin/bash
# Installation Script für Flight Desk Autostart + Boot Animation

set -e

echo "Flight Desk - Installing Boot & Autostart"
echo "=============================================="
echo ""

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 1. Boot-Script ins System kopieren
echo "Installing boot animation..."
sudo cp "$PROJECT_DIR/boot_scripts/boot.sh" /usr/local/bin/boot.sh
sudo chmod +x /usr/local/bin/boot.sh
echo "✓ Boot animation installed to /usr/local/bin/boot.sh"

# 2. Dashboard-Start-Script ins Home kopieren
echo "Installing dashboard start script..."
cp "$SCRIPT_DIR/start_dashboard.sh" ~/start_dashboard.sh
chmod +x ~/start_dashboard.sh
echo "✓ Dashboard start script installed to ~/start_dashboard.sh"

# 3. Autostart-Verzeichnis erstellen
echo "Creating autostart directory..."
mkdir -p ~/.config/lxsession/LXDE-pi/

# 4. Autostart-Datei erstellen
echo "Configuring autostart..."
cat > ~/.config/lxsession/LXDE-pi/autostart << 'AUTOSTART_EOF'
@xset s off
@xset -dpms
@xset s noblank

# Boot Animation + Dashboard im Vollbild-Terminal
@lxterminal --command="bash -c '/home/pi/start_dashboard.sh; exec bash'"
AUTOSTART_EOF

echo "✓ Autostart configured"
echo ""
echo "=========================================="
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Test the dashboard: ~/start_dashboard.sh"
echo "  2. Reboot to test autostart: sudo reboot"
echo ""
echo "To disable autostart:"
echo "  rm ~/.config/lxsession/LXDE-pi/autostart"
echo ""