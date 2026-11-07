from flask import Flask, render_template, jsonify, request
import httpx
from datetime import datetime, date, timedelta
import json
import math
import os
import re
import threading
import logging
from html import unescape
import xml.etree.ElementTree as ET
from logging.handlers import RotatingFileHandler
from functools import wraps
from time import time
from dotenv import load_dotenv

from display import DisplayController

# Load .env next to this file (works regardless of the working directory)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

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
# httpx logs full request URLs at INFO — that would write the NASA key into the log file
logging.getLogger("httpx").setLevel(logging.WARNING)

app = Flask(__name__)

# === ENVIRONMENT VARIABLES ===
# NASA's public DEMO_KEY works without signup (rate-limited); set your own in .env
NASA_API_KEY = os.getenv("NASA_API_KEY") or "DEMO_KEY"

# Free, keyless data sources
AWC_API = "https://aviationweather.gov/api/data"   # METAR / TAF / airport info
ADSB_API = "https://api.adsb.lol/v2"               # live aircraft positions
HTTP_HEADERS = {"User-Agent": "AviationDashboard/2.0 (+https://github.com/codebyem/IndiaLimaYankee)"}

# Debug mode exposes the Werkzeug debugger (remote code execution) — only enable locally
DEBUG = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")

# Home Coordinates
HOME_LAT = float(os.getenv("HOME_LAT", "51.963"))
HOME_LON = float(os.getenv("HOME_LON", "8.534"))

# Files
DINO_DATA_FILE = os.getenv("DINO_DATA_FILE", "dinos.json")
SETTINGS_FILE = os.getenv("SETTINGS_FILE", "settings.json")

logger.info(f"Starting Aviation Dashboard with coordinates: {HOME_LAT}, {HOME_LON}")


# === CACHING DECORATOR ===
MAX_STALE_SECONDS = 6 * 3600   # older than this: fetch synchronously instead of serving stale data


def timed_cache(seconds=300, cache_if=lambda result: True):
    """Cache decorator with time-based expiration and stale-while-revalidate.

    Expired entries are returned immediately while a background thread refreshes
    them — a tap on HOME never waits for NASA or aviationweather.gov.
    cache_if decides whether a result is worth keeping — fallback/error results
    must not be cached, otherwise one timeout shows N/A until the cache expires.
    """

    def decorator(func):
        cache = {}
        refreshing = set()
        lock = threading.Lock()

        def compute(key, args, kwargs):
            result = func(*args, **kwargs)
            if cache_if(result):
                cache[key] = (result, time())
            else:
                logger.warning(f"{func.__name__} returned fallback data — not caching")
            return result

        def refresh_in_background(key, args, kwargs):
            try:
                compute(key, args, kwargs)
            except Exception as e:
                logger.error(f"Background refresh of {func.__name__} failed: {e}")
            finally:
                with lock:
                    refreshing.discard(key)

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            entry = cache.get(key)

            if entry:
                result, timestamp = entry
                age = time() - timestamp
                if age < seconds:
                    return result
                if age < MAX_STALE_SECONDS:
                    with lock:
                        start = key not in refreshing
                        refreshing.add(key)
                    if start:
                        logger.debug(f"Serving stale {func.__name__}, refreshing in background")
                        threading.Thread(target=refresh_in_background, args=(key, args, kwargs),
                                         daemon=True).start()
                    return result

            return compute(key, args, kwargs)

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

def awc_get(product, station):
    """Query aviationweather.gov; returns the first JSON record or None (one retry on timeout)"""
    for attempt in (1, 2):
        try:
            resp = httpx.get(f"{AWC_API}/{product}", params={"ids": station, "format": "json"},
                             headers=HTTP_HEADERS, timeout=10)
            break
        except httpx.TimeoutException:
            if attempt == 2:
                raise
            logger.warning(f"AWC {product} timeout for {station}, retrying")
    if resp.status_code != 200 or not resp.text.strip():
        logger.error(f"AWC {product} returned status {resp.status_code} for {station}")
        return None
    data = resp.json()
    return data[0] if data else None


def format_visibility(visib):
    """AWC reports statute miles ('6+' = 10 km or more) — convert to km"""
    if visib is None:
        return "N/A"
    text = str(visib)
    if text.endswith("+"):
        return "≥10"
    try:
        return f"{float(text) * 1.609:.1f}".rstrip("0").rstrip(".")
    except ValueError:
        return text


