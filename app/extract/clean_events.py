def clean_event(raw: dict) -> dict:
    return {
        "event_id": raw.get("id"),
        "title": raw.get("title"),
        "slug": raw.get("slug"),
        "category": raw.get("category"),
        "volume": raw.get("volume"),
        "volume_24hr": raw.get("volume24hr"),
        "volume_1wk": raw.get("volume1wk"),
        "liquidity": raw.get("liquidity"),
        "open_interest": raw.get("openInterest"),
        "start_date": raw.get("startDate"),
        "end_date": raw.get("endDate"),
        "is_active": raw.get("active"),
        "is_closed": raw.get("closed"),
        "created_at": raw.get("createdAt"),
        "updated_at": raw.get("updatedAt"),
    }