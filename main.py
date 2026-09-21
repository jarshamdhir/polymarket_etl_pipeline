from app.extract.fetch_events import fetch_clean_events
from app.load.save_events import save_events

def main():
    print("1. Extracting + cleaning events from API")
    events = fetch_clean_events(limit=100)
    print(f"     Got {len(events)} rows of data")

    print("2. Saving events to PostgreSQL")
    save_events(events)
    print("3. Done!")

if __name__ == "__main__":
    main()