#!/usr/bin/env python3
"""
Fetch conversations by intercepting API responses.
"""

from playwright.sync_api import sync_playwright
from pathlib import Path
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

PROFILE_DIR = Path("./chatgpt_profile")
DATA_DIR = Path("./data")

def fetch_conversations():
    """Fetch conversations by intercepting the actual API responses."""
    
    if not PROFILE_DIR.exists():
        raise RuntimeError(f"Profile not found at {PROFILE_DIR}. Run setup_auth.py first.")
    
    DATA_DIR.mkdir(exist_ok=True)
    conversations_data = None
    conversation_details = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,  # Show browser to see what's happening
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = browser.new_page()
        
        # Intercept responses
        def handle_response(response):
            nonlocal conversations_data, conversation_details
            
            try:
                if 'backend-api/conversations' in response.url and response.status == 200:
                    data = response.json()
                    if 'items' in data:
                        conversations_data = data
                        logging.info(f"Intercepted conversations list: {len(data['items'])} items")
                
                elif 'backend-api/conversation/' in response.url and response.status == 200:
                    data = response.json()
                    if 'id' in data:
                        conv_id = data['id']
                        conversation_details[conv_id] = data
                        logging.info(f"Intercepted conversation: {data.get('title', 'Untitled')}")
            except Exception as e:
                pass  # Ignore non-JSON responses
        
        page.on("response", handle_response)
        
        # Navigate to ChatGPT
        logging.info("Loading ChatGPT...")
        page.goto("https://chatgpt.com")
        page.wait_for_load_state("networkidle")
        
        # Wait for conversations to load
        logging.info("Waiting for conversations to load...")
        page.wait_for_timeout(5000)
        
        if not conversations_data:
            logging.info("No conversations intercepted on page load. Trying to trigger a refresh...")
            
            # Try clicking on the ChatGPT logo or new chat button to trigger a refresh
            try:
                # Look for new chat button
                new_chat = page.locator("a[href='/']").first
                if new_chat.count() > 0:
                    new_chat.click()
                    page.wait_for_timeout(3000)
            except:
                pass
        
        if conversations_data:
            logging.info(f"\n✅ Successfully captured {len(conversations_data['items'])} conversations!")
            
            # Save the conversations list
            with open(DATA_DIR / "conversations_list.json", 'w') as f:
                json.dump(conversations_data, f, indent=2)
            
            # Now click on each conversation to get details
            logging.info("\nFetching conversation details...")
            
            conv_links = page.locator("a[href^='/c/']")
            conv_count = conv_links.count()
            
            if conv_count > 0:
                logging.info(f"Found {conv_count} conversation links in sidebar")
                
                # Click on each conversation (up to 10 for demo)
                for i in range(min(conv_count, 10)):
                    try:
                        conv_links.nth(i).click()
                        page.wait_for_timeout(2000)  # Wait for conversation to load
                    except:
                        pass
            
            # Save all intercepted conversations
            saved_count = 0
            for conv_id, conv_data in conversation_details.items():
                conv_file = DATA_DIR / f"{conv_id}.json"
                with open(conv_file, 'w') as f:
                    json.dump(conv_data, f, indent=2)
                saved_count += 1
            
            logging.info(f"\n✅ Saved {saved_count} conversation details to {DATA_DIR}")
            
            # Save state
            state = {
                "last_fetch": datetime.now().isoformat(),
                "conversation_count": len(conversations_data['items']),
                "details_saved": saved_count
            }
            with open(DATA_DIR / ".state.json", 'w') as f:
                json.dump(state, f, indent=2)
            
        else:
            logging.error("Could not intercept any conversations. The page structure might have changed.")
        
        input("\nPress Enter to close browser...")
        browser.close()

def main():
    """Main entry point."""
    try:
        fetch_conversations()
        return 0
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())