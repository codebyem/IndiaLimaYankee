#!/usr/bin/env python3
"""
Strava Debug Script - Prüft Konfiguration und API
"""

import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("STRAVA CONFIGURATION CHECK")
print("=" * 60)
print()

# Check environment variables
client_id = os.getenv("STRAVA_CLIENT_ID", "")
client_secret = os.getenv("STRAVA_CLIENT_SECRET", "")
refresh_token = os.getenv("STRAVA_REFRESH_TOKEN", "")

print("1. Environment Variables:")
print("-" * 60)
print(f"STRAVA_CLIENT_ID:     {'✅ Set' if client_id else '❌ NOT SET'}")
if client_id:
    print(f"                      {client_id[:10]}...")

print(f"STRAVA_CLIENT_SECRET: {'✅ Set' if client_secret else '❌ NOT SET'}")
if client_secret:
    print(f"                      {client_secret[:10]}...")

print(f"STRAVA_REFRESH_TOKEN: {'✅ Set' if refresh_token else '❌ NOT SET'}")
if refresh_token:
    print(f"                      {refresh_token[:10]}...")

print()

if not (client_id and client_secret and refresh_token):
    print("❌ PROBLEM: Strava ist nicht vollständig konfiguriert!")
    print()
    print("LÖSUNG:")
    print("1. Führe setup_strava.py aus:")
    print("   python setup_strava.py")
    print()
    print("2. ODER füge manuell zu .env hinzu:")
    print("   STRAVA_CLIENT_ID=deine_id")
    print("   STRAVA_CLIENT_SECRET=dein_secret")
    print("   STRAVA_REFRESH_TOKEN=dein_token")
    print()
    exit(1)

print("✅ Alle Tokens sind konfiguriert!")
print()

# Test token refresh
print("2. Testing Token Refresh:")
print("-" * 60)

try:
    import httpx

    url = "https://www.strava.com/oauth/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }

    print("Sende Token-Refresh-Anfrage...")
    resp = httpx.post(url, data=data, timeout=10)

    if resp.status_code == 200:
        token_data = resp.json()
        access_token = token_data['access_token']

        print("✅ Token erfolgreich refreshed!")
        print(f"   Access Token: {access_token[:10]}...")
        print()

        # Test activities API
        print("3. Testing Activities API:")
        print("-" * 60)

        activities_url = "https://www.strava.com/api/v3/athlete/activities"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"per_page": 5}

        print("Lade letzte 5 Aktivitäten...")
        act_resp = httpx.get(activities_url, headers=headers, params=params, timeout=10)

        if act_resp.status_code == 200:
            activities = act_resp.json()

            print(f"✅ {len(activities)} Aktivitäten gefunden!")
            print()

            if len(activities) > 0:
                print("Letzte Aktivität:")
                latest = activities[0]
                print(f"   Name: {latest['name']}")
                print(f"   Type: {latest['type']}")
                print(f"   Distance: {latest['distance'] / 1000:.1f} km")
                print(f"   Date: {latest['start_date']}")
                print()
            else:
                print("⚠️  Keine Aktivitäten gefunden.")
                print("    Stelle sicher, dass dein Strava-Account Aktivitäten hat.")
                print()

            print("=" * 60)
            print("✅ ALLES FUNKTIONIERT!")
            print("=" * 60)
            print()
            print("Dein Dashboard sollte jetzt Strava-Daten anzeigen.")
            print("Falls nicht, starte den Server neu:")
            print("  python app_complete_with_strava.py")

        else:
            print(f"❌ Activities API Error: {act_resp.status_code}")
            print(f"   Response: {act_resp.text}")

    else:
        print(f"❌ Token Refresh failed: {resp.status_code}")
        print(f"   Response: {resp.text}")
        print()
        print("MÖGLICHE PROBLEME:")
        print("- Client ID oder Secret falsch")
        print("- Refresh Token ist abgelaufen oder ungültig")
        print()
        print("LÖSUNG: Führe setup_strava.py erneut aus")

except ImportError:
    print("❌ httpx nicht installiert!")
    print("   pip install httpx")
except Exception as e:
    print(f"❌ Fehler: {e}")
    import traceback

    traceback.print_exc()