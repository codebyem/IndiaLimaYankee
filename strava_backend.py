# Strava Integration for Aviation Dashboard
# Add this to your app_improved.py

import httpx
from datetime import datetime, date, timedelta
import os
from functools import wraps

# === STRAVA CONFIGURATION ===
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID", "")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN", "")
STRAVA_ACCESS_TOKEN = None
STRAVA_TOKEN_EXPIRY = 0

logger.info(f"Strava Client ID: {STRAVA_CLIENT_ID[:10] if STRAVA_CLIENT_ID else 'NOT SET'}...")


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
    
    # Refresh if token is expired or will expire in 5 minutes
    if not STRAVA_ACCESS_TOKEN or current_time >= (STRAVA_TOKEN_EXPIRY - 300):
        return refresh_strava_token()
    
    return STRAVA_ACCESS_TOKEN


@timed_cache(seconds=1800)  # Cache for 30 minutes
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
        
        # Get last 30 activities
        params = {"per_page": 30}
        
        resp = httpx.get(url, headers=headers, params=params, timeout=10)
        
        if resp.status_code == 200:
            activities = resp.json()
            logger.info(f"Fetched {len(activities)} Strava activities")
            return activities
        elif resp.status_code == 401:
            # Token might be invalid, try refreshing
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
    
    pace_per_km = (seconds_per_meter * 1000) / 60  # minutes per km
    minutes = int(pace_per_km)
    seconds = int((pace_per_km - minutes) * 60)
    
    return f"{minutes}:{seconds:02d}"


def calculate_streak(activities):
    """Calculate current activity streak in days"""
    if not activities:
        return 0
    
    # Sort activities by date (newest first)
    sorted_activities = sorted(activities, 
                               key=lambda x: datetime.fromisoformat(x['start_date'].replace('Z', '+00:00')), 
                               reverse=True)
    
    today = datetime.now().date()
    streak = 0
    current_check_date = today
    
    for activity in sorted_activities:
        activity_date = datetime.fromisoformat(activity['start_date'].replace('Z', '+00:00')).date()
        
        if activity_date == current_check_date:
            streak += 1
            current_check_date -= timedelta(days=1)
        elif activity_date < current_check_date:
            # Gap in activities
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
    
    # Latest activity
    latest = activities[0]
    
    # Calculate streak
    streak = calculate_streak(activities)
    
    # This month's distance
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    month_activities = [a for a in activities 
                       if datetime.fromisoformat(a['start_date'].replace('Z', '+00:00')) >= month_start]
    
    month_distance = sum(a['distance'] for a in month_activities) / 1000  # km
    
    # Weekly count
    week_ago = now - timedelta(days=7)
    week_activities = [a for a in activities 
                      if datetime.fromisoformat(a['start_date'].replace('Z', '+00:00')) >= week_ago]
    
    week_count = len(week_activities)
    
    # Decide what to display (rotate or choose most impressive)
    display_stat = f"{month_distance:.1f}"
    display_label = "KM MONAT"
    
    # Alternative: show streak if it's impressive
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
    
    now = datetime.now()
    
    # Latest activity details
    latest = activities[0]
    distance_km = latest['distance'] / 1000
    moving_time = latest['moving_time']
    
    latest_data = {
        "distance": f"{distance_km:.1f}",
        "time": format_time(moving_time),
        "pace": format_pace(moving_time, latest['distance']),
        "elevation": round(latest.get('total_elevation_gain', 0), 0)
    }
    
    # Weekly stats by type
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
    
    # Activity heatmap (last 7 days)
    heatmap = []
    for i in range(7):
        check_date = (now - timedelta(days=6-i)).date()
        has_activity = any(
            datetime.fromisoformat(a['start_date'].replace('Z', '+00:00')).date() == check_date
            for a in activities
        )
        heatmap.append(has_activity)
    
    # Personal records
    runs = [a for a in activities if a['type'] == 'Run']
    
    longest_run = max((a['distance'] for a in runs), default=0) / 1000 if runs else 0
    
    # Fastest 5K (within 4.5-5.5km range)
    five_k_runs = [a for a in runs if 4500 <= a['distance'] <= 5500]
    fastest_5k_time = min((a['moving_time'] for a in five_k_runs), default=None) if five_k_runs else None
    
    max_elevation = max((a.get('total_elevation_gain', 0) for a in activities), default=0)
    
    records = {
        "longest_run": f"{longest_run:.1f} km" if longest_run > 0 else "--",
        "fastest_5k": format_time(fastest_5k_time) if fastest_5k_time else "--",
        "max_elevation": f"{round(max_elevation)}m" if max_elevation > 0 else "--"
    }
    
    # Month distance
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


# === ROUTES ===

@app.route("/strava")
def strava_page():
    """Strava statistics page"""
    activities = fetch_strava_activities()
    strava_data = parse_strava_data(activities) if activities else None
    return render_template("strava.html", strava=strava_data)


@app.route("/api/strava")
def api_strava():
    """Strava API endpoint - simple stats for dashboard"""
    activities = fetch_strava_activities()
    
    if not activities:
        return jsonify({"error": "No Strava data available"})
    
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


# Update the home route to include Strava
@app.route("/")
def home():
    """Main dashboard page"""
    airport = APP_SETTINGS.get("airport_icao", "EDLP")
    
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
