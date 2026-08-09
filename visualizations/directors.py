"""
Directors & Crew Module - 导演统计
"""

import sqlite3
from html import escape

import pandas as pd
import streamlit as st

from letterboxd_stats.ui_components import section_header

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w185"


def get_top_directors(
    conn: sqlite3.Connection, year: int, limit: int = 10
) -> pd.DataFrame:
    """Get most watched directors for a specific year."""
    df = pd.read_sql_query(
        """
        SELECT 
            md.director_name as name,
            md.director_photo as photo,
            COUNT(*) as film_count,
            GROUP_CONCAT(m.name, ', ') as films
        FROM movie_directors md
        JOIN movie_metadata m ON md.letterboxd_uri = m.letterboxd_uri
        JOIN diary di ON di.letterboxd_uri = md.letterboxd_uri
        WHERE strftime('%Y', di.watched_date) = ?
        GROUP BY md.director_name
        ORDER BY film_count DESC, md.director_name
        LIMIT ?
    """,
        conn,
        params=(str(year), limit),
    )
    return df


def get_all_time_top_directors(
    conn: sqlite3.Connection, limit: int = 10
) -> pd.DataFrame:
    """Get most watched directors all-time."""
    df = pd.read_sql_query(
        """
        SELECT 
            md.director_name as name,
            md.director_photo as photo,
            COUNT(*) as film_count
        FROM movie_directors md
        JOIN diary di ON di.letterboxd_uri = md.letterboxd_uri
        GROUP BY md.director_name
        ORDER BY film_count DESC
        LIMIT ?
    """,
        conn,
        params=(limit,),
    )
    return df


def render_directors(conn: sqlite3.Connection, year: int):
    """Render directors section."""
    section_header("Directors", "video", color="orange")

    directors_df = get_top_directors(conn, year, limit=10)

    if directors_df.empty:
        st.info(
            "No director data available for this year. Run the enrichment script first."
        )
        return

    # Display as two rows of 5
    directors_list = directors_df.to_dict("records")

    # First row (0-4)
    cols1 = st.columns(5)
    for i, director in enumerate(directors_list[:5]):
        with cols1[i]:
            if director["photo"]:
                st.image(f"{TMDB_IMAGE_BASE}{director['photo']}", width=120)
            else:
                st.markdown(
                    '<div class="lb-poster-missing" style="width:120px;height:120px">'
                    '<i class="fa-solid fa-user"></i><span>No photo</span></div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                f'<span class="lb-title-serif">{escape(director["name"])}</span>',
                unsafe_allow_html=True,
            )
            st.caption(f"{director['film_count']} films")

    # Second row (5-9)
    if len(directors_list) > 5:
        cols2 = st.columns(5)
        for i, director in enumerate(directors_list[5:10]):
            with cols2[i]:
                if director["photo"]:
                    st.image(f"{TMDB_IMAGE_BASE}{director['photo']}", width=120)
                else:
                    st.markdown(
                        '<div class="lb-poster-missing" style="width:120px;height:120px">'
                        '<i class="fa-solid fa-user"></i><span>No photo</span></div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(
                    f'<span class="lb-title-serif">{escape(director["name"])}</span>',
                    unsafe_allow_html=True,
                )
                st.caption(f"{director['film_count']} films")

    # Show films list in expander
    with st.expander("View all directors' films"):
        for _, row in directors_df.iterrows():
            st.markdown(
                f'<span class="lb-title-serif">{escape(row["name"])}</span> '
                f"({row['film_count']}): "
                f'<span class="lb-title-serif">{escape(row["films"] or "")}</span>',
                unsafe_allow_html=True,
            )
