#!/bin/bash
# Update Aviation Dashboard auf dem Pi
# Aufruf: bash ~/IndiaLimaYankee/update.sh

cd ~/IndiaLimaYankee

echo "Pulling latest code..."
git pull

echo "Copying start script..."
cp scripts/start_dashboard.sh ~/start_dashboard.sh
chmod +x ~/start_dashboard.sh

echo "Restarting service..."
sudo systemctl restart aviation-dashboard

echo "Done! Dashboard updated."
