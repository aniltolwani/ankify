#!/usr/bin/env python3
"""
Fetch conversations using JavaScript extraction in the browser context.
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
    """Fetch conversations by extracting the access token from the page."""
    
    if not PROFILE_DIR.exists():
        raise RuntimeError(f"Profile not found at {PROFILE_DIR}. Run setup_auth.py first.")
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,  # Show browser to debug
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = browser.new_page()
        
        # Navigate to ChatGPT
        logging.info("Loading ChatGPT...")
        page.goto("https://chatgpt.com")
        page.wait_for_load_state("networkidle")
        
        # Wait for the page to fully load
        page.wait_for_timeout(5000)
        
        # Try to get the access token from the page context
        logging.info("Extracting access token...")
        
        # Execute JavaScript to get the token
        token_result = page.evaluate("""() => {
            // Try to find the access token in various places
            
            // Method 1: From localStorage
            const localToken = localStorage.getItem('__Secure-next-auth.session-token');
            if (localToken) return { source: 'localStorage', token: localToken };
            
            // Method 2: From __NEXT_DATA__
            const nextData = document.getElementById('__NEXT_DATA__');
            if (nextData) {
                try {
                    const data = JSON.parse(nextData.textContent);
                    const token = data?.props?.pageProps?.session?.accessToken;
                    if (token) return { source: '__NEXT_DATA__', token: token };
                } catch (e) {}
            }
            
            // Method 3: Try to intercept from fetch calls
            // This would require injecting code before page load
            
            return { source: 'not_found', token: null };
        }""")
        
        logging.info(f"Token search result: {token_result['source']}")
        
        if token_result['token']:
            access_token = token_result['token']
            logging.info(f"Found token! Length: {len(access_token)}")
            
            # Now fetch conversations using the page context
            logging.info("Fetching conversations...")
            
            conversations = page.evaluate("""(token) => {
                return fetch('https://chatgpt.com/backend-api/conversations?offset=0&limit=100', {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Accept': 'application/json'
                    }
                }).then(r => r.json());
            }""", access_token)
            
            if conversations and 'items' in conversations:
                logging.info(f"Found {len(conversations['items'])} conversations!")
                
                # Save conversations
                DATA_DIR.mkdir(exist_ok=True)
                
                for conv in conversations['items']:
                    conv_id = conv['id']
                    title = conv.get('title', 'Untitled')
                    
                    # Save summary
                    conv_file = DATA_DIR / f"{conv_id}_summary.json"
                    with open(conv_file, 'w') as f:
                        json.dump(conv, f, indent=2)
                    
                    logging.info(f"  Saved: {title}")
                
                return True
            else:
                logging.error("Could not fetch conversations")
                logging.error(f"Response: {conversations}")
        else:
            # Try alternative: intercept network requests
            logging.info("Token not found in page, trying network interception...")
            
            # Set up request interception
            access_token = None
            
            def handle_request(route, request):
                nonlocal access_token
                auth_header = request.headers.get('authorization', '')
                if auth_header.startswith('Bearer ') and not access_token:
                    access_token = auth_header.replace('Bearer ', '')
                    logging.info(f"Intercepted token from request!")
                route.continue_()
            
            page.route("**/*", handle_request)
            
            # Trigger a request by navigating or refreshing
            page.reload()
            page.wait_for_timeout(5000)
            
            if access_token:
                logging.info("Successfully intercepted token!")
                # Now you can use the token...
            
        input("Press Enter to close browser...")
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