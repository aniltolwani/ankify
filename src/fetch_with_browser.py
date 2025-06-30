#!/usr/bin/env python3
"""
Alternative fetch method using browser automation to export conversations.
"""

from playwright.sync_api import sync_playwright
from pathlib import Path
import logging
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

PROFILE_DIR = Path("./chatgpt_profile")
DATA_DIR = Path("./data")

def export_conversations():
    """Use browser automation to trigger ChatGPT's export feature."""
    
    if not PROFILE_DIR.exists():
        raise RuntimeError(f"Profile not found at {PROFILE_DIR}. Run setup_auth.py first.")
    
    with sync_playwright() as p:
        logging.info("Launching browser...")
        browser = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,  # Must be False to handle any auth challenges
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = browser.new_page()
        
        try:
            # Navigate to ChatGPT
            logging.info("Navigating to ChatGPT...")
            page.goto("https://chatgpt.com")
            page.wait_for_load_state("networkidle")
            
            # Check if logged in
            if "auth" in page.url:
                logging.error("Not logged in! Please run setup_auth.py")
                return False
            
            # Navigate to settings
            logging.info("Opening settings...")
            
            # Try to find and click profile button (bottom left)
            profile_button = page.locator("button[data-testid='profile-button']").first
            if profile_button.count() == 0:
                # Try alternative selector
                profile_button = page.locator("div.relative button").filter(has_text="Settings")
            
            if profile_button.count() > 0:
                profile_button.click()
                page.wait_for_timeout(1000)
            else:
                logging.error("Could not find profile/settings button")
                return False
            
            # Click on Settings
            settings_link = page.locator("text=Settings").first
            if settings_link.count() > 0:
                settings_link.click()
                page.wait_for_timeout(2000)
            
            # Click on Data controls
            data_controls = page.locator("text=Data controls").first
            if data_controls.count() > 0:
                data_controls.click()
                page.wait_for_timeout(1000)
            
            # Click Export data
            export_button = page.locator("button:has-text('Export data')").first
            if export_button.count() > 0:
                logging.info("Clicking export button...")
                export_button.click()
                page.wait_for_timeout(2000)
                
                # Confirm export if needed
                confirm_button = page.locator("button:has-text('Confirm export')").first
                if confirm_button.count() > 0:
                    confirm_button.click()
                    logging.info("✅ Export requested! Check your email for the download link.")
                else:
                    logging.info("✅ Export requested (no confirmation needed)")
                
                # Save state
                DATA_DIR.mkdir(exist_ok=True)
                state = {
                    "export_requested": datetime.now().isoformat(),
                    "method": "browser_automation",
                    "note": "Check email for download link"
                }
                with open(DATA_DIR / ".export_state.json", 'w') as f:
                    json.dump(state, f, indent=2)
                
                return True
            else:
                logging.error("Could not find export button")
                return False
                
        except Exception as e:
            logging.error(f"Error during export: {e}")
            return False
        finally:
            page.wait_for_timeout(3000)  # Let user see the result
            browser.close()

def main():
    """Main entry point."""
    try:
        success = export_conversations()
        if success:
            logging.info("\n" + "="*60)
            logging.info("✅ Export requested successfully!")
            logging.info("📧 Check your email for the download link")
            logging.info("💾 Once downloaded, extract conversations.json to ./data/")
            logging.info("🔄 Then run: ./run.sh --extract")
            logging.info("="*60)
        else:
            logging.error("❌ Export failed")
            return 1
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())