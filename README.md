# Aviation Dashboard 🛩️

A Flask-based aviation dashboard featuring real-time METAR/TAF weather data, NASA imagery (APOD & EPIC), flight tracking, and Strava integration. Optimized for Raspberry Pi deployment.

## Quick Start (Raspberry Pi) 🥧

### Clone from GitHub:
```bash
git clone https://github.com/YOUR_USERNAME/IndiaLimaYankee.git
cd IndiaLimaYankee
```

### Automated Setup:
```bash
# Run the setup script
bash setup_raspi.sh

# Configure your API keys
nano .env

# Test the application
source .venv/bin/activate
python app.py
```

### Install as Service (Auto-start on boot):
```bash
# Install and enable systemd service
sudo bash install_service.sh

# The dashboard will now start automatically on boot
# Access it at: http://raspberry-pi-ip:5000
```

## API Keys Required 🔑

Get your free API keys from:
- **NASA API**: https://api.nasa.gov/
- **AVWX Weather**: https://account.avwx.rest/
- **Strava** (optional): https://www.strava.com/settings/api

## Features ✨

### 1. **Caching System** ⚡
- METAR: 5 Minuten Cache
- TAF: 10 Minuten Cache
- NASA APOD: 1 Stunde Cache
- NASA EPIC: 1 Stunde Cache
- Sonnenauf-/untergang: 1 Stunde Cache

**Vorteile:**
- Reduziert API-Calls massiv
- Schnellere Response-Zeiten
- Schont API-Limits
- Weniger Netzwerk-Traffic

### 2. **Environment Variables** 🔐
- API Keys nicht mehr im Code
- Sichere Konfiguration
- Einfaches Deployment
- Koordinaten konfigurierbar

### 3. **Logging System** 📝
- Detaillierte Logs in `aviation_dashboard.log`
- Request-Timing
- Error-Tracking
- Debug-Informationen

### 4. **Neue API Endpoints** 🚀
- `/api/health` - System Health Check
- `/api/config` - Frontend Konfiguration
- `/api/refresh` - Manuelles Cache-Leeren

## Installation 📦

### 1. Dependencies installieren:
```bash
pip install -r requirements.txt
```

### 2. Environment Variables einrichten:
```bash
# .env.example zu .env kopieren
cp .env.example .env

# .env bearbeiten mit deinen API Keys
nano .env
```

### 3. Server starten:
```bash
python app_improved.py
```

## Environment Variables (.env) 🔧

```env
# API Keys
NASA_API_KEY=dein_nasa_key_hier
AVWX_TOKEN=dein_avwx_token_hier

# Koordinaten (Gütersloh)
HOME_LAT=51.963
HOME_LON=8.534

# Optional
DINO_DATA_FILE=dinos.json
SETTINGS_FILE=settings.json
```

## Cache-Verwaltung 🗑️

### Automatisches Caching:
Alle API-Calls werden automatisch gecacht basierend auf der konfigurierten Zeit.

### Manuelles Cache-Leeren:
```bash
# Via API
curl http://localhost:5000/api/refresh

# Oder: Refresh-Button im Dashboard nutzen
```

### Cache wird automatisch geleert bei:
- Airport-Änderung in Settings
- Manuellem Refresh
- Server-Neustart

## Logging 📊

### Log-Datei: `aviation_dashboard.log`

**Was wird geloggt:**
- Alle API-Requests (mit Timing)
- Cache Hits/Misses
- Fehler und Warnings
- Settings-Änderungen
- Server-Start-Info

**Beispiel Log:**
```
2025-01-15 10:30:45 - __main__ - INFO - GET /api/metar - 200 - 0.234s
2025-01-15 10:30:45 - __main__ - DEBUG - Cache HIT for fetch_metar
2025-01-15 10:31:00 - __main__ - INFO - Airport changed to: EDDL, cache cleared
```

## Health Check Endpoint 🏥

**Prüft Status aller APIs:**
```bash
curl http://localhost:5000/api/health
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-01-15T10:30:00",
  "services": {
    "nasa": "ok",
    "avwx": "ok"
  }
}
```

## Performance Verbesserungen 🚀

### Vorher (ohne Cache):
- Jeder Seitenaufruf → 4-5 API-Calls
- Response-Zeit: ~2-3 Sekunden
- API-Limits schnell erreicht

### Nachher (mit Cache):
- Cache Hits → 0 API-Calls
- Response-Zeit: ~50-200ms
- API-Limits geschont

## Neue API-Endpunkte

### `/api/config`
Frontend-Konfiguration:
```json
{
  "refresh_intervals": {
    "metar": 300000,
    "flights": 30000,
    "weather": 300000,
    "apod": 3600000
  },
  "coordinates": {
    "lat": 51.963,
    "lon": 8.534
  }
}
```

### `/api/health`
System-Status:
```json
{
  "status": "ok",
  "services": {
    "nasa": "ok",
    "avwx": "ok"
  }
}
```

### `/api/refresh`
Cache leeren und alle Daten neu laden:
```bash
curl http://localhost:5000/api/refresh
```

## Sicherheit 🔒

### API Keys:
- ✅ Nicht mehr im Code
- ✅ In .env-Datei (nicht versioniert)
- ✅ In Logs maskiert (`***KEY`)

### .gitignore ergänzen:
```
.env
*.log
settings.json
```

## Troubleshooting 🔧

### Problem: "Module not found: dotenv"
```bash
pip install python-dotenv
```

### Problem: API Keys werden nicht geladen
```bash
# Prüfen ob .env existiert
ls -la .env

# .env Datei prüfen
cat .env
```

### Problem: Cache wird nicht geleert
```bash
# Server neu starten
# ODER
curl http://localhost:5000/api/refresh
```

## Raspberry Pi Management 🥧

### Service Management:
```bash
# Start the dashboard
sudo systemctl start aviation-dashboard

# Stop the dashboard
sudo systemctl stop aviation-dashboard

# Restart the dashboard
sudo systemctl restart aviation-dashboard

# View service status
sudo systemctl status aviation-dashboard

# View live logs
sudo journalctl -u aviation-dashboard -f
```

### Accessing the Dashboard:
- **Local**: http://localhost:5000
- **Network**: http://YOUR_PI_IP:5000
- Find your Pi's IP: `hostname -I`

## Cache-Zeiten anpassen 🕐

Im Code `app_improved.py`:

```python
@timed_cache(seconds=300)  # 5 Minuten
def fetch_metar(station="EDLP"):
    ...

# Ändern zu z.B. 10 Minuten:
@timed_cache(seconds=600)
```

## Support 💬

Bei Problemen:
1. Log-Datei prüfen: `cat aviation_dashboard.log`
2. Health-Check: `curl http://localhost:5000/api/health`
3. Environment Variables prüfen: `.env` Datei

---

**Viel Spaß mit deinem Aviation Dashboard! ✈️🦖🌌**