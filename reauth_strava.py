#!/usr/bin/env python3
"""
Strava Re-Authorization - Holt neue Tokens mit korrekten Scopes
"""

import httpx
import webbrowser
import os
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("STRAVA RE-AUTHORIZATION")
print("=" * 60)
print()

client_id = os.getenv("STRAVA_CLIENT_ID", "")
client_secret = os.getenv("STRAVA_CLIENT_SECRET", "")

if not client_id or not client_secret:
    print("❌ Client ID oder Secret nicht gefunden in .env")
    exit(1)

print(f"Client ID: {client_id}")
print()

print("PROBLEM:")
print("Deine aktuellen Tokens haben nicht die richtigen Berechtigungen.")
print("Wir brauchen 'activity:read_all' Scope.")
print()

# Build authorization URL with correct scope
params = {
    "client_id": client_id,
    "redirect_uri": "http://localhost",
    "response_type": "code",
    "scope": "activity:read_all"  # ← WICHTIG!
}

auth_url = f"https://www.strava.com/oauth/authorize?{urlencode(params)}"

print("SCHRITT 1: Authorization")
print("-" * 60)
print("Öffne diese URL in deinem Browser:")
print(auth_url)
print()

# Try to open browser
try:
    webbrowser.open(auth_url)
    print("✅ Browser geöffnet!")
except:
    print("⚠️  Browser konnte nicht geöffnet werden.")
    print("   Kopiere die URL manuell.")

print()
print("WICHTIG: Stelle sicher, dass diese Box angehakt ist:")
print("  ✅ View data about your activities")
print()
print("Klicke dann auf 'Authorize'")
print()

# Get authorization code
authorization_code = input("Kopiere den CODE aus der URL und füge ihn hier ein: ").strip()

if not authorization_code:
    print("❌ Kein Code eingegeben!")
    exit(1)

print()
print("SCHRITT 2: Neue Tokens holen")
print("-" * 60)

try:
    token_url = "https://www.strava.com/oauth/token"

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": authorization_code,
        "grant_type": "authorization_code"
    }

    print("Sende Anfrage...")
    resp = httpx.post(token_url, data=data, timeout=30)

    if resp.status_code == 200:
        token_data = resp.json()

        access_token = token_data['access_token']
        refresh_token = token_data['refresh_token']

        print("✅ Neue Tokens erhalten!")
        print()

        # Test the new token
        print("SCHRITT 3: Token testen")
        print("-" * 60)

        test_url = "https://www.strava.com/api/v3/athlete/activities"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"per_page": 1}

        test_resp = httpx.get(test_url, headers=headers, params=params, timeout=10)

        if test_resp.status_code == 200:
            activities = test_resp.json()

            print("✅ Token funktioniert!")
            print(f"   {len(activities)} Aktivität(en) gefunden")
            print()

            # Update .env file
            print("SCHRITT 4: .env aktualisieren")
            print("-" * 60)

            # Read current .env
            env_lines = []
            token_updated = False

            try:
                with open('.env', 'r') as f:
                    env_lines = f.readlines()

                # Update refresh token line
                for i, line in enumerate(env_lines):
                    if line.startswith('STRAVA_REFRESH_TOKEN='):
                        env_lines[i] = f'STRAVA_REFRESH_TOKEN={refresh_token}\n'
                        token_updated = True
                        break

                if not token_updated:
                    env_lines.append(f'\nSTRAVA_REFRESH_TOKEN={refresh_token}\n')

                # Write back
                with open('.env', 'w') as f:
                    f.writelines(env_lines)

                print("✅ .env aktualisiert!")
                print()

            except Exception as e:
                print(f"⚠️  Konnte .env nicht automatisch aktualisieren: {e}")
                print()
                print("Füge manuell hinzu:")
                print(f"STRAVA_REFRESH_TOKEN={refresh_token}")
                print()

            print("=" * 60)
            print("🎉 FERTIG!")
            print("=" * 60)
            print()
            print("Starte jetzt deinen Server neu:")
            print("  python app_complete_with_strava.py")
            print()
            print("Strava sollte jetzt funktionieren!")

        else:
            print(f"❌ Token-Test fehlgeschlagen: {test_resp.status_code}")
            print(f"   Response: {test_resp.text}")
            print()
            print("   Versuche es nochmal oder kontaktiere Support.")

    else:
        print(f"❌ Token-Anfrage fehlgeschlagen: {resp.status_code}")
        print(f"   Response: {resp.text}")

except Exception as e:
    print(f"❌ Fehler: {e}")
    import traceback

    traceback.print_exc()