from __future__ import annotations

from letterboxd_stats import enrichment
from letterboxd_stats.database import connect, ensure_schema
from letterboxd_stats.enrichment import enrich_library


class FakeTMDBClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def validate_key(self):
        return True

    def full_media(self, name, year):
        if name == "Missing":
            return None
        return {
            "media_type": "movie",
            "match_confidence": 0.95,
            "details": {
                "id": 42,
                "poster_path": "/poster.jpg",
                "runtime": 100,
                "genres": [{"name": "Drama"}],
                "production_countries": [{"iso_3166_1": "NL"}],
                "spoken_languages": [{"iso_639_1": "nl"}],
            },
            "credits": {
                "crew": [
                    {
                        "job": "Director",
                        "name": "Director",
                        "id": 7,
                        "profile_path": "/d.jpg",
                    }
                ],
                "cast": [
                    {
                        "name": "Actor",
                        "id": 8,
                        "character": "Lead",
                        "profile_path": "/a.jpg",
                    }
                ],
            },
        }


def test_enrichment_is_incremental_and_restartable(tmp_path, monkeypatch):
    monkeypatch.setattr(enrichment, "TMDBClient", FakeTMDBClient)
    conn = connect(tmp_path / "app.db")
    ensure_schema(conn)
    conn.executemany(
        "INSERT INTO diary(name,year,letterboxd_uri,watched_date) VALUES(?,?,?,?)",
        [
            ("Found", 2020, "found-uri", "2025-01-01"),
            ("Missing", 2021, "missing-uri", "2025-01-02"),
        ],
    )
    conn.commit()
    first = enrich_library(conn, "key", max_workers=2)
    assert first.found == 1
    assert first.failed == 0
    assert (
        conn.execute(
            "SELECT status FROM enrichment_status WHERE letterboxd_uri='found-uri'"
        ).fetchone()[0]
        == "success"
    )
    assert (
        conn.execute(
            "SELECT status FROM enrichment_status WHERE letterboxd_uri='missing-uri'"
        ).fetchone()[0]
        == "no_match"
    )
    metadata = conn.execute(
        "SELECT media_type, match_confidence FROM movie_metadata WHERE letterboxd_uri='found-uri'"
    ).fetchone()
    assert tuple(metadata) == ("movie", 0.95)
    second = enrich_library(conn, "key", max_workers=2)
    assert second.total == 0
    retry = enrich_library(conn, "key", retry_unmatched=True, max_workers=2)
    assert retry.total == 1
