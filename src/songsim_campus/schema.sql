CREATE TABLE IF NOT EXISTS places (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    aliases_json TEXT NOT NULL DEFAULT '[]',
    description TEXT NOT NULL DEFAULT '',
    latitude REAL,
    longitude REAL,
    opening_hours_json TEXT NOT NULL DEFAULT '{}',
    source_tag TEXT NOT NULL DEFAULT 'demo',
    last_synced_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    last_synced_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS restaurants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    min_price INTEGER,
    max_price INTEGER,
    latitude REAL,
    longitude REAL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    description TEXT NOT NULL DEFAULT '',
    source_tag TEXT NOT NULL DEFAULT 'demo',
    last_synced_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    published_at TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    labels_json TEXT NOT NULL DEFAULT '[]',
    source_url TEXT,
    source_tag TEXT NOT NULL DEFAULT 'demo',
    last_synced_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transport_guides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    steps_json TEXT NOT NULL DEFAULT '[]',
    source_url TEXT,
    source_tag TEXT NOT NULL DEFAULT 'demo',
    last_synced_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_courses (
    profile_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    code TEXT NOT NULL,
    section TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (profile_id, year, semester, code, section),
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS profile_notice_preferences (
    profile_id TEXT PRIMARY KEY,
    categories_json TEXT NOT NULL DEFAULT '[]',
    keywords_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_places_name ON places(name);
CREATE INDEX IF NOT EXISTS idx_courses_title ON courses(title);
CREATE INDEX IF NOT EXISTS idx_courses_code ON courses(code);
CREATE INDEX IF NOT EXISTS idx_restaurants_name ON restaurants(name);
CREATE INDEX IF NOT EXISTS idx_notices_published_at ON notices(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_transport_guides_mode ON transport_guides(mode);
CREATE INDEX IF NOT EXISTS idx_profile_courses_profile_id ON profile_courses(profile_id);
