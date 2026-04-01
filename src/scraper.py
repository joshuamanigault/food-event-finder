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
import datetime as Date
import asyncio

PROJECT_ROOT = Path(__file__).parent.parent
TARGET_URL = "https://sundevilcentral.eoss.asu.edu/events?format=on_campus"
SESSION_DIR = PROJECT_ROOT / "data" / "session"
STORAGE_STATE_PATH = SESSION_DIR / "storage_state.json"


async def scrape_events():
    cutoff_date = Date.datetime.now() + Date.timedelta(weeks=2)

    if not await validate_session():
        await auth()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=STORAGE_STATE_PATH)
        page = await context.new_page()
        await page.goto(TARGET_URL, wait_until="networkidle")
        await page.wait_for_selector("#divAllItems", timeout=10000)

        await scroll_until_cutoff(page, cutoff_date)

        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')

        await context.close()
        await browser.close()


async def scroll_until_cutoff(page, cutoff_date):
    reached_cutoff = False
    stagnant_count = 0
    scroll_iteration = 0

    while not reached_cutoff and stagnant_count < 5:
        scroll_iteration += 1

        prev_count = await page.locator('li[id^="event_"]').count()

        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await page.wait_for_timeout(2000)

        new_count = await page.locator('li[id^="event_"]').count()

        if new_count == prev_count:
            stagnant_count += 1
            print(f"Scroll iteration {scroll_iteration}: No new events loaded (Total: {new_count}) - Stagnant count: {stagnant_count}")
        else:
            events_loaded = new_count - prev_count
            print(f"Scroll iteration {scroll_iteration}: Loaded {events_loaded} new events (Total: {new_count})")
            stagnant_count = 0
        
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        check_reached_cutoff(soup, cutoff_date)
        # if check_reached_cutoff(soup, cutoff_date):
        #     reached_cutoff = True
        #     print(f"Scroll {scroll_iteration}: Reached cutoff date")
        #     break
    
    final_count = await page.locator('li[id^="event_"]').count()
    print(f"Total events loaded: {final_count}")

def check_reached_cutoff(soup, cutoff_date):
    seperators = soup.find_all('li', class_='list-group__separator')
    
    for sep in seperators:
        date_text = sep.get_text(strip=True) # Example: "Fri, Apr 3, 2026" - "Mon, Apr 6, 2026"
        print(date_text)

def parse_date_from_seperator(sep):
    date_text = sep.get_text(strip=True)
    today = Date.datetime.now().date()
    format = ""

    if date_text == "Ongoing":
        return None

    if date_text == "Today":
        return Date.datetime.combine(today, Date.time.min)

    if date_text == "Tomorrow":
        return Date.datetime.combine(today + Date.timedelta(days=1), Date.time.min)
    

    

if __name__ == "__main__":
    asyncio.run(scrape_events())
