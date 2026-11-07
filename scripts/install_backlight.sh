#!/bin/bash
# Allow the dashboard to control the display backlight (night mode / screen off).
# Run once on the Pi:  bash scripts/install_backlight.sh
set -e

RULE_FILE=/etc/udev/rules.d/99-dashboard-backlight.rules
APP_USER=${SUDO_USER:-$(whoami)}

if ! ls /sys/class/backlight/*/brightness >/dev/null 2>&1; then
    echo "❌ Keine steuerbare Hintergrundbeleuchtung gefunden (/sys/class/backlight ist leer)."
    echo "   Ist das Touch Display angeschlossen und der Pi neu gestartet?"
    exit 1
fi

echo "💡 Gefunden: $(ls -d /sys/class/backlight/*)"

# Members of the 'video' group may write the brightness — survives reboots
sudo tee "$RULE_FILE" >/dev/null <<'EOF'
SUBSYSTEM=="backlight", ACTION=="add", RUN+="/bin/chgrp video /sys/class/backlight/%k/brightness", RUN+="/bin/chmod g+w /sys/class/backlight/%k/brightness"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger --action=add --subsystem-match=backlight

if ! id -nG "$APP_USER" | grep -qw video; then
    sudo usermod -aG video "$APP_USER"
    echo "👤 $APP_USER zur Gruppe 'video' hinzugefügt (wirkt nach Neustart des Dienstes/Logins)"
fi

ls -l /sys/class/backlight/*/brightness
echo "✅ Fertig. Danach den Dienst neu starten: sudo systemctl restart aviation-dashboard"
