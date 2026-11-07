#!/bin/bash
# Flight Desk Smart Start
# Boot-Animation → Dashboard im Vollbild

echo "Flight Desk - Starting..."

# 1. Boot-Animation im Fullscreen-Terminal zeigen
if [ -f /usr/local/bin/boot.sh ]; then
    if command -v foot &>/dev/null; then
        foot --fullscreen -- bash /usr/local/bin/boot.sh
    else
        /usr/local/bin/boot.sh
    fi
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

# Touch Display 2 = 1280×720 (landscape). The layout is designed for ~800×480,
# so scale 1.5 → 853×480 CSS px: everything fits and buttons get finger-sized.
# Old 800×480 display: DASHBOARD_SCALE=1
SCALE="${DASHBOARD_SCALE:-1.5}"

echo "Using: $CHROMIUM_BIN (scale $SCALE)"
"$CHROMIUM_BIN" \
  --kiosk \
  --ozone-platform=wayland \
  --app=http://localhost:5000 \
  --start-fullscreen \
  --window-position=0,0 \
  --force-device-scale-factor="$SCALE" \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --disable-features=TouchpadOverscrollHistoryNavigation \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-restore-session-state \
  --password-store=basic \
  --disable-translate

echo "Dashboard closed."
