#!/usr/bin/env python3
"""
Strava OAuth Setup Script
Hilft dir, die initialen Strava API Tokens zu bekommen
"""

import httpx
import webbrowser
from urllib.parse import urlencode

print("=" * 60)
print("STRAVA API SETUP - AVIATION DASHBOARD")
print("=" * 60)
print()

# Step 1: Get Client ID and Secret
print("SCHRITT 1: Strava App erstellen")
print("-" * 60)
print("1. Gehe zu: https://www.strava.com/settings/api")
print("2. Erstelle eine neue App mit folgenden Einstellungen:")
print("   - Application Name: Aviation Dashboard")
print("   - Category: Visualizer")
print("   - Website: http://localhost")
print("   - Authorization Callback Domain: localhost")
print()

client_id = input("Gib deine Client ID ein: ").strip()
client_secret = input("Gib dein Client Secret ein: ").strip()

if not client_id or not client_secret:
    print("❌ Client ID und Secret sind erforderlich!")
    exit(1)

print("\n✅ Client ID und Secret gespeichert!")
print()

# Step 2: Authorization
print("SCHRITT 2: Authorization Code holen")
print("-" * 60)

# Build authorization URL
params = {
    "client_id": client_id,
    "redirect_uri": "http://localhost",
    "response_type": "code",
    "scope": "activity:read_all"
}

auth_url = f"https://www.strava.com/oauth/authorize?{urlencode(params)}"

print("Öffne diese URL in deinem Browser:")
print(auth_url)
print()

# Try to open browser automatically
try:
    webbrowser.open(auth_url)
    print("✅ Browser geöffnet!")
except:
    print("⚠️  Browser konnte nicht automatisch geöffnet werden.")
    print("   Kopiere die URL manuell in deinen Browser.")

print()
print("Du wirst zu Strava weitergeleitet.")
print("Klicke auf 'Authorize' um Zugriff zu gewähren.")
print()
print("Nach der Autorisierung wirst du zu einer URL weitergeleitet, die so aussieht:")
print("http://localhost/?state=&code=XXXXXXXXXXXXXX&scope=read,activity:read_all")
print()

authorization_code = input("Kopiere den CODE aus der URL und füge ihn hier ein: ").strip()

if not authorization_code:
    print("❌ Authorization Code ist erforderlich!")
    exit(1)

print("\n✅ Authorization Code erhalten!")
print()

# Step 3: Exchange for tokens
print("SCHRITT 3: Tokens holen")
print("-" * 60)

try:
    token_url = "https://www.strava.com/oauth/token"
    
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": authorization_code,
        "grant_type": "authorization_code"
    }
    
    print("Sende Anfrage an Strava...")
    resp = httpx.post(token_url, data=data, timeout=30)
    
    if resp.status_code == 200:
        token_data = resp.json()
        
        access_token = token_data['access_token']
        refresh_token = token_data['refresh_token']
        expires_at = token_data['expires_at']
        
        print("\n" + "=" * 60)
        print("✅ ERFOLG! Tokens erhalten!")
        print("=" * 60)
        print()
        
        # Get athlete info
        athlete_url = "https://www.strava.com/api/v3/athlete"
        headers = {"Authorization": f"Bearer {access_token}"}
        athlete_resp = httpx.get(athlete_url, headers=headers, timeout=10)
        
        if athlete_resp.status_code == 200:
            athlete = athlete_resp.json()
            print(f"👤 Athlet: {athlete['firstname']} {athlete['lastname']}")
            print(f"   Username: {athlete['username']}")
            print()
        
        print("Füge diese Werte zu deiner .env Datei hinzu:")
        print("-" * 60)
        print(f"STRAVA_CLIENT_ID={client_id}")
        print(f"STRAVA_CLIENT_SECRET={client_secret}")
        print(f"STRAVA_REFRESH_TOKEN={refresh_token}")
        print("-" * 60)
        print()
        
        # Write to .env file
        try:
            with open('.env', 'a') as f:
                f.write("\n# Strava Configuration\n")
                f.write(f"STRAVA_CLIENT_ID={client_id}\n")
                f.write(f"STRAVA_CLIENT_SECRET={client_secret}\n")
                f.write(f"STRAVA_REFRESH_TOKEN={refresh_token}\n")
            
            print("✅ Werte wurden automatisch zu .env hinzugefügt!")
        except Exception as e:
            print(f"⚠️  .env konnte nicht geschrieben werden: {e}")
            print("   Füge die Werte manuell hinzu.")
        
        print()
        print("=" * 60)
        print("🎉 SETUP ABGESCHLOSSEN!")
        print("=" * 60)
        print()
        print("Du kannst jetzt deinen Dashboard-Server starten:")
        print("  python app_improved.py")
        print()
        print("WICHTIG: Der Refresh Token läuft NICHT ab!")
        print("         Bewahre ihn sicher auf.")
        
    else:
        print(f"❌ Fehler beim Token-Austausch: {resp.status_code}")
        print(f"   Response: {resp.text}")
        exit(1)

except Exception as e:
    print(f"❌ Fehler: {e}")
    exit(1)
