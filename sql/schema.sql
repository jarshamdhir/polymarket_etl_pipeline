CREATE TABLE events (
    event_id       TEXT PRIMARY KEY,
    title          TEXT,
    slug           TEXT,
    category       TEXT,
    volume         NUMERIC,
    volume_24hr    NUMERIC,
    volume_1wk     NUMERIC,
    liquidity      NUMERIC,
    open_interest  NUMERIC,
    start_date     TIMESTAMPTZ,
    end_date       TIMESTAMPTZ,
    is_active      BOOLEAN,
    is_closed      BOOLEAN,
    created_at     TIMESTAMPTZ,
    updated_at     TIMESTAMPTZ,
    loaded_at      TIMESTAMPTZ DEFAULT NOW()
);