"""Incremental, restartable TMDB enrichment pipeline."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime

from .database import ensure_schema
from .tmdb import TMDBClient


@dataclass(frozen=True)
class EnrichmentProgress:
    completed: int
    total: int
    found: int
    failed: int
    movie_name: str = ""


ProgressCallback = Callable[[EnrichmentProgress], None]


def _pending_movies(
    conn: sqlite3.Connection,
    force: bool = False,
    retry_unmatched: bool = False,
) -> list[dict]:
    if force:
        where = "1=1"
    else:
        statuses = (
            "'pending', 'failed', 'running', 'no_match'"
            if retry_unmatched
            else "'pending', 'failed', 'running'"
        )
        where = f"COALESCE(e.status, 'pending') IN ({statuses})"
    rows = conn.execute(
        f"""
        SELECT DISTINCT d.letterboxd_uri, d.name, d.year
        FROM diary d
        LEFT JOIN enrichment_status e ON e.letterboxd_uri=d.letterboxd_uri
        LEFT JOIN movie_metadata m ON m.letterboxd_uri=d.letterboxd_uri
        WHERE d.letterboxd_uri IS NOT NULL AND d.letterboxd_uri != ''
          AND {where}
          AND COALESCE(m.manually_corrected, 0) = 0
        ORDER BY d.year DESC, d.name
        """
    ).fetchall()
    return [{"uri": row[0], "name": row[1], "year": row[2]} for row in rows]


def _normalize(movie: dict, payload: dict | None) -> dict:
    if payload is None:
        return {**movie, "found": False}
    details = payload["details"]
    credits = payload["credits"]
    return {
        **movie,
        "found": True,
        "tmdb_id": details["id"],
        "poster_path": details.get("poster_path"),
        "genres": ",".join(g["name"] for g in details.get("genres", [])),
        "countries": ",".join(
            c["iso_3166_1"] for c in details.get("production_countries", [])
        ),
        "languages": ",".join(
            l["iso_639_1"] for l in details.get("spoken_languages", [])
        ),
        "runtime": details.get("runtime"),
        "media_type": payload.get("media_type", "movie"),
        "match_confidence": payload.get("match_confidence"),
        "directors": [
            {
                "name": person["name"],
                "id": person["id"],
                "photo": person.get("profile_path"),
            }
            for person in credits.get("crew", [])
            if person.get("job") == "Director"
        ],
        "cast": [
            {
                "name": person["name"],
                "character": person.get("character"),
                "id": person["id"],
                "photo": person.get("profile_path"),
                "order": order,
            }
            for order, person in enumerate(credits.get("cast", [])[:5])
        ],
    }


def _fetch(client: TMDBClient, movie: dict) -> dict:
    return _normalize(movie, client.full_media(movie["name"], movie["year"]))


def save_tmdb_payload(
    conn: sqlite3.Connection,
    letterboxd_uri: str,
    name: str,
    year: int | None,
    payload: dict,
    *,
    manually_corrected: bool = False,
) -> None:
    """Atomically replace metadata children while keeping the stable parent row."""
    result = _normalize({"uri": letterboxd_uri, "name": name, "year": year}, payload)
    result["found"] = True
    conn.execute(
        """
        INSERT INTO movie_metadata(
            letterboxd_uri,name,year,tmdb_id,poster_path,genres,countries,languages,runtime,
            manually_corrected,media_type,match_confidence
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(letterboxd_uri) DO UPDATE SET
            name=excluded.name, year=excluded.year, tmdb_id=excluded.tmdb_id,
            poster_path=excluded.poster_path, genres=excluded.genres, countries=excluded.countries,
            languages=excluded.languages, runtime=excluded.runtime,
            manually_corrected=excluded.manually_corrected,
            media_type=excluded.media_type, match_confidence=excluded.match_confidence
        """,
        (
            letterboxd_uri,
            name,
            year,
            result["tmdb_id"],
            result["poster_path"],
            result["genres"],
            result["countries"],
            result["languages"],
            result["runtime"],
            int(manually_corrected),
            result["media_type"],
            1.0 if manually_corrected else result["match_confidence"],
        ),
    )
    conn.execute(
        "DELETE FROM movie_directors WHERE letterboxd_uri=?", (letterboxd_uri,)
    )
    conn.execute("DELETE FROM movie_cast WHERE letterboxd_uri=?", (letterboxd_uri,))
    conn.executemany(
        "INSERT INTO movie_directors(letterboxd_uri,director_name,director_tmdb_id,director_photo) VALUES(?,?,?,?)",
        [
            (letterboxd_uri, d["name"], d["id"], d.get("photo"))
            for d in result["directors"]
        ],
    )
    conn.executemany(
        "INSERT INTO movie_cast(letterboxd_uri,actor_name,character_name,actor_tmdb_id,actor_photo,cast_order) VALUES(?,?,?,?,?,?)",
        [
            (
                letterboxd_uri,
                a["name"],
                a.get("character"),
                a["id"],
                a.get("photo"),
                a["order"],
            )
            for a in result["cast"]
        ],
    )
    _set_status(conn, letterboxd_uri, "success", None, increment=True)


def _set_status(
    conn: sqlite3.Connection,
    uri: str,
    status: str,
    error: str | None,
    *,
    increment: bool,
) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """
        INSERT INTO enrichment_status(letterboxd_uri,status,attempts,last_error,updated_at)
        VALUES(?,?,?,?,?)
        ON CONFLICT(letterboxd_uri) DO UPDATE SET
            status=excluded.status,
            attempts=enrichment_status.attempts + ?,
            last_error=excluded.last_error,
            updated_at=excluded.updated_at
        """,
        (uri, status, int(increment), error, now, int(increment)),
    )


def _save_result(conn: sqlite3.Connection, result: dict) -> None:
    if not result["found"]:
        conn.execute(
            """
            INSERT INTO movie_metadata(letterboxd_uri,name,year)
            VALUES(?,?,?) ON CONFLICT(letterboxd_uri) DO NOTHING
            """,
            (result["uri"], result["name"], result["year"]),
        )
        _set_status(
            conn, result["uri"], "no_match", "No TMDB match found", increment=True
        )
        return
    payload = {
        "details": {
            "id": result["tmdb_id"],
            "poster_path": result["poster_path"],
            "genres": [
                {"name": value} for value in result["genres"].split(",") if value
            ],
            "production_countries": [
                {"iso_3166_1": value}
                for value in result["countries"].split(",")
                if value
            ],
            "spoken_languages": [
                {"iso_639_1": value}
                for value in result["languages"].split(",")
                if value
            ],
            "runtime": result["runtime"],
        },
        "credits": {
            "crew": [
                {
                    "name": d["name"],
                    "id": d["id"],
                    "profile_path": d.get("photo"),
                    "job": "Director",
                }
                for d in result["directors"]
            ],
            "cast": [
                {
                    "name": a["name"],
                    "character": a.get("character"),
                    "id": a["id"],
                    "profile_path": a.get("photo"),
                }
                for a in result["cast"]
            ],
        },
        "media_type": result["media_type"],
        "match_confidence": result["match_confidence"],
    }
    save_tmdb_payload(conn, result["uri"], result["name"], result["year"], payload)


def enrich_library(
    conn: sqlite3.Connection,
    api_key: str,
    progress_callback: ProgressCallback | None = None,
    *,
    force: bool = False,
    retry_unmatched: bool = False,
    max_workers: int = 5,
) -> EnrichmentProgress:
    ensure_schema(conn)
    movies = _pending_movies(conn, force=force, retry_unmatched=retry_unmatched)
    total = len(movies)
    progress = EnrichmentProgress(0, total, 0, 0)
    if progress_callback:
        progress_callback(progress)
    if not movies:
        return progress

    client = TMDBClient(api_key)
    # Reject an invalid key before changing hundreds of per-film states to failed.
    client.validate_key()
    for movie in movies:
        _set_status(conn, movie["uri"], "running", None, increment=False)
    conn.commit()

    completed = found = failed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch, client, movie): movie for movie in movies}
        for future in as_completed(futures):
            movie = futures[future]
            try:
                result = future.result()
                with conn:
                    _save_result(conn, result)
                found += int(result["found"])
            except Exception as exc:  # noqa: BLE001 - one failed movie must not abort the batch
                with conn:
                    _set_status(
                        conn, movie["uri"], "failed", str(exc)[:500], increment=True
                    )
                failed += 1
            completed += 1
            progress = EnrichmentProgress(
                completed, total, found, failed, movie["name"]
            )
            if progress_callback:
                progress_callback(progress)
    return progress
