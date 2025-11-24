from flask import Flask, render_template, jsonify, request
import httpx
from datetime import datetime, date, timedelta
import json
import os
import logging
from functools import lru_cache, wraps
from time import time

# === LOGGING SETUP ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('aviation_dashboard.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# === ENVIRONMENT VARIABLES ===
NASA_API_KEY = os.getenv("NASA_API_KEY", "ZXJWkvMvUtYeyDjAVbEjlxR8wkM7tWqgUkinyDwg")
AVWX_TOKEN = os.getenv("AVWX_TOKEN", "0z3Owy4pPyW3RMKfkdRghFWcZdetlrikqOg6vXgx7VQ")

# Strava Configuration
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID", "")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN", "")
STRAVA_ACCESS_TOKEN = None
STRAVA_TOKEN_EXPIRY = 0

# Home Coordinates
HOME_LAT = float(os.getenv("HOME_LAT", "51.963"))
HOME_LON = float(os.getenv("HOME_LON", "8.534"))

# Files
DINO_DATA_FILE = os.getenv("DINO_DATA_FILE", "dinos.json")
SETTINGS_FILE = os.getenv("SETTINGS_FILE", "settings.json")

logger.info(f"Starting Aviation Dashboard with coordinates: {HOME_LAT}, {HOME_LON}")
if STRAVA_CLIENT_ID:
    logger.info(f"Strava Client ID configured: {STRAVA_CLIENT_ID[:10]}...")
else:
    logger.warning("Strava not configured - widget will show placeholder")


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
            logger.info(f"Settings loaded: {settings}")
            return settings
    except FileNotFoundError:
        logger.warning(f"{SETTINGS_FILE} not found, creating default settings")
        default_settings = {"airport_icao": "EDLP"}
        save_settings(default_settings)
        return default_settings
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return {"airport_icao": "EDLP"}


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


# === STRAVA FUNCTIONS ===

def refresh_strava_token():
    """Refresh Strava access token using refresh token"""
    global STRAVA_ACCESS_TOKEN, STRAVA_TOKEN_EXPIRY

    if not STRAVA_REFRESH_TOKEN:
        logger.error("No Strava refresh token configured")
        return None

    try:
        logger.info("Refreshing Strava access token")
        url = "https://www.strava.com/oauth/token"

        data = {
            "client_id": STRAVA_CLIENT_ID,
            "client_secret": STRAVA_CLIENT_SECRET,
            "refresh_token": STRAVA_REFRESH_TOKEN,
            "grant_type": "refresh_token"
        }

        resp = httpx.post(url, data=data, timeout=10)

        if resp.status_code == 200:
            token_data = resp.json()
            STRAVA_ACCESS_TOKEN = token_data['access_token']
            STRAVA_TOKEN_EXPIRY = token_data['expires_at']
            logger.info("Strava token refreshed successfully")
            return STRAVA_ACCESS_TOKEN
        else:
            logger.error(f"Token refresh failed: {resp.status_code}")
            return None
    except Exception as e:
        logger.error(f"Strava token refresh error: {e}")
        return None


def get_strava_token():
    """Get valid Strava access token, refresh if needed"""
    global STRAVA_ACCESS_TOKEN, STRAVA_TOKEN_EXPIRY

    current_time = datetime.now().timestamp()

    if not STRAVA_ACCESS_TOKEN or current_time >= (STRAVA_TOKEN_EXPIRY - 300):
        return refresh_strava_token()

    return STRAVA_ACCESS_TOKEN