@timed_cache(seconds=300, cache_if=lambda r: r["raw"] != "METAR nicht verfügbar")
def fetch_metar(station="EDLP"):
    """Fetch METAR from aviationweather.gov (no key) - Cached for 5 minutes"""
    try:
        logger.info(f"Fetching METAR for {station}")
        data = awc_get("metar", station)

        if data:
            logger.info(f"METAR received for {station}: {data.get('fltCat', 'N/A')}")
            wdir = data.get("wdir")
            return {
                "station": data.get("icaoId", station),
                "raw": data.get("rawOb", "Keine Daten verfügbar"),
                "flight_rules": data.get("fltCat") or "N/A",
                "wind_direction": "VRB" if wdir == "VRB" else (wdir if wdir is not None else "N/A"),
                "wind_speed": data.get("wspd", "N/A"),
                "temperature": data.get("temp", "N/A"),
                "dewpoint": data.get("dewp", "N/A"),
                "visibility": format_visibility(data.get("visib")),
                "altimeter": round(data["altim"]) if data.get("altim") is not None else "N/A",
            }
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


APOD_FALLBACK = {
    "title": "Hubble Ultra Deep Field",
    "url": "https://cdn.esahubble.org/archives/images/screen/heic0611b.jpg",
    "media_type": "image",
    "explanation": "Das Hubble Ultra Deep Field - ein Blick in die Tiefen des Universums."
}


def _apod_from_api():
    """api.nasa.gov — often returns 500 or a 'NASA Science' placeholder since APOD moved"""
    resp = httpx.get("https://api.nasa.gov/planetary/apod",
                     params={"api_key": NASA_API_KEY}, headers=HTTP_HEADERS, timeout=10)
    if resp.status_code != 200:
        logger.warning(f"APOD API returned {resp.status_code}")
        return None
    data = resp.json()
    url = data.get("url", "")
    # Placeholder response: title "NASA Science" with the NASA logo as image
    if not url or "nasa-logo" in url or data.get("title", "").strip() == "NASA Science":
        logger.warning("APOD API returned placeholder data")
        return None

    if data.get("media_type") == "video":
        if "youtube.com/watch" in url and "v=" in url:
            url = f"https://www.youtube.com/embed/{url.split('v=')[1].split('&')[0]}"
        media_type = "video"
    else:
        media_type = "image"
    return {
        "title": data.get("title", "NASA APOD"),
        "url": url,
        "media_type": media_type,
        "explanation": data.get("explanation", "")[:150] + "..."
    }


def _meta(html, prop):
    m = re.search(rf'<meta property="{prop}" content="([^"]*)"', html)
    return unescape(m.group(1)) if m else ""


def _apod_from_website():
    """APOD now lives at science.nasa.gov/apod — read today's article's og:title/og:image"""
    landing = httpx.get("https://science.nasa.gov/apod/", headers=HTTP_HEADERS,
                        timeout=15, follow_redirects=True)
    landing.raise_for_status()
    # Article links look like /image-article/apod-2026-november-7-<slug>/ ; newest first
    links = re.findall(r'href="(https://science\.nasa\.gov/image-article/apod-(\d{4})-([a-z]+)-(\d{1,2})-[^"]*)"',
                       landing.text)
    if not links:
        logger.warning("No APOD article links found on science.nasa.gov")
        return None

    def link_date(link):
        try:
            return datetime.strptime(f"{link[1]} {link[2]} {link[3]}", "%Y %B %d")
        except ValueError:
            return datetime.min

    article_url = max(links, key=link_date)[0]
    article = httpx.get(article_url, headers=HTTP_HEADERS, timeout=15, follow_redirects=True)
    article.raise_for_status()

    image = _meta(article.text, "og:image")
    if not image:
        return None
    # "APOD: 2026 November 7 – De Gerlache-Kocher Massif - NASA Science" → "De Gerlache-Kocher Massif"
    title = _meta(article.text, "og:title").removesuffix(" - NASA Science")
    title = re.sub(r"^APOD:\s*\d{4} \w+ \d{1,2}\s*[–-]\s*", "", title)
    return {
        "title": title or "NASA APOD",
        "url": image,
        "media_type": "image",
        "explanation": _meta(article.text, "og:description")[:150]
    }


