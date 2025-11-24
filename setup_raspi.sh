#!/bin/bash
# Setup script for Aviation Dashboard on Raspberry Pi

set -e

echo "🛩️  Aviation Dashboard - Raspberry Pi Setup"
echo "=========================================="
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update system
echo "📦 Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Python and dependencies
echo "🐍 Installing Python and system dependencies..."
sudo apt-get install -y python3 python3-pip python3-venv git

# Create virtual environment
echo "🔧 Creating Python virtual environment..."
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install Python packages
echo "📚 Installing Python dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file with your API keys!"
    echo "Run: nano .env"
    echo ""
else
    echo "✅ .env file already exists"
fi

# Create initial data files if they don't exist
if [ ! -f settings.json ]; then
    echo '{"airport": "EDLP", "theme": "dark"}' > settings.json
    echo "✅ Created default settings.json"
fi

if [ ! -f dinos.json ]; then
    echo '{}' > dinos.json
    echo "✅ Created default dinos.json"
fi

echo ""
echo "✨ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file:        nano .env"
echo "2. Test the application:  source .venv/bin/activate && python app.py"
echo "3. Install as service:    sudo bash install_service.sh"
echo ""