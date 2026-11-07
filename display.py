"""Night mode, screen-off mode and Raspberry Pi backlight control.

The Touch Display 2 exposes its backlight at /sys/class/backlight/<name>/brightness.
Writing there needs permission — run scripts/install_backlight.sh once on the Pi.
Without it everything still works; the frontend then dims with a black overlay instead.
"""
import glob
import logging
import os
import re
import threading
from datetime import datetime, timedelta

import pytz

logger = logging.getLogger(__name__)
TZ = pytz.timezone("Europe/Berlin")

DISPLAY_DEFAULTS = {
    "display_mode": "auto",       # auto | day | night
    "night_schedule": "sun",      # sun (sunset → sunrise) | fixed (night_from → night_to)
    "night_from": "22:00",
    "night_to": "06:30",
    "night_brightness": 20,       # percent
    "day_brightness": 100,        # percent
    "wake_mode": "sunrise",       # sunrise | time | never — when "screen off" ends by itself
    "wake_time": "07:00",
    "screen_off_until": None,     # None = screen on, "never" or an ISO timestamp
}

_HM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _minutes(hm):
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


class Backlight:
    """Writes the panel brightness via sysfs, if present and writable."""

    def __init__(self):
        dirs = sorted(glob.glob("/sys/class/backlight/*"))
        self.path = dirs[0] if dirs else None
        self.max = 0
        self._last = None
        if self.path:
            try:
                with open(os.path.join(self.path, "max_brightness")) as f:
                    self.max = int(f.read().strip())
            except (OSError, ValueError) as e:
                logger.warning(f"Backlight max_brightness unreadable: {e}")
        self.available = bool(self.max) and os.access(os.path.join(self.path, "brightness"), os.W_OK)
        if self.path and not self.available:
            logger.warning(f"Backlight {self.path} found but not writable — run scripts/install_backlight.sh")
        elif self.available:
            logger.info(f"Backlight control: {self.path} (max {self.max})")

    def set_percent(self, percent):
        if not self.available:
            return False
        # Never 0: in screen-off mode the wake button must stay (barely) visible
        value = max(1, round(self.max * percent / 100))
        if value == self._last:
            return True
        try:
            with open(os.path.join(self.path, "brightness"), "w") as f:
                f.write(str(value))
            self._last = value
            return True
        except OSError as e:
            logger.error(f"Backlight write failed: {e}")
            return False


class DisplayController:
    def __init__(self, settings, save_settings, sun_times):
        self.settings = settings            # shared APP_SETTINGS dict
        self.save_settings = save_settings
        self.sun_times = sun_times          # () -> {"sunrise": "HH:MM", "sunset": "HH:MM"}
        self.backlight = Backlight()
        self.lock = threading.Lock()
        for key, value in DISPLAY_DEFAULTS.items():
            self.settings.setdefault(key, value)

    # --- time helpers ---
    def _now(self):
        return datetime.now(TZ)

    def _sun(self):
        """Sunset/sunrise as HH:MM, or None if the sun API is unavailable"""
        try:
            sun = self.sun_times()
            if _HM.match(sun.get("sunrise", "")) and _HM.match(sun.get("sunset", "")):
                return sun
        except Exception as e:
            logger.warning(f"Sun times unavailable: {e}")
        return None

    def night_window(self):
        s = self.settings
        if s["night_schedule"] == "sun":
            sun = self._sun()
            if sun:
                return sun["sunset"], sun["sunrise"]
        return s["night_from"], s["night_to"]

    def _next_at(self, hm, now):
        h, m = map(int, hm.split(":"))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        return target if target > now else target + timedelta(days=1)

    # --- state ---
    def is_night(self, now=None):
        mode = self.settings["display_mode"]
        if mode == "day":
            return False
        if mode == "night":
            return True
        now = now or self._now()
        start, end = map(_minutes, self.night_window())
        current = now.hour * 60 + now.minute
        if start > end:                       # crosses midnight, e.g. 16:47 → 07:31
            return current >= start or current < end
        return start <= current < end

    def is_off(self, now=None):
        until = self.settings.get("screen_off_until")
        if not until:
            return False
        if until == "never":
            return True
        try:
            if (now or self._now()) >= datetime.fromisoformat(until):
                logger.info("Screen-off period ended — waking display")
                self.screen_on()
                return False
        except ValueError:
            self.screen_on()
            return False
        return True

    def state(self):
        now = self._now()
        off = self.is_off(now)
        night = self.is_night(now)
        start, end = self.night_window()
        s = self.settings
        return {
            "screen_off": off,
            "screen_off_until": s.get("screen_off_until"),
            "night": night,
            "backlight": self.backlight.available,
            "night_window": {"from": start, "to": end},
            "settings": {k: s[k] for k in DISPLAY_DEFAULTS if k != "screen_off_until"},
        }

    def apply(self):
        """Push the current state to the backlight (called periodically and after changes)"""
        with self.lock:
            st = self.state()
            if st["screen_off"]:
                pct = 0
            elif st["night"]:
                pct = self.settings["night_brightness"]
            else:
                pct = self.settings["day_brightness"]
            self.backlight.set_percent(pct)
            return st

    # --- actions ---
    def screen_off(self):
        s, now = self.settings, self._now()
        if s["wake_mode"] == "never":
            until = "never"
        else:
            sun = self._sun() if s["wake_mode"] == "sunrise" else None
            hm = sun["sunrise"] if sun else s["wake_time"]
            until = self._next_at(hm, now).isoformat()
        s["screen_off_until"] = until
        self.save_settings(s)
        logger.info(f"Screen off until {until}")
        return self.apply()

    def screen_on(self):
        self.settings["screen_off_until"] = None
        self.save_settings(self.settings)

    def update(self, data):
        """Validate and store display settings; returns an error string or None"""
        s = self.settings
        choices = {
            "display_mode": ("auto", "day", "night"),
            "night_schedule": ("sun", "fixed"),
            "wake_mode": ("sunrise", "time", "never"),
        }
        for key, allowed in choices.items():
            if key in data:
                if data[key] not in allowed:
                    return f"{key} muss eins von {', '.join(allowed)} sein"
                s[key] = data[key]
        for key in ("night_from", "night_to", "wake_time"):
            if key in data:
                if not _HM.match(str(data[key])):
                    return f"{key} muss HH:MM sein"
                s[key] = data[key]
        for key in ("night_brightness", "day_brightness"):
            if key in data:
                try:
                    value = int(data[key])
                except (TypeError, ValueError):
                    return f"{key} muss eine Zahl sein"
                s[key] = min(100, max(5, value))
        self.save_settings(s)
        return None

    def start(self, interval=30):
        """Background loop: night/day transitions and wake-up happen even if no page polls"""
        def loop():
            while True:
                try:
                    self.apply()
                except Exception as e:
                    logger.error(f"Display loop error: {e}")
                threading.Event().wait(interval)

        threading.Thread(target=loop, name="display-loop", daemon=True).start()
        logger.info("Display controller started")
