#!/usr/bin/env python3
"""
Fetch conversations from ChatGPT using saved browser profile.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
import requests
import json
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

PROFILE_DIR = Path("./chatgpt_profile")
CONV_URL = "https://chatgpt.com/backend-api/conversations?offset=0&limit=100"
DATA_DIR = Path("./data")

def load_cookies():
    """Load cookies from persistent browser profile."""
    if not PROFILE_DIR.exists():
        raise RuntimeError(f"Profile not found at {PROFILE_DIR}. Run setup_auth.py first.")
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = browser.new_page()
        logging.info("Loading ChatGPT to refresh tokens...")
        page.goto("https://chatgpt.com", wait_until="networkidle")
        page.wait_for_timeout(3000)  # Allow token refresh
        
        # Extract required cookies
        all_cookies = browser.cookies()
        needed_cookies = {}
        
        # The session token is the most important one
        for cookie in all_cookies:
            if cookie['name'] == '__Secure-next-auth.session-token':
                needed_cookies[cookie['name']] = cookie
                break
        
        # Check if we have the session token at least
        if '__Secure-next-auth.session-token' not in needed_cookies:
            logging.error("Session token not found")
            raise RuntimeError("Authentication failed. Run setup_auth.py again.")
        
        # Try to get other cookies if available (not strictly required)
        for cookie in all_cookies:
            if cookie['name'] in ['__Secure-next-auth.csrf-token', '_puid']:
                needed_cookies[cookie['name']] = cookie
        
        logging.info(f"Found cookies: {list(needed_cookies.keys())}")
        
        # Debug token format
        session_token = needed_cookies['__Secure-next-auth.session-token']['value']
        logging.debug(f"Token preview: {session_token[:50]}...")
        
        # Check token expiry
        session_cookie = needed_cookies['__Secure-next-auth.session-token']
        exp_ts = session_cookie.get('expires', 0)
        if exp_ts > 0:
            days_left = (exp_ts - time.time()) / 86400
            if days_left < 2:
                logging.warning(f"⚠️  Session expires in {days_left:.1f} days!")
            else:
                logging.info(f"Session valid for {days_left:.0f} more days")
        
        browser.close()
        return needed_cookies

def fetch_all_conversations(cookies):
    """Fetch conversation list from ChatGPT backend API."""
    # Build headers - session token is most important
    token = cookies['__Secure-next-auth.session-token']['value']
    
    # Build cookie string from available cookies
    cookie_parts = []
    for cookie in cookies.values():
        cookie_parts.append(f"{cookie['name']}={cookie['value']}")
    cookie_str = "; ".join(cookie_parts)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://chatgpt.com/",
        "Origin": "https://chatgpt.com"
    }
    
    # Fetch conversation list
    logging.info("Fetching conversation list...")
    logging.debug(f"Headers: {headers}")
    response = requests.get(CONV_URL, headers=headers, allow_redirects=False, timeout=30)
    
    # Check for redirect (indicates expired session)
    if response.status_code == 302:
        logging.error("Session expired - received redirect to login")
        raise RuntimeError("Session expired. Run setup_auth.py again.")
    
    response.raise_for_status()
    
    # Debug: Check response content
    if response.headers.get('content-type', '').startswith('application/json'):
        data = response.json()
        conversations = data.get('items', [])
    else:
        logging.error(f"Unexpected response type: {response.headers.get('content-type')}")
        logging.error(f"Response status: {response.status_code}")
        logging.error(f"Response preview: {response.text[:500]}")
        raise RuntimeError("Invalid response from ChatGPT API")
    
    logging.info(f"Found {len(conversations)} conversations")
    
    # Fetch each conversation
    DATA_DIR.mkdir(exist_ok=True)
    
    for i, conv in enumerate(conversations):
        conv_id = conv['id']
        title = conv.get('title', 'Untitled')
        
        # Skip if already downloaded (simple caching)
        conv_file = DATA_DIR / f"{conv_id}.json"
        if conv_file.exists():
            logging.info(f"  [{i+1}/{len(conversations)}] Skipping '{title}' (already exists)")
            continue
        
        # Fetch full conversation
        conv_url = f"https://chatgpt.com/backend-api/conversation/{conv_id}"
        logging.info(f"  [{i+1}/{len(conversations)}] Fetching '{title}'")
        
        conv_response = requests.get(conv_url, headers=headers, timeout=30)
        conv_response.raise_for_status()
        
        # Save to file
        with open(conv_file, 'w') as f:
            json.dump(conv_response.json(), f, indent=2)
        
        # Rate limiting
        if i < len(conversations) - 1:
            time.sleep(1)  # Be nice to the API
    
    return conversations

def main():
    """Main entry point."""
    try:
        # Load cookies
        cookies = load_cookies()
        
        # Fetch conversations
        conversations = fetch_all_conversations(cookies)
        
        # Save state
        state = {
            "last_fetch": datetime.now().isoformat(),
            "conversation_count": len(conversations)
        }
        with open(DATA_DIR / ".state.json", 'w') as f:
            json.dump(state, f, indent=2)
        
        logging.info("✅ Fetch complete!")
        
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())