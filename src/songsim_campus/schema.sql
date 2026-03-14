CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS places (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    aliases_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    description TEXT NOT NULL DEFAULT '',
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geom GEOGRAPHY(Point, 4326) GENERATED ALWAYS AS (
        CASE
            WHEN longitude IS NULL OR latitude IS NULL THEN NULL
            ELSE ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
        END
    ) STORED,
    opening_hours_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_tag TEXT NOT NULL DEFAULT 'demo',
    last_synced_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    year INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    code TEXT NOT NULL,
    title TEXT NOT NULL,
    professor TEXT,
    department TEXT,
    section TEXT,
    day_of_week TEXT,
    period_start INTEGER,
    period_end INTEGER,
    room TEXT,
    raw_schedule TEXT,
    source_tag TEXT NOT NULL DEFAULT 'demo',
    last_synced_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS restaurants (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    min_price INTEGER,
    max_price INTEGER,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geom GEOGRAPHY(Point, 4326) GENERATED ALWAYS AS (
        CASE
            WHEN longitude IS NULL OR latitude IS NULL THEN NULL
            ELSE ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
        END
    ) STORED,
    tags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    description TEXT NOT NULL DEFAULT '',
    source_tag TEXT NOT NULL DEFAULT 'demo',
    last_synced_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS restaurant_cache_snapshots (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    origin_slug TEXT NOT NULL,
    kakao_query TEXT NOT NULL,
    radius_meters INTEGER NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    source_tag TEXT NOT NULL DEFAULT 'kakao_local_cache'
);

CREATE TABLE IF NOT EXISTS restaurant_cache_items (
    snapshot_id INTEGER NOT NULL,
    item_order INTEGER NOT NULL,
    restaurant_id INTEGER NOT NULL,
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    min_price INTEGER,
    max_price INTEGER,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    kakao_place_id TEXT,
    source_url TEXT,
    geom GEOGRAPHY(Point, 4326) GENERATED ALWAYS AS (
        CASE
            WHEN longitude IS NULL OR latitude IS NULL THEN NULL
            ELSE ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
        END
    ) STORED,
    tags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    description TEXT NOT NULL DEFAULT '',
    source_tag TEXT NOT NULL DEFAULT 'kakao_local_cache',
    last_synced_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (snapshot_id, item_order),
    FOREIGN KEY (snapshot_id) REFERENCES restaurant_cache_snapshots(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS restaurant_hours_cache (
    kakao_place_id TEXT PRIMARY KEY,
    source_url TEXT,
    raw_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    opening_hours_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    fetched_at TIMESTAMPTZ NOT NULL,
    source_tag TEXT NOT NULL DEFAULT 'kakao_place_detail_cache'
);

CREATE TABLE IF NOT EXISTS notices (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    published_at DATE NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    labels_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_url TEXT,
    source_tag TEXT NOT NULL DEFAULT 'demo',
    last_synced_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS transport_guides (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mode TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    steps_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_url TEXT,
    source_tag TEXT NOT NULL DEFAULT 'demo',
    last_synced_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    department TEXT,
    student_year INTEGER,
    admission_type TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_courses (
    profile_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    code TEXT NOT NULL,
    section TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (profile_id, year, semester, code, section),
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS profile_notice_preferences (
    profile_id TEXT PRIMARY KEY,
    categories_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    keywords_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS profile_interests (
    profile_id TEXT PRIMARY KEY,
    tags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

ALTER TABLE profiles ADD COLUMN IF NOT EXISTS department TEXT;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS student_year INTEGER;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS admission_type TEXT;
ALTER TABLE restaurant_cache_items ADD COLUMN IF NOT EXISTS kakao_place_id TEXT;
ALTER TABLE restaurant_cache_items ADD COLUMN IF NOT EXISTS source_url TEXT;

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    target TEXT NOT NULL,
    status TEXT NOT NULL,
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_text TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_places_name ON places(name);
CREATE INDEX IF NOT EXISTS idx_places_geom ON places USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_courses_title ON courses(title);
CREATE INDEX IF NOT EXISTS idx_courses_code ON courses(code);
CREATE INDEX IF NOT EXISTS idx_restaurants_name ON restaurants(name);
CREATE INDEX IF NOT EXISTS idx_restaurants_geom ON restaurants USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_restaurant_cache_key
ON restaurant_cache_snapshots(origin_slug, kakao_query, radius_meters);
CREATE INDEX IF NOT EXISTS idx_restaurant_cache_items_geom
ON restaurant_cache_items USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_restaurant_hours_cache_fetched_at
ON restaurant_hours_cache(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_notices_published_at ON notices(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_transport_guides_mode ON transport_guides(mode);
CREATE INDEX IF NOT EXISTS idx_profile_courses_profile_id ON profile_courses(profile_id);
CREATE INDEX IF NOT EXISTS idx_sync_runs_started_at ON sync_runs(started_at DESC);
