#!/bin/bash
# Flight Desk Smart Start
# Boot-Animation → Dashboard im Vollbild

echo "Flight Desk - Starting..."

# 1. Boot-Animation zeigen (falls vorhanden)
if [ -f /usr/local/bin/boot.sh ]; then
    /usr/local/bin/boot.sh
fi

# 2. Warte bis Service läuft (max 60 Sekunden)
echo "Waiting for aviation-dashboard service..."
WAIT=0
MAX_WAIT=60
while ! systemctl is-active --quiet aviation-dashboard; do
    sleep 2
    WAIT=$((WAIT + 2))
    if [ $WAIT -ge $MAX_WAIT ]; then
        echo "Warning: Service not active after ${MAX_WAIT}s, starting browser anyway..."
        break
    fi
done

echo "Waited ${WAIT}s — launching dashboard..."
sleep 1

# 3. Chromium starten (kompatibel mit verschiedenen Pi-OS-Versionen)
CHROMIUM_BIN=""
for bin in chromium-browser chromium; do
    if command -v "$bin" &>/dev/null; then
        CHROMIUM_BIN="$bin"
        break
    fi
done

if [ -z "$CHROMIUM_BIN" ]; then
    echo "ERROR: chromium not found. Install with: sudo apt-get install -y chromium-browser"
    exit 1
fi

echo "Using: $CHROMIUM_BIN"
"$CHROMIUM_BIN" \
  --kiosk \
  --app=http://localhost:5000 \
  --start-fullscreen \
  --window-size=800,480 \
  --window-position=0,0 \
  --force-device-scale-factor=1 \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-restore-session-state

echo "Dashboard closed."
