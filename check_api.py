#!/usr/bin/env python3
"""Check what APIs are available by inspecting network traffic."""

from playwright.sync_api import sync_playwright
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)

PROFILE_DIR = Path("./chatgpt_profile")

def check_apis():
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,  # Show browser
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = browser.new_page()
        
        # Set up request logging
        def log_request(request):
            if 'backend-api' in request.url or 'api' in request.url:
                logging.info(f"API Request: {request.method} {request.url}")
                if request.method == "GET" and "conversation" in request.url:
                    logging.info(f"  Headers: {request.headers}")
        
        page.on("request", log_request)
        
        logging.info("Loading ChatGPT...")
        page.goto("https://chatgpt.com")
        
        logging.info("Waiting for page to load and make API calls...")
        page.wait_for_timeout(10000)
        
        # Try clicking around to trigger API calls
        logging.info("Looking for conversation history...")
        
        # Try to find sidebar with conversations
        sidebar = page.locator("nav").first
        if sidebar.count() > 0:
            logging.info("Found sidebar, checking for conversations...")
            # Look for conversation items
            conv_items = page.locator("a[href^='/c/']")
            if conv_items.count() > 0:
                logging.info(f"Found {conv_items.count()} conversations in sidebar")
                # Click on first conversation
                conv_items.first.click()
                page.wait_for_timeout(3000)
        
        input("Press Enter to close browser (check the console for API calls)...")
        browser.close()

if __name__ == "__main__":
    check_apis()