@timed_cache(seconds=3600, cache_if=lambda r: r is not APOD_FALLBACK)
def fetch_nasa_apod():
    """NASA Astronomy Picture of the Day - Cached for 1 hour (API first, then website)"""
    for source in (_apod_from_api, _apod_from_website):
        try:
            logger.info(f"Fetching NASA APOD via {source.__name__}")
            result = source()
            if result:
                logger.info(f"NASA APOD: {result['media_type']} - {result['title']}")
                return result
        except Exception as e:
            logger.error(f"NASA APOD error ({source.__name__}): {e}")

    logger.warning("Using hardcoded APOD fallback image")
    return APOD_FALLBACK


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


@timed_cache(seconds=600, cache_if=lambda r: r["raw"] != "TAF nicht verfügbar")
def fetch_taf(station="EDLP"):
    """Fetch TAF (Terminal Aerodrome Forecast) from aviationweather.gov - Cached for 10 minutes"""
    try:
        logger.info(f"Fetching TAF for {station}")
        data = awc_get("taf", station)

        if data:
            logger.info(f"TAF received for {station}")
            return {
                "station": data.get("icaoId", station),
                "raw": data.get("rawTAF", "TAF nicht verfügbar"),
                "forecast": data.get("fcsts", [])
            }
    except Exception as e:
        logger.error(f"TAF Error: {e}")

    return {"station": station, "raw": "TAF nicht verfügbar", "forecast": []}


@timed_cache(seconds=3600, cache_if=lambda r: r["sunrise"] != "──:──")
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


@timed_cache(seconds=86400, cache_if=lambda r: r is not None)
def fetch_station_info(station="EDLP"):
    """Fetch airport info from aviationweather.gov - cached for 24 hours"""
    surfaces = {"H": "Hart", "A": "Asphalt", "C": "Beton", "G": "Gras", "T": "Gras", "W": "Wasser"}

    try:
        logger.info(f"Fetching station info for {station}")
        data = awc_get("airport", station)

        if data:
            runways = []
            for rwy in data.get("runways", []):
                length_ft = 0
                try:
                    length_ft = int(str(rwy.get("dimension", "")).split("x")[0])
                except ValueError:
                    pass
                surface = rwy.get("surface") or ""
                runways.append({
                    "ident": rwy.get("id", "?"),
                    "length_ft": length_ft,
                    "surface": surfaces.get(surface, surface),
                    "lights": False
                })

            elev_m = data.get("elev") or 0   # AWC reports elevation in metres

            logger.info(f"Station info fetched for {station}: {data.get('name')}")
            return {
                "name": (data.get("name") or station).title(),
                "city": "",
                "iata": data.get("iataId") or "",
                "elevation_ft": round(elev_m / 0.3048),
                "elevation_m": round(elev_m),
                "runways": runways,
                "type": ""
            }

    except Exception as e:
        logger.error(f"Station fetch error: {e}")

    return None


# === DISPLAY / NIGHT MODE ===
DISPLAY = DisplayController(APP_SETTINGS, save_settings, calculate_sun_moon_times)


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
        # The APOD API is unreliable; the dashboard falls back to the website, so check that
        resp = httpx.get("https://science.nasa.gov/apod/", headers=HTTP_HEADERS,
                         timeout=5, follow_redirects=True)
        health["services"]["nasa"] = "ok" if resp.status_code == 200 else "error"
    except Exception as e:
        health["services"]["nasa"] = "error"
        logger.error(f"NASA health check failed: {e}")

    checks = {
        "aviationweather": (f"{AWC_API}/metar", {"ids": "EDLP", "format": "json"}),
        "adsb": (f"{ADSB_API}/point/{HOME_LAT}/{HOME_LON}/5", None),
    }
    for name, (url, params) in checks.items():
        try:
            resp = httpx.get(url, params=params, headers=HTTP_HEADERS, timeout=5)
            health["services"][name] = "ok" if resp.status_code == 200 else "error"
        except Exception as e:
            health["services"][name] = "error"
            logger.error(f"{name} health check failed: {e}")

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


@app.route("/api/display", methods=['GET', 'POST'])
def api_display():
    """Night mode / screen-off state and settings"""
    if request.method == 'POST':
        error = DISPLAY.update(request.get_json(silent=True) or {})
        if error:
            return jsonify({"error": error}), 400
    return jsonify(DISPLAY.apply())


@app.route("/api/display/off", methods=['POST'])
def api_display_off():
    """Black screen with only a wake button; backlight to minimum"""
    return jsonify(DISPLAY.screen_off())


