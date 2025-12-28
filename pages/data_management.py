"""
Data Management Page - 数据管理
"""
import os
import sqlite3
from pathlib import Path

import streamlit as st
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env.dev")

TMDB_API_KEY = os.getenv("API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w185"


def get_db_connection():
    """Get database connection."""
    db_path = Path(__file__).parent.parent / "letterboxd.db"
    if not db_path.exists():
        return None
    return sqlite3.connect(db_path)


def get_all_movies(conn: sqlite3.Connection) -> list[dict]:
    """Get all movies with metadata."""
    cursor = conn.execute("""
        SELECT 
            m.letterboxd_uri,
            m.name, 
            m.year, 
            m.tmdb_id,
            m.poster_path,
            m.genres
        FROM movie_metadata m
        ORDER BY m.name
    """)
    return [{"uri": row[0], "name": row[1], "year": row[2], "tmdb_id": row[3], 
             "poster_path": row[4], "genres": row[5]} for row in cursor]


def search_tmdb(query: str, year: int | None = None) -> list[dict]:
    """Search TMDB for movies."""
    if not TMDB_API_KEY:
        return []
    
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "include_adult": "false",
    }
    if year:
        params["year"] = str(year)
    
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{TMDB_BASE_URL}/search/movie", params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])[:10]
    except Exception as e:
        st.error(f"TMDB search error: {e}")
        return []


def get_tmdb_movie_details(tmdb_id: int, media_type: str = "movie") -> dict | None:
    """Get full movie/TV details from TMDB."""
    if not TMDB_API_KEY:
        return None
    
    try:
        with httpx.Client(timeout=10) as client:
            params = {"api_key": TMDB_API_KEY}
            
            # Get details
            resp = client.get(f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}", params=params)
            resp.raise_for_status()
            details = resp.json()
            
            # Get credits
            resp = client.get(f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}/credits", params=params)
            resp.raise_for_status()
            credits = resp.json()
            
            # Normalize TV data to movie format
            if media_type == "tv":
                details["title"] = details.get("name", details.get("original_name"))
                details["release_date"] = details.get("first_air_date", "")
            
            return {"details": details, "credits": credits}
    except Exception as e:
        st.error(f"TMDB details error: {e}")
        return None


