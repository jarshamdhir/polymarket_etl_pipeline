import httpx
from clean_events import clean_event

URL = "https://gamma-api.polymarket.com/events"

def fetch_events(limit: int = 10) -> list:
    # Call polymarket gamma api to fetch events list
    params = {"limit":limit,"active":"true"}
    response = httpx.get(URL, params=params,timeout=10)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch events: {response.status_code}")
    return response.json()

if __name__ == "__main__":
    events = fetch_events(limit=10)
    print(f"Fetched {len(events)} events")
    print(events[0].keys())
    first = events[0]
    print("\n======All top-level keys ========")
    cleaned = clean_event(first)
    print(cleaned)
    # print("id:      ", first.get("id"))
    # print("title:   ", first.get("title"))
    # print("slug:    ", first.get("slug"))
    # print("volume:  ", first.get("volume"))
    # print("endDate: ", first.get("endDate"))
    # print("tags:    ", first.get("tags"))