@app.route("/api/display/on", methods=['POST'])
def api_display_on():
    DISPLAY.screen_on()
    return jsonify(DISPLAY.apply())


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
    """Live aircraft from adsb.lol (no key), returned in OpenSky 'states' format for the frontend"""
    try:
        lat_delta = float(request.args.get('lat_delta', 1.5))
        lon_delta = float(request.args.get('lon_delta', 2.0))
        lat = float(request.args.get('lat', HOME_LAT))
        lon = float(request.args.get('lon', HOME_LON))

        # Box → radius in nautical miles (1° lat = 60 NM); adsb.lol caps at 250 NM
        radius = max(lat_delta * 60, lon_delta * 60 * math.cos(math.radians(lat)))
        radius = min(250, round(radius))

        resp = httpx.get(f"{ADSB_API}/point/{lat}/{lon}/{radius}", timeout=10, headers=HTTP_HEADERS)
        resp.raise_for_status()
        aircraft = resp.json().get("ac") or []

        now = time()
        states = []
        for ac in aircraft:
            if ac.get("lat") is None or ac.get("lon") is None:
                continue
            # Keep the requested rectangle (the API returns a circle)
            if abs(ac["lat"] - lat) > lat_delta or abs(ac["lon"] - lon) > lon_delta:
                continue

            alt_baro = ac.get("alt_baro")
            on_ground = alt_baro == "ground"
            ft_to_m = lambda v: v * 0.3048 if isinstance(v, (int, float)) else None
            rate = ac.get("baro_rate", ac.get("geom_rate"))
            ident = " · ".join(x for x in (ac.get("r"), ac.get("t")) if x)

            # Index layout matches OpenSky /states/all so flights.html stays unchanged
            states.append([
                ac.get("hex", ""),
                ac.get("flight", ""),
                ident or None,                                   # "country" slot → registration · type
                now - ac.get("seen_pos", 0),
                now - ac.get("seen", 0),
                ac["lon"],
                ac["lat"],
                None if on_ground else ft_to_m(alt_baro),
                on_ground,
                ac["gs"] * 0.514444 if ac.get("gs") is not None else None,   # kt → m/s
                ac.get("track", ac.get("true_heading")),
                rate * 0.00508 if isinstance(rate, (int, float)) else None,  # ft/min → m/s
                None,
                ft_to_m(ac.get("alt_geom")),
                ac.get("squawk"),
            ])

        return jsonify({"time": int(now), "states": states})
    except Exception as e:
        logger.error(f"Flights API error: {e}")
        return jsonify({"states": None, "error": str(e)}), 200


@app.route("/api/skycards")
def api_skycards():
    """Latest posts from r/Skycards via RSS (the unauthenticated .json API now returns 403)"""
    return jsonify({"posts": fetch_skycards()})


@timed_cache(seconds=300, cache_if=bool)
def fetch_skycards():
    ns = {"a": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/"}
    try:
        resp = httpx.get("https://www.reddit.com/r/Skycards/new/.rss?limit=10",
                         timeout=15, headers=HTTP_HEADERS, follow_redirects=True)
        logger.info(f"Reddit RSS status: {resp.status_code}")
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        posts = []
        for entry in root.findall("a:entry", ns):
            link = entry.find("a:link", ns)
            thumb = entry.find("media:thumbnail", ns)
            published = entry.findtext("a:published", default="", namespaces=ns)
            try:
                created = datetime.fromisoformat(published).timestamp()
            except ValueError:
                created = 0
            posts.append({
                "title": entry.findtext("a:title", default="", namespaces=ns),
                "url": link.get("href") if link is not None else "",
                "thumbnail": thumb.get("url") if thumb is not None else None,
                "score": None,          # not included in RSS
                "num_comments": None,   # not included in RSS
                "created_utc": created,
                "author": entry.findtext("a:author/a:name", default="", namespaces=ns).removeprefix("/u/"),
            })
        return posts
    except Exception as e:
        logger.error(f"Skycards RSS error: {e}")
        return []


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Starting Aviation Dashboard Server")
    logger.info(f"NASA API Key: {'DEMO_KEY' if NASA_API_KEY == 'DEMO_KEY' else '****' + NASA_API_KEY[-4:]}")
    logger.info(f"Home: {HOME_LAT}, {HOME_LON}")
    logger.info(f"Dinos loaded: {len(DINO_FACTS)}")
    logger.info(f"Debug mode: {DEBUG}")
    logger.info("=" * 50)

    # With the debug reloader the module runs twice — start the loop only in the serving process
    if not DEBUG or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        DISPLAY.start()

    app.run(host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "5000")), debug=DEBUG)
