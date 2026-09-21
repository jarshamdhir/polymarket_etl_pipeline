import httpx
from app.extract.clean_events import clean_event

URL = "https://gamma-api.polymarket.com/events"

def fetch_events(limit: int = 10) -> list:
    # Call polymarket gamma api to fetch events list
    params = {"limit":limit,"active":"true"}
    response = httpx.get(URL, params=params,timeout=10)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch events: {response.status_code}")
    return response.json()
def fetch_clean_events(limit: int =10) -> list:
    raw_events = fetch_events(limit=limit)
    return [clean_event(event) for event in raw_events]
