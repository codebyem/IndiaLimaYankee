from flask import Flask, render_template, jsonify, request
import httpx
from datetime import datetime, date, timedelta
import json
import os
import logging
from logging.handlers import RotatingFileHandler
from functools import lru_cache, wraps
from time import time

# === LOGGING SETUP ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('aviation_dashboard.log', maxBytes=5*1024*1024, backupCount=3),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# === ENVIRONMENT VARIABLES ===
NASA_API_KEY = os.getenv("NASA_API_KEY", "ZXJWkvMvUtYeyDjAVbEjlxR8wkM7tWqgUkinyDwg")
AVWX_TOKEN = os.getenv("AVWX_TOKEN", "0z3Owy4pPyW3RMKfkdRghFWcZdetlrikqOg6vXgx7VQ")

# Home Coordinates
HOME_LAT = float(os.getenv("HOME_LAT", "51.963"))
HOME_LON = float(os.getenv("HOME_LON", "8.534"))

# Files
DINO_DATA_FILE = os.getenv("DINO_DATA_FILE", "dinos.json")
SETTINGS_FILE = os.getenv("SETTINGS_FILE", "settings.json")

logger.info(f"Starting Aviation Dashboard with coordinates: {HOME_LAT}, {HOME_LON}")


# === CACHING DECORATOR ===
def timed_cache(seconds=300):
    """Cache decorator with time-based expiration"""

    def decorator(func):
        cache = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            now = time()

            if key in cache:
                result, timestamp = cache[key]
                if now - timestamp < seconds:
                    logger.debug(f"Cache HIT for {func.__name__}")
                    return result

            logger.debug(f"Cache MISS for {func.__name__}")
            result = func(*args, **kwargs)
            cache[key] = (result, now)
            return result

        wrapper.clear_cache = lambda: cache.clear()
        return wrapper

    return decorator


# === SETTINGS & DINO DATA ===
def load_settings():
    """Load settings from JSON file"""
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            # Ensure countdown fields exist
            settings.setdefault("countdown_label", "Countdown")
            settings.setdefault("countdown_date", "")
            logger.info(f"Settings loaded: {settings}")
            return settings
    except FileNotFoundError:
        logger.warning(f"{SETTINGS_FILE} not found, creating default settings")
        default_settings = {
            "airport_icao": "EDLP",
            "countdown_label": "Countdown",
            "countdown_date": ""
        }
        save_settings(default_settings)
        return default_settings
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return {"airport_icao": "EDLP", "countdown_label": "Countdown", "countdown_date": ""}


def save_settings(settings):
    """Save settings to JSON file"""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
        logger.info(f"Settings saved: {settings}")
        return True
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return False


def load_dino_data():
    """Load dinosaur data from JSON file"""
    try:
        with open(DINO_DATA_FILE, 'r', encoding='utf-8') as f:
            dinos = json.load(f)
            logger.info(f"Loaded {len(dinos)} dinosaurs from {DINO_DATA_FILE}")
            return dinos
    except FileNotFoundError:
        logger.error(f"Warning: {DINO_DATA_FILE} not found")
        return []
    except Exception as e:
        logger.error(f"Error loading dino data: {e}")
        return []


# Load data at startup
APP_SETTINGS = load_settings()
DINO_FACTS = load_dino_data()


def get_daily_dino():
    """Returns a different dinosaur fact each day"""
    if not DINO_FACTS:
        logger.warning("No dino data available")
        return {"name": "No Dino", "fact": "Dino data not available"}

    today = date.today()
    index = today.toordinal() % len(DINO_FACTS)
    dino = DINO_FACTS[index]
    logger.debug(f"Daily dino: {dino['name']}")
    return dino


def get_dino_details(dino_name):
    """Get detailed info about a specific dinosaur"""
    for dino in DINO_FACTS:
        if dino["name"].lower() == dino_name.lower():
            logger.info(f"Found dino details for: {dino_name}")
            return dino

    logger.warning(f"Dino not found: {dino_name}")
    return {"error": "Dino not found"}


def get_countdown_data():
    """Calculate countdown to configured target date"""
    label = APP_SETTINGS.get("countdown_label", "Countdown")
    date_str = APP_SETTINGS.get("countdown_date", "")

    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
            today = date.today()
            days = (target_date - today).days
            return {"label": label, "date": date_str, "days_remaining": days}
        except Exception as e:
            logger.warning(f"Countdown date parse error: {e}")

    return {"label": label, "date": date_str, "days_remaining": None}


# === CACHED API FUNCTIONS ===

