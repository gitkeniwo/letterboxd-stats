"""SQLite schema, migrations, and connection helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 2


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create non-destructive schema additions for both new and legacy databases."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS diary (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, name TEXT NOT NULL,
            year INTEGER, letterboxd_uri TEXT, rating REAL, rewatch INTEGER DEFAULT 0,
            tags TEXT, watched_date TEXT
        );
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, name TEXT NOT NULL,
            year INTEGER, letterboxd_uri TEXT, rating REAL
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, name TEXT NOT NULL,
            year INTEGER, letterboxd_uri TEXT, rating REAL, rewatch INTEGER DEFAULT 0,
            review TEXT, tags TEXT, watched_date TEXT
        );
        CREATE TABLE IF NOT EXISTS watched (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, name TEXT NOT NULL,
            year INTEGER, letterboxd_uri TEXT
        );
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, name TEXT NOT NULL,
            year INTEGER, letterboxd_uri TEXT
        );
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date_joined TEXT, username TEXT,
            given_name TEXT, family_name TEXT, email TEXT, location TEXT, website TEXT,
            bio TEXT, pronoun TEXT, favorite_films TEXT
        );
        CREATE TABLE IF NOT EXISTS movie_metadata (
            letterboxd_uri TEXT PRIMARY KEY, name TEXT NOT NULL, year INTEGER,
            tmdb_id INTEGER, poster_path TEXT, genres TEXT, countries TEXT,
            languages TEXT, runtime INTEGER, manually_corrected INTEGER DEFAULT 0,
            media_type TEXT DEFAULT 'movie', match_confidence REAL
        );
        CREATE TABLE IF NOT EXISTS movie_directors (
            id INTEGER PRIMARY KEY AUTOINCREMENT, letterboxd_uri TEXT NOT NULL,
            director_name TEXT NOT NULL, director_tmdb_id INTEGER, director_photo TEXT,
            FOREIGN KEY (letterboxd_uri) REFERENCES movie_metadata(letterboxd_uri) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS movie_cast (
            id INTEGER PRIMARY KEY AUTOINCREMENT, letterboxd_uri TEXT NOT NULL,
            actor_name TEXT NOT NULL, character_name TEXT, actor_tmdb_id INTEGER,
            actor_photo TEXT, cast_order INTEGER,
            FOREIGN KEY (letterboxd_uri) REFERENCES movie_metadata(letterboxd_uri) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS enrichment_status (
            letterboxd_uri TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS import_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, export_hash TEXT NOT NULL,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, diary_count INTEGER NOT NULL,
            username TEXT, status TEXT NOT NULL DEFAULT 'success'
        );
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_diary_watched_date ON diary(watched_date);
        CREATE INDEX IF NOT EXISTS idx_diary_year ON diary(year);
        CREATE INDEX IF NOT EXISTS idx_diary_rating ON diary(rating);
        CREATE INDEX IF NOT EXISTS idx_metadata_tmdb ON movie_metadata(tmdb_id);
        CREATE INDEX IF NOT EXISTS idx_directors_uri ON movie_directors(letterboxd_uri);
        CREATE INDEX IF NOT EXISTS idx_directors_name ON movie_directors(director_name);
        CREATE INDEX IF NOT EXISTS idx_cast_uri ON movie_cast(letterboxd_uri);
        """
    )

    # Legacy databases predate this flag. SQLite lacks ADD COLUMN IF NOT EXISTS.
    metadata_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(movie_metadata)")
    }
    if "manually_corrected" not in metadata_columns:
        conn.execute(
            "ALTER TABLE movie_metadata ADD COLUMN manually_corrected INTEGER DEFAULT 0"
        )
    if "media_type" not in metadata_columns:
        conn.execute(
            "ALTER TABLE movie_metadata ADD COLUMN media_type TEXT DEFAULT 'movie'"
        )
    if "match_confidence" not in metadata_columns:
        conn.execute("ALTER TABLE movie_metadata ADD COLUMN match_confidence REAL")
    # Preserve successful work from databases created by the legacy pipeline.
    conn.execute(
        """
        INSERT INTO enrichment_status(letterboxd_uri, status, attempts)
        SELECT letterboxd_uri, 'success', 1 FROM movie_metadata
        WHERE tmdb_id IS NOT NULL
        ON CONFLICT(letterboxd_uri) DO NOTHING
        """
    )
    conn.execute(
        "INSERT INTO app_state(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def has_diary_data(conn: sqlite3.Connection) -> bool:
    return bool(
        conn.execute("SELECT EXISTS(SELECT 1 FROM diary LIMIT 1)").fetchone()[0]
    )


def enrichment_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT e.status, COUNT(*) AS count
        FROM enrichment_status e
        JOIN (
            SELECT DISTINCT letterboxd_uri FROM diary
            WHERE letterboxd_uri IS NOT NULL AND letterboxd_uri != ''
        ) current ON current.letterboxd_uri=e.letterboxd_uri
        GROUP BY e.status
        """
    ).fetchall()
    result = {row["status"]: row["count"] for row in rows}
    total = conn.execute(
        "SELECT COUNT(DISTINCT letterboxd_uri) FROM diary "
        "WHERE letterboxd_uri IS NOT NULL AND letterboxd_uri != ''"
    ).fetchone()[0]
    result["total"] = total
    result["remaining"] = max(
        0, total - result.get("success", 0) - result.get("no_match", 0)
    )
    return result
