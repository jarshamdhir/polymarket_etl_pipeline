import httpx

URL = "https://gamma-api.polymarket.com/events"

def fetch_events(limit: int = 10) -> list:
    # Call polymarket gamma api to fetch events list
    params = {"limit":limit,"active":"true"}
    response = httpx.get(URL, params={"limit": limit})
    if response.status_code != 200:
        raise Exception(f"Failed to fetch events: {response.status_code}")
    return response.json()

if __name__ == "__main__":
    events = fetch_events(limit=10)
    print(f"Fetched {len(events)} events")
    print(events[0]['title'])