@timed_cache(seconds=300)
def fetch_metar(station="EDLP"):
    """Fetch METAR data from AVWX API - Cached for 5 minutes"""
    url = f"https://avwx.rest/api/metar/{station}"
    headers = {"Authorization": f"BEARER {AVWX_TOKEN}"}

    try:
        logger.info(f"Fetching METAR for {station}")
        resp = httpx.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"METAR received for {station}: {data.get('flight_rules', 'N/A')}")
            return {
                "station": data.get("station", "N/A"),
                "raw": data.get("raw", "Keine Daten verfügbar"),
                "flight_rules": data.get("flight_rules", "N/A"),
                "wind_direction": data.get("wind_direction", {}).get("value", "N/A"),
                "wind_speed": data.get("wind_speed", {}).get("value", "N/A"),
                "temperature": data.get("temperature", {}).get("value", "N/A"),
                "dewpoint": data.get("dewpoint", {}).get("value", "N/A"),
                "visibility": data.get("visibility", {}).get("value", "N/A"),
                "altimeter": data.get("altimeter", {}).get("value", "N/A"),
            }
        else:
            logger.error(f"METAR API returned status {resp.status_code} for {station}")
    except Exception as e:
        logger.error(f"METAR Error for {station}: {e}")

    return {
        "station": station,
        "raw": "METAR nicht verfügbar",
        "flight_rules": "N/A",
        "wind_direction": "N/A",
        "wind_speed": "N/A",
        "temperature": "N/A",
        "dewpoint": "N/A",
        "visibility": "N/A",
        "altimeter": "N/A",
    }


