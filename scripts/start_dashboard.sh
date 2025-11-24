#!/bin/bash
# Flight Desk Smart Start
# Boot-Animation → Dashboard im Vollbild

echo "Flight Desk - Starting..."

# 1. Boot-Animation zeigen (falls vorhanden)
if [ -f /usr/local/bin/boot.sh ]; then
    /usr/local/bin/boot.sh
fi

# 2. Warte bis Service läuft
echo "Waiting for aviation-dashboard service..."
while ! systemctl is-active --quiet aviation-dashboard; do
    sleep 2
done

echo "Service is running!"
sleep 3

# 3. Starte Browser im Vollbild
echo "Launching dashboard..."
chromium-browser --kiosk \
  --app=http://localhost:5000 \
  --start-fullscreen \
  --window-size=800,480 \
  --window-position=0,0 \
  --force-device-scale-factor=1 \
  --noerrdialogs \
  --disable-infobars

echo "✈ Dashboard launched!"