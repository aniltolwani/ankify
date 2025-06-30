#!/usr/bin/env python3
"""
One-time setup script to login to ChatGPT and save browser profile.
Run this first to create the persistent browser profile.
"""

from playwright.sync_api import sync_playwright
import sys
from pathlib import Path

PROFILE_DIR = "./chatgpt_profile"

def main():
    print("🔐 ChatGPT Authentication Setup")
    print(f"This will create a browser profile in: {PROFILE_DIR}")
    print("-" * 50)
    
    Path(PROFILE_DIR).mkdir(exist_ok=True)
    
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = browser.pages[0] if browser.pages else browser.new_page()
        print("Navigating to ChatGPT...")
        page.goto("https://chatgpt.com")
        
        print("\n✋ Please log in to ChatGPT in the browser window.")
        print("After successful login, press Enter here to save the profile...")
        input()
        
        # Verify we're logged in by checking for cookies
        cookies = browser.cookies()
        session_cookie = next((c for c in cookies if c['name'] == '__Secure-next-auth.session-token'), None)
        
        if session_cookie:
            print("✅ Login successful! Profile saved.")
            print(f"   Cookie expires: {session_cookie.get('expires', 'unknown')}")
        else:
            print("❌ Login failed - session cookie not found.")
            print("   Please try again.")
            sys.exit(1)
        
        browser.close()
    
    print(f"\n✅ Setup complete! Browser profile saved to {PROFILE_DIR}")
    print("You can now run the automated fetch script.")

if __name__ == "__main__":
    main()