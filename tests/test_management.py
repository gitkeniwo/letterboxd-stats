from letterboxd_stats.database import connect, ensure_schema
from letterboxd_stats.management_ui import get_unmatched_movies


def test_manual_queue_only_contains_unmatched_films(tmp_path):
    conn = connect(tmp_path / "app.db")
    ensure_schema(conn)
    conn.executemany(
        "INSERT INTO diary(name,year,letterboxd_uri) VALUES(?,?,?)",
        [("Matched", 2000, "matched"), ("Missing", 2001, "missing")],
    )
    conn.execute(
        "INSERT INTO movie_metadata(letterboxd_uri,name,year,tmdb_id) VALUES(?,?,?,?)",
        ("matched", "Matched", 2000, 42),
    )
    conn.executemany(
        "INSERT INTO enrichment_status(letterboxd_uri,status) VALUES(?,?)",
        [("matched", "success"), ("missing", "no_match")],
    )
    conn.commit()
    queue = get_unmatched_movies(conn)
    assert [movie["name"] for movie in queue] == ["Missing"]
