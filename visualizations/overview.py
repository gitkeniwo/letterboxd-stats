"""
Overview Stats Module - 统计概览卡片
"""
import sqlite3
import streamlit as st
import pandas as pd

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w185"


def film_caption(name: str):
    """Render film name with single-line ellipsis style."""
    st.markdown(
        f'<p style="font-size:0.7rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:100px; margin:0; font-family:var(--font-serif); font-weight:700;" title="{name}">{name}</p>',
        unsafe_allow_html=True
    )


def get_year_stats(conn: sqlite3.Connection, year: int) -> dict:
    """Get statistics for a specific year."""
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total_films,
            ROUND(AVG(rating), 2) as avg_rating,
            SUM(rewatch) as rewatches,
            MAX(rating) as max_rating
        FROM diary 
        WHERE strftime('%Y', watched_date) = ?
    """, (str(year),))
    row = cursor.fetchone()
    
    return {
        "total_films": row[0] or 0,
        "avg_rating": row[1] or 0,
        "rewatches": row[2] or 0,
        "max_rating": row[3] or 0,
    }


def get_top_rated_films_with_posters(conn: sqlite3.Connection, year: int, min_rating: float = 4.5) -> pd.DataFrame:
    """Get top rated films (4.5+ stars) with poster info."""
    df = pd.read_sql_query("""
        SELECT 
            d.name, 
            d.year, 
            d.rating, 
            m.poster_path
        FROM diary d
        LEFT JOIN movie_metadata m ON d.letterboxd_uri = m.letterboxd_uri
        WHERE strftime('%Y', d.watched_date) = ?
          AND d.rating >= ?
        ORDER BY d.rating DESC, d.watched_date DESC
    """, conn, params=(str(year), min_rating))
    return df


def render_overview(conn: sqlite3.Connection, year: int):
    """Render overview stats section."""
    st.header("📊 Year Overview")
    
    stats = get_year_stats(conn, year)
    
    # Metric cards row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="🎬 Total Films",
            value=stats["total_films"]
        )
    
    with col2:
        st.metric(
            label="⭐ Average Rating",
            value=f"{stats['avg_rating']:.1f}" if stats['avg_rating'] else "N/A"
        )
    
    with col3:
        st.metric(
            label="🔄 Rewatches",
            value=stats["rewatches"]
        )
    
    with col4:
        # Estimate watch time (avg 2h per film)
        hours = stats["total_films"] * 2
        st.metric(
            label="⏱️ Est. Watch Time",
            value=f"{hours}h"
        )
    
    # Top rated films with posters
    st.subheader("🏆 Top Rated Films")
    top_films = get_top_rated_films_with_posters(conn, year, min_rating=4.5)
    
    if top_films.empty:
        st.info("No 4.5+ star films found for this year.")
        return
    
    # Separate 5-star and 4.5-star films
    five_star = top_films[top_films["rating"] == 5.0].to_dict('records')
    four_half = top_films[top_films["rating"] == 4.5].to_dict('records')
    
    COLS_PER_ROW = 8
    
    # Display 5-star films
    if five_star:
        st.markdown("**⭐⭐⭐⭐⭐ 5 Stars**")
        for row_start in range(0, len(five_star), COLS_PER_ROW):
            row_films = five_star[row_start:row_start + COLS_PER_ROW]
            cols = st.columns(COLS_PER_ROW)
            for i, film in enumerate(row_films):
                with cols[i]:
                    if film["poster_path"]:
                        st.image(f"{TMDB_IMAGE_BASE}{film['poster_path']}", width=100)
    
    # Display 4.5-star films
    if four_half:
        st.markdown("**⭐⭐⭐⭐½ 4.5 Stars**")
        for row_start in range(0, len(four_half), COLS_PER_ROW):
            row_films = four_half[row_start:row_start + COLS_PER_ROW]
            cols = st.columns(COLS_PER_ROW)
            for i, film in enumerate(row_films):
                with cols[i]:
                    if film["poster_path"]:
                        st.image(f"{TMDB_IMAGE_BASE}{film['poster_path']}", width=100)
    
    # Rewatched films
    render_rewatched_films(conn, year)


def get_rewatched_films(conn: sqlite3.Connection, year: int) -> pd.DataFrame:
    """Get rewatched films for a specific year with posters."""
    df = pd.read_sql_query("""
        SELECT 
            d.name, 
            d.year, 
            d.rating,
            m.poster_path,
            COUNT(*) as watch_count
        FROM diary d
        LEFT JOIN movie_metadata m ON d.letterboxd_uri = m.letterboxd_uri
        WHERE strftime('%Y', d.watched_date) = ?
          AND d.rewatch = 1
        GROUP BY d.letterboxd_uri
        ORDER BY watch_count DESC, d.rating DESC
    """, conn, params=(str(year),))
    return df


def render_rewatched_films(conn: sqlite3.Connection, year: int):
    """Render rewatched films poster wall."""
    st.subheader("🔄 Rewatched Films")
    
    rewatched = get_rewatched_films(conn, year).to_dict('records')
    
    if not rewatched:
        st.info("No rewatched films this year.")
        return
    
    COLS_PER_ROW = 8
    
    for row_start in range(0, len(rewatched), COLS_PER_ROW):
        row_films = rewatched[row_start:row_start + COLS_PER_ROW]
        cols = st.columns(COLS_PER_ROW)
        for i, film in enumerate(row_films):
            with cols[i]:
                if film["poster_path"]:
                    st.image(f"{TMDB_IMAGE_BASE}{film['poster_path']}", width=100)
