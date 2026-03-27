"""
Authentication bootstrap for first-time SSO login.

This script launches a persistent browser context, lets you complete SSO + DUO
manually, then saves session state so future runs can reuse it until expiry.
"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Use absolute path from project root
PROJECT_ROOT = Path(__file__).parent.parent
TARGET_URL = "https://sundevilcentral.eoss.asu.edu/events"
SESSION_DIR = PROJECT_ROOT / "data" / "session"
STORAGE_STATE_PATH = SESSION_DIR / "storage_state.json"


async def run() -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,
        )

        page = context.pages[0] if context.pages else await context.new_page()
        
        print(f"\n Opening {TARGET_URL}...")
        await page.goto(TARGET_URL, wait_until="networkidle")
        
        # Wait a moment for potential redirects
        await asyncio.sleep(2)
        
        # Check if we got redirected to SSO login
        current_url = page.url
        if "weblogin.asu.edu" in current_url or "login" in current_url.lower():
            print("\n SSO login detected!")
            print(" Complete SSO/DUO authentication in the browser window.")
            print(" Navigate to the events page if not redirected automatically.")
            print(" Once you can see the events page, return here and press Enter...")
        elif "sundevilcentral.eoss.asu.edu/events" in current_url:
            print("\n Already authenticated! Session is valid.")
            print(" Press Enter to save the session state...")
        else:
            print(f"\n Unexpected URL: {current_url}")
            print(" Navigate to the events page manually, then press Enter...")

        # Wait for user confirmation
        await asyncio.to_thread(input, "\nPress Enter when ready: ")
        
        # Verify we're on the events page
        try:
            print("\n Verifying authentication...")
            await page.wait_for_url("**/events", timeout=5000)
            print(" Successfully on events page!")
        except PlaywrightTimeoutError:
            current_url = page.url
            if "sundevilcentral.eoss.asu.edu/events" in current_url:
                print(" Verified: on events page!")
            else:
                print(f" Warning: Not on events page. Current URL: {current_url}")
                print("Saving session anyway - you may need to re-authenticate later.")

        # Save session state
        print(f"\n Saving session state...")
        await context.storage_state(path=str(STORAGE_STATE_PATH))
        print(f" Session saved to: {STORAGE_STATE_PATH.resolve()}")
        
        print("\n Authentication complete! You can now use this session for scraping.")

        await context.close()


if __name__ == "__main__":
    asyncio.run(run())