def update_movie_metadata(conn: sqlite3.Connection, letterboxd_uri: str, tmdb_data: dict):
    """Update movie metadata with new TMDB data using letterboxd_uri."""
    details = tmdb_data["details"]
    credits = tmdb_data["credits"]
    
    tmdb_id = details["id"]
    poster_path = details.get("poster_path")
    genres = ",".join([g["name"] for g in details.get("genres", [])])
    countries = ",".join([c["iso_3166_1"] for c in details.get("production_countries", [])])
    languages = ",".join([l["iso_639_1"] for l in details.get("spoken_languages", [])])
    runtime = details.get("runtime")
    
    # Update metadata
    conn.execute("""
        UPDATE movie_metadata 
        SET tmdb_id = ?, poster_path = ?, genres = ?, countries = ?, languages = ?, runtime = ?
        WHERE letterboxd_uri = ?
    """, (tmdb_id, poster_path, genres, countries, languages, runtime, letterboxd_uri))
    
    # Delete old directors and cast
    conn.execute("DELETE FROM movie_directors WHERE letterboxd_uri = ?", (letterboxd_uri,))
    conn.execute("DELETE FROM movie_cast WHERE letterboxd_uri = ?", (letterboxd_uri,))
    
    # Insert new directors
    crew = credits.get("crew", [])
    directors = [c for c in crew if c.get("job") == "Director"]
    for director in directors:
        conn.execute("""
            INSERT INTO movie_directors (letterboxd_uri, director_name, director_tmdb_id, director_photo)
            VALUES (?, ?, ?, ?)
        """, (letterboxd_uri, director["name"], director["id"], director.get("profile_path")))
    
    # Insert new cast
    cast = credits.get("cast", [])[:5]
    for i, actor in enumerate(cast):
        conn.execute("""
            INSERT INTO movie_cast 
            (letterboxd_uri, actor_name, character_name, actor_tmdb_id, actor_photo, cast_order)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (letterboxd_uri, actor["name"], actor.get("character"), actor["id"], actor.get("profile_path"), i))
    
    conn.commit()


def main():
    st.set_page_config(page_title="Data Management", page_icon="⚙️", layout="wide")
    
    st.title("⚙️ Data Management")
    st.markdown("Fix incorrect movie posters and metadata")
    
    conn = get_db_connection()
    if conn is None:
        st.error("Database not found.")
        return
    
    try:
        movies = get_all_movies(conn)
        
        if not movies:
            st.warning("No movies found in database.")
            return
        
        # Movie selector
        movie_names = [f"{m['name']} ({m['year']})" for m in movies]
        selected_idx = st.selectbox(
            "Select movie to fix", 
            range(len(movies)), 
            format_func=lambda i: movie_names[i],
            index=None,
            placeholder="Choose a movie..."
        )
        
        if selected_idx is None:
            st.info("Please select a movie to fix.")
            return
        
        selected_movie = movies[selected_idx]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Current Data")
            if selected_movie["poster_path"]:
                st.image(f"{TMDB_IMAGE_BASE}{selected_movie['poster_path']}", width=150)
            else:
                st.markdown("No poster")
            st.markdown(f"**TMDB ID:** {selected_movie['tmdb_id'] or 'None'}")
            st.markdown(f"**Genres:** {selected_movie['genres'] or 'None'}")
        
        with col2:
            st.subheader("Search TMDB for Replacement")
            
            search_query = st.text_input("Search query", value=selected_movie["name"])
            search_year = st.number_input("Year (optional)", value=selected_movie["year"] or 0, min_value=0)
            
            if st.button("🔍 Search TMDB"):
                results = search_tmdb(search_query, search_year if search_year > 0 else None)
                
                if results:
                    st.session_state["tmdb_results"] = results
                else:
                    st.warning("No results found.")
            
            st.markdown("---")
            st.subheader("Or Enter TMDB ID Directly")
            st.caption("Find the ID at themoviedb.org/movie/[ID] or /tv/[ID]")
            
            col_type, col_id = st.columns([1, 2])
            with col_type:
                media_type = st.selectbox("Type", ["movie", "tv"], index=0)
            with col_id:
                direct_tmdb_id = st.number_input("TMDB ID", value=0, min_value=0, step=1)
            
            if st.button("📥 Use This TMDB ID"):
                if direct_tmdb_id > 0:
                    tmdb_data = get_tmdb_movie_details(direct_tmdb_id, media_type)
                    if tmdb_data:
                        # Preview before applying
                        st.image(f"{TMDB_IMAGE_BASE}{tmdb_data['details'].get('poster_path')}", width=100)
                        st.markdown(f"**{tmdb_data['details'].get('title')}** ({tmdb_data['details'].get('release_date', '')[:4]})")
                        
                        if st.button("✅ Confirm Update", key="confirm_direct"):
                            update_movie_metadata(conn, selected_movie["uri"], tmdb_data)
                            st.success(f"Updated {selected_movie['name']}!")
                            st.rerun()
                else:
                    st.warning("Please enter a valid TMDB ID.")
        
        # Show search results
        if "tmdb_results" in st.session_state and st.session_state["tmdb_results"]:
            st.markdown("---")
            st.subheader("Search Results")
            
            results = st.session_state["tmdb_results"]
            cols = st.columns(5)
            
            for i, result in enumerate(results[:5]):
                with cols[i]:
                    if result.get("poster_path"):
                        st.image(f"{TMDB_IMAGE_BASE}{result['poster_path']}", width=120)
                    st.markdown(f"**{result['title']}**")
                    st.caption(f"{result.get('release_date', 'N/A')[:4]}")
                    
                    if st.button(f"Use this", key=f"use_{result['id']}"):
                        # Fetch full details and update
                        tmdb_data = get_tmdb_movie_details(result["id"])
                        if tmdb_data:
                            update_movie_metadata(conn, selected_movie["uri"], tmdb_data)
                            st.success(f"Updated {selected_movie['name']}!")
                            st.session_state["tmdb_results"] = None
                            st.rerun()
    
    finally:
        conn.close()


if __name__ == "__main__":
    main()
