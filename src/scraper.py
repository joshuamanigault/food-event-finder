"""
Purpose of this file is to scrape the events page and extract relevant information

This file will utilize auth.py to authenticate, if a session is valid it will reuse it, otherwise reauthentication is needed.


Events live in <ul id="divAllItems" class="list-group>, each event is classified as a <li id="event_###### class="list-group-item">

There are seperators listed as <li class="list-group__separator">, with another 
<li class="list-group-item style="display: none;"> following right after. 

These seperators are used to seperate the events by their date. For example, at the top of the page you have ongoing,
then it goes to today, then tomorrow, then it classifies it by the date after that. Generally, we should ignore the Ongoing Events
and focus on everything after that.

"""

from auth import auth, validate_session
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from pathlib import Path
import asyncio

PROJECT_ROOT = Path(__file__).parent.parent
TARGET_URL = "https://sundevilcentral.eoss.asu.edu/events"
SESSION_DIR = PROJECT_ROOT / "data" / "session"
STORAGE_STATE_PATH = SESSION_DIR / "storage_state.json"


async def scrape_events():
    if not await validate_session():
        await auth()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=STORAGE_STATE_PATH)
        page = await context.new_page()
        await page.goto(TARGET_URL, wait_until="networkidle")
        await page.wait_for_selector("#divAllItems", timeout=10000)

        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        events_list = soup.find('ul', id='divAllItems')
        events = [event for event in events_list.find_all('li', class_='list-group-item') if 'event_' in event.get('id','')]
        for event in events:
            print(event.get_text(strip=True))
        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_events())
