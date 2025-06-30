#!/usr/bin/env python3
"""
Working fetch implementation using response interception.
"""

from playwright.sync_api import sync_playwright
from pathlib import Path
import json
import logging
from datetime import datetime
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

PROFILE_DIR = Path("./chatgpt_profile")
DATA_DIR = Path("./data")

def fetch_all_conversations():
    """Fetch conversations using response interception."""
    
    if not PROFILE_DIR.exists():
        raise RuntimeError(f"Profile not found at {PROFILE_DIR}. Run setup_auth.py first.")
    
    DATA_DIR.mkdir(exist_ok=True)
    intercepted_data = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,  # Note: headless=True may not trigger API calls properly
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = browser.new_page()
        
        # Intercept all API responses
        def handle_response(response):
            try:
                if 'backend-api' in response.url and response.status == 200:
                    data = response.json()
                    intercepted_data[response.url] = data
                    
                    if 'backend-api/conversations' in response.url and 'items' in data:
                        logging.info(f"Intercepted conversations list: {len(data['items'])} items")
                    elif 'backend-api/conversation/' in response.url and 'id' in data:
                        logging.info(f"Intercepted conversation: {data.get('title', 'Untitled')}")
                    else:
                        logging.debug(f"Intercepted other API: {response.url}")
            except:
                pass
        
        page.on("response", handle_response)
        
        # Navigate to ChatGPT
        logging.info("Loading ChatGPT...")
        page.goto("https://chatgpt.com")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)
        
        # Check if we're on the right page
        if "/auth" in page.url:
            logging.error("Not logged in! Please run setup again.")
            browser.close()
            return False
        
        # Try different ways to trigger the API call
        if not intercepted_data:
            logging.info("Waiting for conversations to load...")
            page.wait_for_timeout(5000)
            
        if not intercepted_data:
            logging.info("No API calls intercepted, trying to navigate to specific page...")
            # Try going to the root chat page
            page.goto("https://chatgpt.com/")
            page.wait_for_timeout(5000)
        
        # Find conversations data
        conversations_data = None
        for url, data in intercepted_data.items():
            if 'backend-api/conversations' in url and 'items' in data:
                conversations_data = data
                break
        
        if not conversations_data:
            logging.error("No conversations found. Make sure you're logged in.")
            browser.close()
            return False
        
        # Save conversations list
        conversations = conversations_data['items']
        logging.info(f"\nProcessing {len(conversations)} conversations...")
        
        # Process each conversation
        saved_count = 0
        for i, conv in enumerate(conversations):
            conv_id = conv['id']
            title = conv.get('title', 'Untitled')
            
            # Check if already saved
            conv_file = DATA_DIR / f"{conv_id}.json"
            if conv_file.exists():
                logging.info(f"  [{i+1}/{len(conversations)}] Skipping '{title}' (already exists)")
                continue
            
            # Check if we already intercepted this conversation
            full_conv = None
            for url, data in intercepted_data.items():
                if f'backend-api/conversation/{conv_id}' in url:
                    full_conv = data
                    break
            
            if full_conv:
                # Save the intercepted data
                with open(conv_file, 'w') as f:
                    json.dump(full_conv, f, indent=2)
                logging.info(f"  [{i+1}/{len(conversations)}] Saved '{title}' (from cache)")
                saved_count += 1
            else:
                # We need to fetch this conversation
                logging.info(f"  [{i+1}/{len(conversations)}] Fetching '{title}'")
                
                # Navigate to the conversation
                conv_url = f"https://chatgpt.com/c/{conv_id}"
                page.goto(conv_url)
                page.wait_for_timeout(2000)
                
                # Check if we intercepted it
                for url, data in list(intercepted_data.items()):
                    if f'backend-api/conversation/{conv_id}' in url:
                        with open(conv_file, 'w') as f:
                            json.dump(data, f, indent=2)
                        saved_count += 1
                        break
        
        # Save state
        state = {
            "last_fetch": datetime.now().isoformat(),
            "conversation_count": len(conversations),
            "saved_count": saved_count
        }
        with open(DATA_DIR / ".state.json", 'w') as f:
            json.dump(state, f, indent=2)
        
        logging.info(f"\n✅ Fetch complete! Saved {saved_count} conversations.")
        browser.close()
        return True

def main():
    """Main entry point."""
    try:
        success = fetch_all_conversations()
        return 0 if success else 1
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())