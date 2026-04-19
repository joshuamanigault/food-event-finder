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


"""
TODO List: 
- Potentailly use tqdm for a progress bar instead of print statements
"""

from auth import auth, validate_session
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from pathlib import Path
import datetime as Date
import asyncio
import argparse

PROJECT_ROOT = Path(__file__).parent.parent
TARGET_URL = "https://sundevilcentral.eoss.asu.edu/events?format=on_campus"
SESSION_DIR = PROJECT_ROOT / "data" / "session"
STORAGE_STATE_PATH = SESSION_DIR / "storage_state.json"


async def scrape_events(dry_run_limit: int | None = None):
    cutoff_date = Date.datetime.now() + Date.timedelta(weeks=2)

    if not await validate_session():
        await auth()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=STORAGE_STATE_PATH)
        page = await context.new_page()
        await page.goto(TARGET_URL, wait_until="networkidle")
        await page.wait_for_selector("#divAllItems", timeout=10000)

        await scroll_until_cutoff(page, cutoff_date, dry_run_limit)

        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        filtered_events = extract_and_filter_events(soup, cutoff_date)
        for i in range(len(filtered_events)):
            print(f"Event {i + 1}: {filtered_events[i]}")

        await context.close()
        await browser.close()


async def scroll_until_cutoff(page, cutoff_date: Date.datetime, dry_run_limit: int | None = None):
    if dry_run_limit:
        print(f"DRY RUN MODE: Limiting scraping to {dry_run_limit} events")

    reached_cutoff = False
    stagnant_count = 0
    scroll_iteration = 0

    while not reached_cutoff and stagnant_count < 5:
        scroll_iteration += 1
        prev_count = await page.locator('li[id^="event_"]').count()
        
        await page.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })")
        await page.wait_for_timeout(2000)
        
        load_more_button = page.locator('#lnkLoadMore')
        try:
            if await load_more_button.is_visible():
                await load_more_button.click()
                await page.wait_for_load_state('networkidle')
                print(f"Scroll iteration {scroll_iteration}: Clicked 'Load More' button")
            else:
                print(f"Scroll iteration {scroll_iteration}: 'Load More' button not visible")
        except Exception as e:
            print(f'Scroll iteration {scroll_iteration}: Could not intereact with load button: {e}')

        new_count = await page.locator('li[id^="event_"]').count()

        if dry_run_limit and new_count >= dry_run_limit:
            break

        if new_count == prev_count:
            stagnant_count += 1
            print(f"Scroll iteration {scroll_iteration}: No new events loaded (Total: {new_count}) - Stagnant count: {stagnant_count}")
        else:
            events_loaded = new_count - prev_count
            print(f"Scroll iteration {scroll_iteration}: Loaded {events_loaded} new events (Total: {new_count})")
            stagnant_count = 0
        
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        if check_reached_cutoff(soup, cutoff_date):
            reached_cutoff = True
            print(f"Scroll {scroll_iteration}: Reached cutoff date")
            break
    
    if stagnant_count >= 5:
        print(f"Stopped scrolling after {scroll_iteration} iterations with no new events loaded.")
    
    final_count = await page.locator('li[id^="event_"]').count()
    print(f"Total events loaded: {final_count}")

def check_reached_cutoff(soup: BeautifulSoup, cutoff_date: Date.datetime) -> bool:
    seperators = soup.find_all('li', class_='list-group__separator')
    
    for sep in seperators:
        date_text = sep.get_text(strip=True) # Example: "Fri, Apr 3, 2026" - "Mon, Apr 6, 2026"
        event_date = parse_date_from_seperator(sep)
        if event_date and event_date > cutoff_date:
            print(f"Found seperator beyond cutoff: {date_text} - {event_date}")
            return True
        
    return False

def parse_date_from_seperator(sep: BeautifulSoup) -> Date.datetime | None:
    date_text = sep.get_text(strip=True)
    today = Date.datetime.now().date()
    format = "%a, %b %d, %Y"

    if date_text == "Ongoing":
        return None

    if date_text == "Today":
        return Date.datetime.combine(today, Date.time.min)

    if date_text == "Tomorrow":
        return Date.datetime.combine(today + Date.timedelta(days=1), Date.time.min)
    
    try:
        parsed = Date.datetime.strptime(date_text, format)
        return parsed
    except ValueError:
        return None


def extract_and_filter_events(soup: BeautifulSoup, cutoff_date: Date.datetime) -> list[BeautifulSoup]:
    events_list = soup.find('ul', id='divAllItems')

    if not events_list:
        print('Could not find events list')
        return []

    all_items = events_list.find_all('li', recursive=False)
    filtered_events =  []
    current_date = None

    for item in all_items:
        if 'list-group__separator' in item.get('class', []):
            current_date = parse_date_from_seperator(item)
            continue

        if 'list-group-item' in item.get('class', []) and 'event_' in item.get('id', ''):
            if current_date == None:
                continue
            
            if current_date > cutoff_date:
                continue
            
            event_data = parse_event_details(item)
            event_data['event_date'] = current_date
            filtered_events.append(event_data)
    
    return filtered_events

def parse_event_details(event_item: BeautifulSoup) -> dict:
    event_id = event_item.get('id', '').replace('event_', '')
    text_content = event_item.get_text(strip=True)

    return {
        'id': event_id,
        'raw_text': text_content,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape ASU events, decide if they have food or not, sync to Google Calendar"
        )

    parser.add_argument(
        '--dry-run', 
        type=int,
        nargs='?',
        const=15,
        help="Dry run mode: limit scraping to N events (10-30; Default : 15)"
        )
    
    args = parser.parse_args()
    if args.dry_run and (args.dry_run < 10 or args.dry_run > 30):
        print("Dry run limit should be between 10 and 30")
        exit(1)

    asyncio.run(scrape_events(dry_run_limit=args.dry_run))
