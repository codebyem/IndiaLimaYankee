# Raspberry Pi Deployment Guide

Complete step-by-step guide to deploy the Aviation Dashboard on your Raspberry Pi.

---

## Prerequisites

- Raspberry Pi (any model with network connectivity)
- Raspberry Pi OS installed and running
- Network connection (WiFi or Ethernet)
- SSH access enabled on the Pi

---

## Step 1: Find Your Raspberry Pi's IP Address

### Option A: If you have a monitor connected to the Pi
```bash
hostname -I
```

### Option B: From your Mac, scan your network
```bash
# Install nmap if you don't have it
brew install nmap

# Scan your network (replace with your network range)
nmap -sn 192.168.1.0/24 | grep -B 2 "Raspberry"
```

### Option C: Check your router's admin page
Look for a device named "raspberrypi" in the connected devices list.

---

## Step 2: Connect to Your Raspberry Pi via SSH

From your Mac's Terminal:

```bash
# Default Raspberry Pi credentials
# Username: pi
# Password: raspberry (or whatever you set it to)

ssh pi@YOUR_PI_IP_ADDRESS

# Example:
# ssh pi@192.168.1.100
```

**First time connecting?** You'll see a message about authenticity. Type `yes` and press Enter.

---

## Step 3: Update Your Raspberry Pi (Recommended)

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

This may take 5-10 minutes depending on your Pi.

---

## Step 4: Clone the Repository

```bash
# Navigate to home directory
cd ~

# Clone your repository
git clone https://github.com/codebyem/IndiaLimaYankee.git

# Enter the project directory
cd IndiaLimaYankee
```

---

## Step 5: Run the Automated Setup Script

```bash
# Make the script executable (if needed)
chmod +x setup_raspi.sh

# Run the setup script
bash setup_raspi.sh
```

**What this does:**
- Installs Python 3 and pip
- Creates a virtual environment
- Installs all Python dependencies
- Creates default configuration files

**This will take 5-10 minutes.** You'll see progress messages.

---

## Step 6: Configure Your API Keys

```bash
# Edit the .env file
nano .env
```

**Required configuration:**

```env
# Get your NASA API key at: https://api.nasa.gov/
NASA_API_KEY=your_actual_nasa_api_key_here

# Get your AVWX token at: https://account.avwx.rest/
AVWX_TOKEN=your_actual_avwx_token_here

# Optional: Strava integration
STRAVA_CLIENT_ID=your_strava_client_id
STRAVA_CLIENT_SECRET=your_strava_client_secret
STRAVA_REFRESH_TOKEN=your_strava_refresh_token

# Your home coordinates (default is Gütersloh)
HOME_LAT=51.963
HOME_LON=8.534
```

**How to edit in nano:**
1. Use arrow keys to navigate
2. Type your API keys
3. Press `Ctrl + X` to exit
4. Press `Y` to save
5. Press `Enter` to confirm

---

## Step 7: Test the Application

Before installing as a service, let's test it:

```bash
# Activate the virtual environment
source .venv/bin/activate

# Run the application
python app.py
```

**You should see:**
```
* Running on http://0.0.0.0:5000
* Running on http://YOUR_PI_IP:5000
```

**Test it:** Open a web browser on your Mac and go to:
```
http://YOUR_PI_IP:5000
```

You should see the Aviation Dashboard!

**Stop the test:** Press `Ctrl + C` in the terminal.

---

## Step 8: Install as System Service (Auto-start on boot)

```bash
# Make sure you're in the project directory
cd ~/IndiaLimaYankee

# Make the install script executable (if needed)
chmod +x install_service.sh

# Install the service
sudo bash install_service.sh
```

**When prompted "Start the service now? (y/n)"**, press `y` and Enter.

---

## Step 9: Verify the Service is Running

```bash
# Check service status
sudo systemctl status aviation-dashboard

# You should see "active (running)" in green
```

---

## Step 10: Access Your Dashboard

From any device on your network, open a web browser and go to:

```
http://YOUR_PI_IP:5000
```

**Bookmark this URL for easy access!**

---

## Common Management Commands

### Start/Stop/Restart the Service

```bash
# Start
sudo systemctl start aviation-dashboard

# Stop
sudo systemctl stop aviation-dashboard

# Restart (after making changes)
sudo systemctl restart aviation-dashboard

# Check status
sudo systemctl status aviation-dashboard
```

### View Logs

```bash
# View live logs (press Ctrl+C to exit)
sudo journalctl -u aviation-dashboard -f

# View last 50 lines
sudo journalctl -u aviation-dashboard -n 50

# View logs from today
sudo journalctl -u aviation-dashboard --since today
```

### Update the Application

```bash
# SSH into your Pi
ssh pi@YOUR_PI_IP

# Navigate to project directory
cd ~/IndiaLimaYankee

# Pull latest changes from GitHub
git pull

# Restart the service
sudo systemctl restart aviation-dashboard
```

---

## Troubleshooting

### Problem: Can't access the dashboard

**Check if service is running:**
```bash
sudo systemctl status aviation-dashboard
```

**Check logs for errors:**
```bash
sudo journalctl -u aviation-dashboard -n 50
```

**Restart the service:**
```bash
sudo systemctl restart aviation-dashboard
```

### Problem: API keys not working

**Verify .env file:**
```bash
cd ~/IndiaLimaYankee
cat .env
```

Make sure there are no extra spaces or quotes around your API keys.

### Problem: Service won't start

**Check for syntax errors:**
```bash
cd ~/IndiaLimaYankee
source .venv/bin/activate
python app.py
```

This will show you any error messages.

### Problem: Port 5000 already in use

**Find what's using port 5000:**
```bash
sudo lsof -i :5000
```

**Kill the process:**
```bash
sudo kill -9 PROCESS_ID
```

---

## Optional: Set Static IP Address

To ensure your Pi always has the same IP address:

### On Raspberry Pi OS (Bookworm or newer):
```bash
sudo nmtui
```

1. Select "Edit a connection"
2. Choose your connection (WiFi or Ethernet)
3. Change IPv4 from "Automatic" to "Manual"
4. Set your desired IP, gateway, and DNS
5. Save and exit
6. Reboot: `sudo reboot`

---

## Optional: Access from Internet (Advanced)

If you want to access your dashboard from outside your home network:

1. **Port forwarding:** Set up port forwarding on your router (port 5000 → your Pi's IP)
2. **Dynamic DNS:** Use a service like No-IP or DuckDNS
3. **Security:** Consider adding authentication or using a reverse proxy with HTTPS

⚠️ **Security Warning:** Exposing services to the internet requires proper security measures.

---

## Performance Tips

### For Raspberry Pi Zero/1:
The dashboard may be slow on older Pis. Consider:
- Increasing cache times in app.py
- Using a lightweight browser
- Reducing refresh intervals

### For Raspberry Pi 3/4/5:
Should run smoothly with default settings.

---

## Next Steps

- Configure your home airport in the dashboard settings
- Set up Strava integration (optional)
- Customize cache times if needed
- Enjoy your Aviation Dashboard!

---

## Quick Reference Card

```bash
# Service commands
sudo systemctl start aviation-dashboard    # Start
sudo systemctl stop aviation-dashboard     # Stop
sudo systemctl restart aviation-dashboard  # Restart
sudo systemctl status aviation-dashboard   # Status

# View logs
sudo journalctl -u aviation-dashboard -f   # Live logs

# Update from GitHub
cd ~/IndiaLimaYankee && git pull && sudo systemctl restart aviation-dashboard

# Access URL
http://YOUR_PI_IP:5000
```

---

**Questions?** Check the main README.md or the troubleshooting section above.