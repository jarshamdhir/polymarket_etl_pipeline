import httpx
from app.extract.clean_events import clean_event
import time

URL = "https://gamma-api.polymarket.com/events"

def fetch_events(limit: int = 100, offset: int = 0) -> list:
    # Call polymarket gamma api to fetch events list
    params = {"limit":limit,"active":"true","closed":"false","offset":offset}
    response = httpx.get(URL, params=params,timeout=10)
    if response.status_code == 422:
        return []
    if response.status_code != 200:
        raise Exception(f"Failed to fetch events: {response.status_code}")
    return response.json()
def fetch_clean_events(limit: int =100) -> list:
    raw_events = fetch_events_with_offset(limit=limit)
    return [clean_event(event) for event in raw_events]

def fetch_events_with_offset(limit: int = 100) -> list:
    all_events = []
    offset = 0

    for page_num in range(1, limit + 1):
        print(f"Fetching page {page_num} (offset={offset})...")
        page = fetch_events(limit=limit, offset=offset)
        if not page:
            print("     No more data -- stopping...")
            break

        all_events.extend(page)
        print(f" Got {len(page)} events (total so far: {len(all_events)})")

        if len(page) < limit:
            print("     Reached end of data -- stopping...")
            break
        
        offset += limit
        print(f"     Next offset: {offset}")
        time.sleep(1)
    print(f" Total events fetched: {len(all_events)}")
    return all_events
if __name__ == "__main__":
    events = fetch_events_with_offset(limit=1)
    for event in events:
        print(event.keys())