@timed_cache(seconds=3600)
def fetch_nasa_apod():
    """Fetch NASA Astronomy Picture of the Day - Cached for 1 hour"""
    url = f"https://api.nasa.gov/planetary/apod?api_key={NASA_API_KEY}"

    try:
        logger.info("Fetching NASA APOD")
        resp = httpx.get(url, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            media_type = data.get("media_type", "image")

            if media_type == "video":
                video_url = data.get("url", "")
                if "youtube.com/watch" in video_url:
                    video_id = video_url.split("v=")[1].split("&")[0] if "v=" in video_url else ""
                    video_url = f"https://www.youtube.com/embed/{video_id}" if video_id else video_url

                logger.info(f"NASA APOD: Video - {data.get('title', 'Unknown')}")
                return {
                    "title": data.get("title", "NASA Video"),
                    "url": video_url,
                    "media_type": "video",
                    "explanation": data.get("explanation", "")[:150] + "..."
                }
            else:
                image_url = data.get("url", "")
                try:
                    test = httpx.head(image_url, timeout=3)
                    if test.status_code == 200:
                        logger.info(f"NASA APOD: Image - {data.get('title', 'Unknown')}")
                        return {
                            "title": data.get("title", "NASA Bild"),
                            "url": image_url,
                            "media_type": "image",
                            "explanation": data.get("explanation", "")[:150] + "..."
                        }
                except Exception as e:
                    logger.warning(f"Image validation failed: {e}")
    except Exception as e:
        logger.error(f"NASA APOD Error: {e}")

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    fallback_url = f"https://api.nasa.gov/planetary/apod?api_key={NASA_API_KEY}&date={yesterday}"

    try:
        resp = httpx.get(fallback_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("media_type") == "image":
                logger.info("Using yesterday's APOD as fallback")
                return {
                    "title": data.get("title", "NASA APOD (Yesterday)"),
                    "url": data.get("url", ""),
                    "media_type": "image",
                    "explanation": "Gestern: " + data.get("explanation", "")[:140] + "..."
                }
    except Exception:
        pass

    logger.warning("Using hardcoded fallback image")
    return {
        "title": "Hubble Ultra Deep Field",
        "url": "https://cdn.esahubble.org/archives/images/screen/heic0611b.jpg",
        "media_type": "image",
        "explanation": "Das Hubble Ultra Deep Field - ein Blick in die Tiefen des Universums."
    }


@timed_cache(seconds=3600)
def fetch_nasa_epic():
    """Fetch latest NASA EPIC Earth image - Cached for 1 hour"""
    try:
        logger.info("Fetching NASA EPIC")
        url = "https://epic.gsfc.nasa.gov/api/natural"
        resp = httpx.get(url, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                item = data[0]
                try:
                    date_str = item["date"]
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    image_url = f"https://epic.gsfc.nasa.gov/archive/natural/{dt.strftime('%Y/%m/%d')}/jpg/{item['image']}.jpg"
                    logger.info(f"NASA EPIC image: {date_str}")
                    return {
                        "caption": item.get("caption", "Earth from Space"),
                        "url": image_url,
                        "date": date_str
                    }
                except Exception as e:
                    logger.warning(f"EPIC parse error: {e}")
    except Exception as e:
        logger.error(f"NASA EPIC Error: {e}")

    logger.warning("Using EPIC fallback image")
    return {
        "caption": "NASA Earth Observatory",
        "url": "https://eoimages.gsfc.nasa.gov/images/imagerecords/73000/73909/world.topo.bathy.200412.3x5400x2700.jpg",
        "date": "Archive Image"
    }


@timed_cache(seconds=600)
def fetch_taf(station="EDLP"):
    """Fetch TAF (Terminal Aerodrome Forecast) - Cached for 10 minutes"""
    url = f"https://avwx.rest/api/taf/{station}"
    headers = {"Authorization": f"BEARER {AVWX_TOKEN}"}

    try:
        logger.info(f"Fetching TAF for {station}")
        resp = httpx.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"TAF received for {station}")
            return {
                "station": data.get("station", station),
                "raw": data.get("raw", "TAF nicht verfügbar"),
                "forecast": data.get("forecast", [])
            }
        else:
            logger.error(f"TAF API returned status {resp.status_code}")
    except Exception as e:
        logger.error(f"TAF Error: {e}")

    return {"station": station, "raw": "TAF nicht verfügbar", "forecast": []}


@timed_cache(seconds=3600)
def calculate_sun_moon_times():
    """Calculate sunrise, sunset times - Cached for 1 hour"""
    try:
        logger.info("Fetching sun/moon times")
        url = f"https://api.sunrise-sunset.org/json?lat={HOME_LAT}&lng={HOME_LON}&formatted=0"
        resp = httpx.get(url, timeout=10)

        if resp.status_code == 200:
            data = resp.json()["results"]
            import pytz
            tz = pytz.timezone("Europe/Berlin")

            def parse_time(time_str):
                dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                return dt.astimezone(tz).strftime("%H:%M")

            times = {
                "sunrise": parse_time(data["sunrise"]),
                "sunset": parse_time(data["sunset"])
            }
            logger.info(f"Sun times: {times}")
            return times
    except Exception as e:
        logger.error(f"Sun/Moon Error: {e}")

    return {"sunrise": "──:──", "sunset": "──:──"}


@timed_cache(seconds=86400)
def fetch_station_info(station="EDLP"):
    """Fetch station/airport info from AVWX - cached for 24 hours"""
    url = f"https://avwx.rest/api/station/{station}"
    headers = {"Authorization": f"BEARER {AVWX_TOKEN}"}

    try:
        logger.info(f"Fetching station info for {station}")
        resp = httpx.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()

            runways = []
            for rwy in data.get("runways", []):
                length_raw = rwy.get("length_ft", {})
                length_ft = length_raw.get("value", 0) if isinstance(length_raw, dict) else length_raw
                surface_raw = rwy.get("surface", {})
                surface = surface_raw.get("value", "") if isinstance(surface_raw, dict) else surface_raw
                runways.append({
                    "ident": f"{rwy.get('ident1', '?')}/{rwy.get('ident2', '?')}",
                    "length_ft": int(length_ft) if length_ft else 0,
                    "surface": surface,
                    "lights": rwy.get("lights", False)
                })

            elev_ft = data.get("elevation_ft") or 0

            logger.info(f"Station info fetched for {station}: {data.get('name')}")
            return {
                "name": data.get("name", station),
                "city": data.get("city", ""),
                "iata": data.get("iata", ""),
                "elevation_ft": int(elev_ft),
                "elevation_m": round(int(elev_ft) * 0.3048),
                "runways": runways,
                "type": data.get("type", "")
            }
        else:
            logger.error(f"Station API returned {resp.status_code} for {station}")

    except Exception as e:
        logger.error(f"Station fetch error: {e}")

    return None


# === REQUEST TIMING MIDDLEWARE ===
@app.before_request
def before_request():
    """Log request start time"""
    request.start_time = time()


@app.after_request
def after_request(response):
    """Log request completion time"""
    if hasattr(request, 'start_time'):
        elapsed = time() - request.start_time
        logger.info(f"{request.method} {request.path} - {response.status_code} - {elapsed:.3f}s")
    return response


@app.errorhandler(Exception)
def handle_exception(e):
    """Global error handler — keeps the server running on unexpected errors"""
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    logger.error(f"Unhandled exception: {e}", exc_info=True)
    if request.path.startswith('/api/'):
        return jsonify({"error": "Internal server error"}), 500
    return render_template("dashboard.html",
                           metar={"station": "ERR", "raw": "", "flight_rules": "N/A",
                                  "wind_direction": "N/A", "wind_speed": "N/A",
                                  "temperature": "N/A", "dewpoint": "N/A",
                                  "visibility": "N/A", "altimeter": "N/A"},
                           dino=get_daily_dino(),
                           nasa_apod={"title": "", "url": "", "media_type": "image"},
                           nasa_epic={"caption": "", "url": "", "date": ""},
                           countdown=get_countdown_data()), 500


# === ROUTES ===

@app.route("/")
def home():
    """Main dashboard page"""
    airport = APP_SETTINGS.get("airport_icao", "EDLP")
    logger.info(f"Loading dashboard for airport: {airport}")

    return render_template(
        "dashboard.html",
        metar=fetch_metar(airport),
        dino=get_daily_dino(),
        nasa_apod=fetch_nasa_apod(),
        nasa_epic=fetch_nasa_epic(),
        countdown=get_countdown_data()
    )


@app.route("/dino")
def dino_page():
    """Dino detail page"""
    dino = get_daily_dino()
    logger.info(f"Loading dino page: {dino['name']}")
    return render_template("dino.html", dino=dino)


@app.route("/settings")
def settings_page():
    """Settings page"""
    return render_template(
        "settings.html",
        current_airport=APP_SETTINGS.get("airport_icao", "EDLP"),
        countdown_label=APP_SETTINGS.get("countdown_label", "Countdown"),
        countdown_date=APP_SETTINGS.get("countdown_date", "")
    )


@app.route("/weather")
def weather_page():
    """Weather radar page"""
    return render_template("weather.html", lat=HOME_LAT, lon=HOME_LON)


@app.route("/flights")
def flights_page():
    """Live flight tracking page"""
    return render_template("flights.html", lat=HOME_LAT, lon=HOME_LON)


# === API ENDPOINTS ===

@app.route("/api/settings", methods=['GET', 'POST'])
def api_settings():
    """Settings API"""
    if request.method == 'POST':
        try:
            data = request.get_json()

            # Airport ICAO (optional in payload)
            if 'airport_icao' in data:
                airport_icao = data['airport_icao'].strip().upper()
                if len(airport_icao) != 4:
                    logger.warning(f"Invalid ICAO length: {airport_icao}")
                    return jsonify({"error": "ICAO must be 4 characters"}), 400
                APP_SETTINGS['airport_icao'] = airport_icao
                fetch_metar.clear_cache()
                fetch_taf.clear_cache()
                fetch_station_info.clear_cache()
                logger.info(f"Airport changed to: {airport_icao}, cache cleared")

            # Countdown settings
            if 'countdown_label' in data:
                APP_SETTINGS['countdown_label'] = data['countdown_label'].strip()
            if 'countdown_date' in data:
                APP_SETTINGS['countdown_date'] = data['countdown_date'].strip()

            if save_settings(APP_SETTINGS):
                return jsonify({"success": True})
            else:
                return jsonify({"error": "Failed to save"}), 500
        except Exception as e:
            logger.error(f"Settings update error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify(APP_SETTINGS)


@app.route("/api/test-airport/<icao>")
def api_test_airport(icao):
    """Test airport ICAO"""
    logger.info(f"Testing airport: {icao}")
    metar = fetch_metar(icao)
    valid = metar.get("station") != "N/A" and metar.get("raw") != "METAR nicht verfügbar"
    return jsonify({"valid": valid, "station": metar.get("station")})


@app.route("/api/countdown")
def api_countdown():
    """Countdown API"""
    return jsonify(get_countdown_data())


@app.route("/api/refresh")
def api_refresh():
    """Refresh all data and clear caches"""
    logger.info("Manual refresh requested - clearing all caches")

    fetch_metar.clear_cache()
    fetch_nasa_apod.clear_cache()
    fetch_nasa_epic.clear_cache()
    fetch_taf.clear_cache()
    calculate_sun_moon_times.clear_cache()

    airport = APP_SETTINGS.get("airport_icao", "EDLP")

    return jsonify({
        "metar": fetch_metar(airport),
        "dino": get_daily_dino(),
        "nasa_apod": fetch_nasa_apod(),
        "nasa_epic": fetch_nasa_epic(),
        "countdown": get_countdown_data()
    })


@app.route("/api/taf")
def api_taf():
    """TAF API"""
    airport = APP_SETTINGS.get("airport_icao", "EDLP")
    return jsonify(fetch_taf(airport))


@app.route("/api/sunmoon")
def api_sunmoon():
    """Sun/Moon API"""
    return jsonify(calculate_sun_moon_times())


@app.route("/api/station")
def api_station():
    """Station info API"""
    airport = APP_SETTINGS.get("airport_icao", "EDLP")
    data = fetch_station_info(airport)
    if data:
        return jsonify(data)
    return jsonify({"error": "Station data unavailable"}), 503


@app.route("/api/dino/<dino_name>")
def api_dino_details(dino_name):
    """Dino details API"""
    return jsonify(get_dino_details(dino_name))


@app.route("/api/health")
def api_health():
    """System health check"""
    logger.info("Health check requested")
    health = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "services": {}
    }

    try:
        resp = httpx.get(f"https://api.nasa.gov/planetary/apod?api_key={NASA_API_KEY}", timeout=5)
        health["services"]["nasa"] = "ok" if resp.status_code == 200 else "error"
    except Exception as e:
        health["services"]["nasa"] = "error"
        logger.error(f"NASA health check failed: {e}")

    try:
        resp = httpx.get(f"https://avwx.rest/api/metar/EDLP",
                         headers={"Authorization": f"BEARER {AVWX_TOKEN}"}, timeout=5)
        health["services"]["avwx"] = "ok" if resp.status_code == 200 else "error"
    except Exception as e:
        health["services"]["avwx"] = "error"
        logger.error(f"AVWX health check failed: {e}")

    health["status"] = "ok" if all(v == "ok" for v in health["services"].values()) else "degraded"

    logger.info(f"Health check result: {health['status']}")
    return jsonify(health)


@app.route("/api/config")
def api_config():
    """Frontend configuration"""
    return jsonify({
        "refresh_intervals": {
            "metar": 300000,
            "flights": 30000,
            "weather": 300000,
            "apod": 3600000,
            "countdown": 3600000
        },
        "coordinates": {
            "lat": HOME_LAT,
            "lon": HOME_LON
        },
        "caching": {
            "metar": "5 minutes",
            "taf": "10 minutes",
            "apod": "1 hour",
            "epic": "1 hour",
            "sunmoon": "1 hour"
        }
    })


@app.route("/api/exit-kiosk", methods=['POST'])
def api_exit_kiosk():
    """Close Chromium kiosk on the Pi"""
    import subprocess
    try:
        subprocess.Popen(['pkill', '-f', 'chromium'])
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/flights")
def api_flights():
    """Proxy OpenSky Network flight data to avoid CORS issues"""
    try:
        lat_delta = float(request.args.get('lat_delta', 1.5))
        lon_delta = float(request.args.get('lon_delta', 2.0))
        lat = float(request.args.get('lat', HOME_LAT))
        lon = float(request.args.get('lon', HOME_LON))
        url = (
            f"https://opensky-network.org/api/states/all"
            f"?lamin={lat-lat_delta}&lomin={lon-lon_delta}"
            f"&lamax={lat+lat_delta}&lomax={lon+lon_delta}"
        )
        resp = httpx.get(url, timeout=10, headers={"User-Agent": "AviationDashboard/1.0"})
        return jsonify(resp.json())
    except Exception as e:
        logger.error(f"Flights API error: {e}")
        return jsonify({"states": None, "error": str(e)}), 200


@app.route("/api/skycards")
def api_skycards():
    """Fetch latest posts from r/Skycards"""
    try:
        resp = httpx.get(
            "https://www.reddit.com/r/Skycards/new.json?limit=10",
            timeout=10,
            headers={"User-Agent": "AviationDashboard/1.0"},
            follow_redirects=True
        )
        data = resp.json()
        posts = []
        for child in data.get("data", {}).get("children", []):
            p = child["data"]
            posts.append({
                "title": p.get("title", ""),
                "url": f"https://reddit.com{p.get('permalink', '')}",
                "thumbnail": p.get("thumbnail") if p.get("thumbnail", "").startswith("http") else None,
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "created_utc": p.get("created_utc", 0),
                "author": p.get("author", ""),
            })
        return jsonify({"posts": posts})
    except Exception as e:
        logger.error(f"Skycards API error: {e}")
        return jsonify({"posts": [], "error": str(e)}), 200


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Starting Aviation Dashboard Server")
    logger.info(f"NASA API Key: {'*' * (len(NASA_API_KEY) - 4) + NASA_API_KEY[-4:]}")
    logger.info(f"AVWX Token: {'*' * (len(AVWX_TOKEN) - 4) + AVWX_TOKEN[-4:]}")
    logger.info(f"Home: {HOME_LAT}, {HOME_LON}")
    logger.info(f"Dinos loaded: {len(DINO_FACTS)}")
    logger.info("=" * 50)

    os.makedirs("templates", exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)
