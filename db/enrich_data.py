"""
Enrich movie data with TMDB API - fetch directors, genres, countries, posters.
Uses letterboxd_uri as the unique identifier for movies.
"""
import os
import sqlite3
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from dotenv import load_dotenv


# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env.dev")

TMDB_API_KEY = os.getenv("API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# Rate limiting: 30 requests per 10 seconds = 3 per second
MAX_WORKERS = 5
REQUEST_DELAY = 0.35

thread_local = threading.local()


def get_client() -> httpx.Client:
    """Get thread-local HTTP client."""
    if not hasattr(thread_local, "client"):
        thread_local.client = httpx.Client(timeout=30)
    return thread_local.client


def search_movie(name: str, year: int | None) -> dict | None:
    """Search for a movie on TMDB."""
    client = get_client()
    params = {
        "api_key": TMDB_API_KEY,
        "query": name,
        "include_adult": "false",
    }
    if year:
        params["year"] = str(year)
    
    try:
        resp = client.get(f"{TMDB_BASE_URL}/search/movie", params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("results"):
            return data["results"][0]
    except Exception as e:
        print(f"  Error searching for '{name}': {e}")
    return None


def get_movie_details(movie_id: int) -> dict | None:
    """Get movie details."""
    client = get_client()
    params = {"api_key": TMDB_API_KEY}
    try:
        resp = client.get(f"{TMDB_BASE_URL}/movie/{movie_id}", params=params)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  Error getting details for {movie_id}: {e}")
    return None


def get_movie_credits(movie_id: int) -> dict | None:
    """Get movie credits."""
    client = get_client()
    params = {"api_key": TMDB_API_KEY}
    try:
        resp = client.get(f"{TMDB_BASE_URL}/movie/{movie_id}/credits", params=params)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  Error getting credits for {movie_id}: {e}")
    return None


def create_metadata_tables(conn: sqlite3.Connection):
    """Create tables using letterboxd_uri as primary identifier."""
    conn.executescript("""
        DROP TABLE IF EXISTS movie_metadata;
        DROP TABLE IF EXISTS movie_directors;
        DROP TABLE IF EXISTS movie_cast;
        
        CREATE TABLE movie_metadata (
            letterboxd_uri TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            year INTEGER,
            tmdb_id INTEGER,
            poster_path TEXT,
            genres TEXT,
            countries TEXT,
            languages TEXT,
            runtime INTEGER
        );
        
        CREATE TABLE movie_directors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            letterboxd_uri TEXT NOT NULL,
            director_name TEXT NOT NULL,
            director_tmdb_id INTEGER,
            director_photo TEXT,
            FOREIGN KEY (letterboxd_uri) REFERENCES movie_metadata(letterboxd_uri)
        );
        
        CREATE TABLE movie_cast (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            letterboxd_uri TEXT NOT NULL,
            actor_name TEXT NOT NULL,
            character_name TEXT,
            actor_tmdb_id INTEGER,
            actor_photo TEXT,
            cast_order INTEGER,
            FOREIGN KEY (letterboxd_uri) REFERENCES movie_metadata(letterboxd_uri)
        );
        
        CREATE INDEX idx_metadata_tmdb ON movie_metadata(tmdb_id);
        CREATE INDEX idx_directors_uri ON movie_directors(letterboxd_uri);
        CREATE INDEX idx_directors_name ON movie_directors(director_name);
        CREATE INDEX idx_cast_uri ON movie_cast(letterboxd_uri);
    """)


def get_unique_movies(conn: sqlite3.Connection) -> list[dict]:
    """Get list of unique movies from diary with letterboxd_uri."""
    cursor = conn.execute("""
        SELECT DISTINCT letterboxd_uri, name, year 
        FROM diary
        WHERE letterboxd_uri IS NOT NULL AND letterboxd_uri != ''
        ORDER BY year DESC, name
    """)
    return [{"uri": row[0], "name": row[1], "year": row[2]} for row in cursor]


def get_already_enriched(conn: sqlite3.Connection) -> set[str]:
    """Get already enriched letterboxd_uris."""
    cursor = conn.execute("SELECT letterboxd_uri FROM movie_metadata")
    return {row[0] for row in cursor}


def enrich_movie(movie: dict) -> dict:
    """Enrich a single movie with TMDB data."""
    uri = movie["uri"]
    name = movie["name"]
    year = movie["year"]
    
    time.sleep(REQUEST_DELAY)
    
    search_result = search_movie(name, year)
    if not search_result:
        time.sleep(REQUEST_DELAY)
        search_result = search_movie(name, None)
    
    if not search_result:
        return {"uri": uri, "name": name, "year": year, "found": False}
    
    tmdb_id = search_result["id"]
    
    time.sleep(REQUEST_DELAY)
    details = get_movie_details(tmdb_id)
    time.sleep(REQUEST_DELAY)
    credits = get_movie_credits(tmdb_id)
    
    if not details:
        return {"uri": uri, "name": name, "year": year, "found": False}
    
    result = {
        "uri": uri,
        "name": name,
        "year": year,
        "found": True,
        "tmdb_id": tmdb_id,
        "poster_path": details.get("poster_path"),
        "genres": ",".join([g["name"] for g in details.get("genres", [])]),
        "countries": ",".join([c["iso_3166_1"] for c in details.get("production_countries", [])]),
        "languages": ",".join([l["iso_639_1"] for l in details.get("spoken_languages", [])]),
        "runtime": details.get("runtime"),
        "directors": [],
        "cast": [],
    }
    
    if credits:
        crew = credits.get("crew", [])
        directors = [c for c in crew if c.get("job") == "Director"]
        result["directors"] = [
            {"name": d["name"], "id": d["id"], "photo": d.get("profile_path")}
            for d in directors
        ]
        
        cast = credits.get("cast", [])[:5]
        result["cast"] = [
            {"name": a["name"], "character": a.get("character"), "id": a["id"], "photo": a.get("profile_path"), "order": i}
            for i, a in enumerate(cast)
        ]
    
    return result


def save_result(conn: sqlite3.Connection, result: dict):
    """Save enrichment result to database."""
    uri = result["uri"]
    
    if not result["found"]:
        conn.execute("""
            INSERT OR IGNORE INTO movie_metadata (letterboxd_uri, name, year)
            VALUES (?, ?, ?)
        """, (uri, result["name"], result["year"]))
        return
    
    conn.execute("""
        INSERT OR REPLACE INTO movie_metadata 
        (letterboxd_uri, name, year, tmdb_id, poster_path, genres, countries, languages, runtime)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (uri, result["name"], result["year"], result["tmdb_id"], result["poster_path"], 
          result["genres"], result["countries"], result["languages"], result["runtime"]))
    
    for director in result["directors"]:
        conn.execute("""
            INSERT INTO movie_directors (letterboxd_uri, director_name, director_tmdb_id, director_photo)
            VALUES (?, ?, ?, ?)
        """, (uri, director["name"], director["id"], director.get("photo")))
    
    for actor in result["cast"]:
        conn.execute("""
            INSERT INTO movie_cast 
            (letterboxd_uri, actor_name, character_name, actor_tmdb_id, actor_photo, cast_order)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (uri, actor["name"], actor.get("character"), actor["id"], actor.get("photo"), actor["order"]))


def main():
    """Enrich all movies with TMDB data."""
    if not TMDB_API_KEY:
        print("Error: API_KEY not found in .env.dev")
        return
    
    db_path = Path(__file__).parent.parent / "letterboxd.db"
    if not db_path.exists():
        print("Error: letterboxd.db not found. Run init_db.py first.")
        return
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    lock = threading.Lock()
    
    try:
        create_metadata_tables(conn)
        conn.commit()
        
        movies = get_unique_movies(conn)
        already_done = get_already_enriched(conn)
        
        pending = [m for m in movies if m["uri"] not in already_done]
        
        print(f"Total movies: {len(movies)}")
        print(f"Already enriched: {len(already_done)}")
        print(f"Pending: {len(pending)}")
        print(f"Workers: {MAX_WORKERS}")
        print()
        
        if not pending:
            print("All movies already enriched!")
            return
        
        completed = 0
        found = 0
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(enrich_movie, m): m for m in pending}
            
            for future in as_completed(futures):
                movie = futures[future]
                try:
                    result = future.result()
                    
                    with lock:
                        save_result(conn, result)
                        conn.commit()
                        completed += 1
                        if result and result.get("found"):
                            found += 1
                            print(f"[{completed}/{len(pending)}] ✅ {movie['name']} ({movie['year']})")
                        else:
                            print(f"[{completed}/{len(pending)}] ❌ {movie['name']} ({movie['year']})")
                except Exception as e:
                    print(f"[{completed}/{len(pending)}] ⚠️ {movie['name']} - Error: {e}")
                    completed += 1
        
        elapsed = time.time() - start_time
        print()
        print(f"Done in {elapsed:.1f} seconds!")
        print(f"  - Found: {found}/{len(pending)}")
        
        cursor = conn.execute("SELECT COUNT(DISTINCT director_name) FROM movie_directors")
        print(f"  - Unique directors: {cursor.fetchone()[0]}")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
