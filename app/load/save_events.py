import os
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL",
                         "postgresql://polyetl:polyetl@localhost:5432/polyetl")

def save_events(events: list[dict]) -> None:
    """Insert cleaned events into PostgreSQL."""
    sql = """
        INSERT INTO events (
            event_id, title, slug, category,
            volume, volume_24hr, volume_1wk,
            liquidity, open_interest,
            start_date, end_date,
            is_active, is_closed,
            created_at, updated_at
        ) VALUES (
            %(event_id)s, %(title)s, %(slug)s, %(category)s,
            %(volume)s, %(volume_24hr)s, %(volume_1wk)s,
            %(liquidity)s, %(open_interest)s,
            %(start_date)s, %(end_date)s,
            %(is_active)s, %(is_closed)s,
            %(created_at)s, %(updated_at)s
        )
        ON CONFLICT (event_id) DO NOTHING
    """

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for row in events:
                cur.execute(sql, row)
        conn.commit()

