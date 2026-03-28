"""
Authentication bootstrap for first-time SSO login.

This script launches a persistent browser context, lets you complete SSO + DUO
manually, then saves session state so future runs can reuse it until expiry.
"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

PROJECT_ROOT = Path(__file__).parent.parent
TARGET_URL = "https://sundevilcentral.eoss.asu.edu/events"
SESSION_DIR = PROJECT_ROOT / "data" / "session"
STORAGE_STATE_PATH = SESSION_DIR / "storage_state.json"


async def validate_session() -> bool:
    if STORAGE_STATE_PATH.exists():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=str(STORAGE_STATE_PATH))
            page = await context.new_page()
            try:
                await page.goto(TARGET_URL, wait_until="networkidle")
                await page.wait_for_url("**/events", timeout=5000)
                print("Existing session is valid")
                return True
            except PlaywrightTimeoutError:
                print("Existing session is invalid or expired")
                return False
            finally:
                await context.close()
                await browser.close()
    else:
        print("No existing session found")
        return False

async def auth() -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,
        )

        page = context.pages[0] if context.pages else await context.new_page()
        
        print(f"\n Opening {TARGET_URL}...")
        await page.goto(TARGET_URL, wait_until="networkidle")
        
        await asyncio.sleep(2)
        
        current_url = page.url
        if "weblogin.asu.edu" in current_url or "login" in current_url.lower():
            print("\n SSO login detected")
            print(" Complete SSO/DUO authentication in the browser window")
            print(" Navigate to the events page if not redirected automatically")
            print(" Once you can see the events page, return here and press Enter")
        elif "sundevilcentral.eoss.asu.edu/events" in current_url:
            print("\n Already authenticated! Session is valid.")
            print(" Press Enter to save the session state")
        else:
            print(f"\n Unexpected URL: {current_url}")
            print(" Navigate to the events page manually, then press Enter...")

        await asyncio.to_thread(input, "\nPress Enter when ready: ")
        
        try:
            print("\n Verifying authentication")
            await page.wait_for_url("**/events", timeout=5000)
            print(" Successfully on events page!")
        except PlaywrightTimeoutError:
            current_url = page.url
            if "sundevilcentral.eoss.asu.edu/events" in current_url:
                print(" Verified: on events page!")
            else:
                print(f" Warning: Not on events page. Current URL: {current_url}")
                print("Saving session anyway - you may need to re-authenticate later.")

        print(f"\n Saving session state")
        await context.storage_state(path=str(STORAGE_STATE_PATH))
        print(f" Session saved to: {STORAGE_STATE_PATH.resolve()}")
        
        print("\n Authentication complete! You can now use this session for scraping.")

        await context.close()

async def run() -> None:
    session_is_valid = await validate_session()
    if not session_is_valid:
        await auth()
    else:
        print("No need to re-authenticate. Session is still valid.")
    


if __name__ == "__main__":
    asyncio.run(run())