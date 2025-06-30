#!/usr/bin/env python3
"""Debug token format and API access."""

from playwright.sync_api import sync_playwright
from pathlib import Path
import requests
import json
import base64

PROFILE_DIR = Path("./chatgpt_profile")

def debug_token():
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = browser.new_page()
        page.goto("https://chatgpt.com", wait_until="networkidle")
        page.wait_for_timeout(3000)
        
        # Get all cookies
        cookies = browser.cookies()
        session_cookie = next((c for c in cookies if c['name'] == '__Secure-next-auth.session-token'), None)
        
        if session_cookie:
            token = session_cookie['value']
            print(f"Token length: {len(token)}")
            print(f"Token preview: {token[:50]}...")
            
            # Check if it's a JWT
            parts = token.split('.')
            if len(parts) == 3:
                print("Token appears to be a JWT")
                try:
                    # Decode JWT payload (add padding if needed)
                    payload = parts[1]
                    payload += '=' * (4 - len(payload) % 4)
                    decoded = base64.urlsafe_b64decode(payload)
                    print(f"JWT payload: {json.loads(decoded)}")
                except Exception as e:
                    print(f"Could not decode JWT: {e}")
            else:
                print(f"Token has {len(parts)} parts (expected 3 for JWT)")
            
            # Try a simple API call
            headers = {
                "Authorization": f"Bearer {token}",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Referer": "https://chatgpt.com/"
            }
            
            # Try conversations endpoint
            print("\nTrying conversations endpoint...")
            resp = requests.get("https://chatgpt.com/backend-api/conversations?offset=0&limit=1", 
                              headers=headers, allow_redirects=False)
            print(f"Status: {resp.status_code}")
            print(f"Headers: {dict(resp.headers)}")
            if resp.status_code != 200:
                print(f"Response: {resp.text[:500]}")
            
            # Try models endpoint (simpler)
            print("\nTrying models endpoint...")
            resp2 = requests.get("https://chatgpt.com/backend-api/models", 
                               headers=headers, allow_redirects=False)
            print(f"Status: {resp2.status_code}")
            if resp2.status_code == 200:
                print("Models response OK!")
            
        browser.close()

if __name__ == "__main__":
    debug_token()