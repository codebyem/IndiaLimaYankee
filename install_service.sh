#!/bin/bash
# Install Aviation Dashboard as systemd service

set -e

echo "🛩️  Installing Aviation Dashboard as systemd service"
echo "===================================================="
echo ""

# Get current directory
CURRENT_DIR=$(pwd)
SERVICE_FILE="aviation-dashboard.service"
TEMP_SERVICE="/tmp/aviation-dashboard.service"

# Check if service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Error: $SERVICE_FILE not found"
    exit 1
fi

# Get current user
CURRENT_USER=$(whoami)

# Create temporary service file with correct paths
echo "📝 Creating service file with correct paths..."
sed "s|/home/pi/IndiaLimaYankee|$CURRENT_DIR|g" "$SERVICE_FILE" | \
sed "s|User=pi|User=$CURRENT_USER|g" > "$TEMP_SERVICE"

# Copy service file to systemd directory
echo "📋 Installing service file..."
sudo cp "$TEMP_SERVICE" /etc/systemd/system/aviation-dashboard.service

# Reload systemd
echo "🔄 Reloading systemd..."
sudo systemctl daemon-reload

# Enable service
echo "✅ Enabling service..."
sudo systemctl enable aviation-dashboard.service

echo ""
echo "✨ Service installed successfully!"
echo ""
echo "Useful commands:"
echo "  Start service:   sudo systemctl start aviation-dashboard"
echo "  Stop service:    sudo systemctl stop aviation-dashboard"
echo "  Restart service: sudo systemctl restart aviation-dashboard"
echo "  View status:     sudo systemctl status aviation-dashboard"
echo "  View logs:       sudo journalctl -u aviation-dashboard -f"
echo ""
echo "The service will now start automatically on boot."
echo ""

# Ask if user wants to start now
read -p "Start the service now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo systemctl start aviation-dashboard
    echo "✅ Service started!"
    echo ""
    echo "Check status with: sudo systemctl status aviation-dashboard"
fi