@timed_cache(seconds=1800)
def fetch_strava_activities():
    """Fetch recent Strava activities"""
    token = get_strava_token()

    if not token:
        logger.error("No valid Strava token available")
        return None

    try:
        logger.info("Fetching Strava activities")
        url = "https://www.strava.com/api/v3/athlete/activities"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"per_page": 30}

        resp = httpx.get(url, headers=headers, params=params, timeout=10)

        if resp.status_code == 200:
            activities = resp.json()
            logger.info(f"Fetched {len(activities)} Strava activities")
            return activities
        elif resp.status_code == 401:
            logger.warning("Strava 401, refreshing token")
            token = refresh_strava_token()
            if token:
                headers = {"Authorization": f"Bearer {token}"}
                resp = httpx.get(url, headers=headers, params=params, timeout=10)
                if resp.status_code == 200:
                    return resp.json()

        logger.error(f"Strava API error: {resp.status_code}")
        return None

    except Exception as e:
        logger.error(f"Strava fetch error: {e}")
        return None


def format_time(seconds):
    """Format seconds to HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def format_pace(seconds_per_meter, distance_meters):
    """Calculate pace in min/km"""
    if distance_meters == 0:
        return "--:--"

    pace_per_km = (seconds_per_meter * 1000) / 60
    minutes = int(pace_per_km)
    seconds = int((pace_per_km - minutes) * 60)

    return f"{minutes}:{seconds:02d}"


def calculate_streak(activities):
    """Calculate current activity streak in days"""
    if not activities:
        return 0

    sorted_activities = sorted(activities,
                               key=lambda x: datetime.fromisoformat(x['start_date'].replace('Z', '+00:00')),
                               reverse=True)

    # Use timezone-aware date
    import pytz
    tz = pytz.timezone('Europe/Berlin')
    today = datetime.now(tz).date()
    streak = 0
    current_check_date = today

    for activity in sorted_activities:
        activity_date = datetime.fromisoformat(activity['start_date'].replace('Z', '+00:00')).date()

        if activity_date == current_check_date:
            streak += 1
            current_check_date -= timedelta(days=1)
        elif activity_date < current_check_date:
            break

    return streak


def parse_strava_data(activities):
    """Parse Strava activities into dashboard-ready data"""
    if not activities or len(activities) == 0:
        return {
            "display_stat": "--",
            "display_label": "Keine Daten",
            "streak": 0
        }

    streak = calculate_streak(activities)

    # Use timezone-aware datetime
    import pytz
    tz = pytz.timezone('Europe/Berlin')
    now = datetime.now(tz)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    month_activities = [a for a in activities
                        if datetime.fromisoformat(a['start_date'].replace('Z', '+00:00')) >= month_start]

    month_distance = sum(a['distance'] for a in month_activities) / 1000

    week_ago = now - timedelta(days=7)
    week_activities = [a for a in activities
                       if datetime.fromisoformat(a['start_date'].replace('Z', '+00:00')) >= week_ago]

    week_count = len(week_activities)

    display_stat = f"{month_distance:.1f}"
    display_label = "KM MONAT"

    if streak >= 7:
        display_stat = str(streak)
        display_label = "DAY STREAK"

    return {
        "display_stat": display_stat,
        "display_label": display_label,
        "streak": streak,
        "month_distance": f"{month_distance:.1f}",
        "week_count": week_count
    }


def parse_strava_detailed(activities):
    """Parse detailed Strava statistics"""
    if not activities or len(activities) == 0:
        return {"error": "No activities"}

    # Use timezone-aware datetime
    import pytz
    tz = pytz.timezone('Europe/Berlin')
    now = datetime.now(tz)

    latest = activities[0]
    distance_km = latest['distance'] / 1000
    moving_time = latest['moving_time']

    latest_data = {
        "distance": f"{distance_km:.1f}",
        "time": format_time(moving_time),
        "pace": format_pace(moving_time, latest['distance']),
        "elevation": round(latest.get('total_elevation_gain', 0), 0)
    }

    week_ago = now - timedelta(days=7)
    week_activities = [a for a in activities
                       if datetime.fromisoformat(a['start_date'].replace('Z', '+00:00')) >= week_ago]

    run_distance = sum(a['distance'] for a in week_activities if a['type'] == 'Run') / 1000
    ride_distance = sum(a['distance'] for a in week_activities if a['type'] == 'Ride') / 1000
    swim_distance = sum(a['distance'] for a in week_activities if a['type'] == 'Swim') / 1000

    weekly_data = {
        "run": f"{run_distance:.1f}",
        "ride": f"{ride_distance:.1f}",
        "swim": f"{swim_distance:.1f}",
        "total": f"{(run_distance + ride_distance + swim_distance):.1f}"
    }

    heatmap = []
    for i in range(7):
        check_date = (now - timedelta(days=6 - i)).date()
        has_activity = any(
            datetime.fromisoformat(a['start_date'].replace('Z', '+00:00')).date() == check_date
            for a in activities
        )
        heatmap.append(has_activity)

    runs = [a for a in activities if a['type'] == 'Run']
    longest_run = max((a['distance'] for a in runs), default=0) / 1000 if runs else 0

    five_k_runs = [a for a in runs if 4500 <= a['distance'] <= 5500]
    fastest_5k_time = min((a['moving_time'] for a in five_k_runs), default=None) if five_k_runs else None

    max_elevation = max((a.get('total_elevation_gain', 0) for a in activities), default=0)

    records = {
        "longest_run": f"{longest_run:.1f} km" if longest_run > 0 else "--",
        "fastest_5k": format_time(fastest_5k_time) if fastest_5k_time else "--",
        "max_elevation": f"{round(max_elevation)}m" if max_elevation > 0 else "--"
    }

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_activities = [a for a in activities
                        if datetime.fromisoformat(a['start_date'].replace('Z', '+00:00')) >= month_start]
    month_distance = sum(a['distance'] for a in month_activities) / 1000

    return {
        "streak": calculate_streak(activities),
        "month_distance": f"{month_distance:.1f}",
        "week_count": len(week_activities),
        "latest": latest_data,
        "weekly": weekly_data,
        "heatmap": heatmap,
        "records": records
    }


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
    except:
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
        url = f"https://api.nasa.gov/EPIC/api/natural?api_key={NASA_API_KEY}"
        resp = httpx.get(url, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                for item in data[:3]:
                    try:
                        date_str = item["date"]
                        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        image_url = f"https://epic.gsfc.nasa.gov/archive/natural/{dt.strftime('%Y/%m/%d')}/jpg/{item['image']}.jpg"

                        test = httpx.head(image_url, timeout=3)
                        if test.status_code == 200:
                            logger.info(f"NASA EPIC image found: {date_str}")
                            return {
                                "caption": item.get("caption", "Earth from Space"),
                                "url": image_url,
                                "date": date_str
                            }
                    except Exception as e:
                        logger.warning(f"EPIC image validation failed: {e}")
                        continue
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


def fetch_notams(station="EDLP"):
    """Fetch NOTAMs - mock data"""
    logger.debug(f"Fetching NOTAMs for {station}")
    return {
        "notams": [
            {"id": "A0123/25", "message": "RWY 06/24 CLSD FOR MAINTENANCE"},
            {"id": "A0124/25", "message": "TWR FREQ CHANGED TO 119.75 MHZ"}
        ]
    }


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


# === ROUTES ===

@app.route("/")
def home():
    """Main dashboard page"""
    airport = APP_SETTINGS.get("airport_icao", "EDLP")
    logger.info(f"Loading dashboard for airport: {airport}")

    # Fetch Strava data
    activities = fetch_strava_activities()
    strava_data = parse_strava_data(activities) if activities else None

    return render_template(
        "dashboard.html",
        metar=fetch_metar(airport),
        dino=get_daily_dino(),
        nasa_apod=fetch_nasa_apod(),
        nasa_epic=fetch_nasa_epic(),
        strava=strava_data
    )


@app.route("/dino")
def dino_page():
    """Dino detail page"""
    dino = get_daily_dino()
    logger.info(f"Loading dino page: {dino['name']}")
    return render_template("dino.html", dino=dino)


@app.route("/strava")
def strava_page():
    """Strava statistics page"""
    activities = fetch_strava_activities()
    strava_data = parse_strava_data(activities) if activities else None
    return render_template("strava.html", strava=strava_data)


@app.route("/settings")
def settings_page():
    """Settings page"""
    return render_template("settings.html", current_airport=APP_SETTINGS.get("airport_icao", "EDLP"))


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
            airport_icao = data.get('airport_icao', '').strip().upper()

            if len(airport_icao) != 4:
                logger.warning(f"Invalid ICAO length: {airport_icao}")
                return jsonify({"error": "ICAO must be 4 characters"}), 400

            APP_SETTINGS['airport_icao'] = airport_icao

            if save_settings(APP_SETTINGS):
                fetch_metar.clear_cache()
                fetch_taf.clear_cache()
                logger.info(f"Airport changed to: {airport_icao}, cache cleared")
                return jsonify({"success": True, "airport_icao": airport_icao})
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


@app.route("/api/refresh")
def api_refresh():
    """Refresh all data and clear caches"""
    logger.info("Manual refresh requested - clearing all caches")

    fetch_metar.clear_cache()
    fetch_nasa_apod.clear_cache()
    fetch_nasa_epic.clear_cache()
    fetch_taf.clear_cache()
    calculate_sun_moon_times.clear_cache()
    fetch_strava_activities.clear_cache()

    airport = APP_SETTINGS.get("airport_icao", "EDLP")
    activities = fetch_strava_activities()

    return jsonify({
        "metar": fetch_metar(airport),
        "dino": get_daily_dino(),
        "nasa_apod": fetch_nasa_apod(),
        "nasa_epic": fetch_nasa_epic(),
        "strava": parse_strava_data(activities) if activities else None
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


@app.route("/api/notams")
def api_notams():
    """NOTAMs API"""
    airport = APP_SETTINGS.get("airport_icao", "EDLP")
    return jsonify(fetch_notams(airport))


@app.route("/api/dino/<dino_name>")
def api_dino_details(dino_name):
    """Dino details API"""
    return jsonify(get_dino_details(dino_name))


@app.route("/api/strava")
def api_strava():
    """Strava API endpoint - simple stats for dashboard"""
    activities = fetch_strava_activities()

    if not activities:
        return jsonify(
            {"error": "No Strava data available", "display_stat": "--", "display_label": "Keine Daten", "streak": 0})

    data = parse_strava_data(activities)
    return jsonify(data)


@app.route("/api/strava/detailed")
def api_strava_detailed():
    """Strava API endpoint - detailed stats for stats page"""
    activities = fetch_strava_activities()

    if not activities:
        return jsonify({"error": "No Strava data available"})

    data = parse_strava_detailed(activities)
    return jsonify(data)


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

    if STRAVA_REFRESH_TOKEN:
        try:
            token = get_strava_token()
            health["services"]["strava"] = "ok" if token else "error"
        except Exception as e:
            health["services"]["strava"] = "error"
            logger.error(f"Strava health check failed: {e}")
    else:
        health["services"]["strava"] = "not_configured"

    health["status"] = "ok" if all(
        v == "ok" for v in health["services"].values() if v != "not_configured") else "degraded"

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
            "strava": 1800000
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
            "sunmoon": "1 hour",
            "strava": "30 minutes"
        },
        "features": {
            "strava_enabled": bool(STRAVA_REFRESH_TOKEN)
        }
    })


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Starting Aviation Dashboard Server")
    logger.info(f"NASA API Key: {'*' * (len(NASA_API_KEY) - 4) + NASA_API_KEY[-4:]}")
    logger.info(f"AVWX Token: {'*' * (len(AVWX_TOKEN) - 4) + AVWX_TOKEN[-4:]}")
    logger.info(f"Home: {HOME_LAT}, {HOME_LON}")
    logger.info(f"Dinos loaded: {len(DINO_FACTS)}")

    if STRAVA_REFRESH_TOKEN:
        logger.info(f"Strava: ENABLED")
    else:
        logger.warning("Strava: NOT CONFIGURED")

    logger.info("=" * 50)

    os.makedirs("templates", exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)