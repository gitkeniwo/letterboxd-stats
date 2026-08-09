"""
Genres & Countries Module - 类型和国家统计
"""

import sqlite3

import altair as alt
import pandas as pd
import streamlit as st

from letterboxd_stats.ui_components import metric_card, section_header


def get_genre_distribution(conn: sqlite3.Connection, year: int) -> pd.DataFrame:
    """Get genre distribution for a specific year."""
    cursor = conn.execute(
        """
        SELECT m.genres
        FROM movie_metadata m
        JOIN diary d ON m.letterboxd_uri = d.letterboxd_uri
        WHERE strftime('%Y', d.watched_date) = ?
          AND m.genres IS NOT NULL AND m.genres != ''
    """,
        (str(year),),
    )

    genre_counts = {}
    for row in cursor:
        genres = row[0].split(",")
        for genre in genres:
            genre = genre.strip()
            if genre:
                genre_counts[genre] = genre_counts.get(genre, 0) + 1

    df = pd.DataFrame(list(genre_counts.items()), columns=["genre", "count"])
    df = df.sort_values("count", ascending=False).head(15)
    return df


def get_country_distribution(conn: sqlite3.Connection, year: int) -> pd.DataFrame:
    """Get country distribution for a specific year."""
    cursor = conn.execute(
        """
        SELECT m.countries
        FROM movie_metadata m
        JOIN diary d ON m.letterboxd_uri = d.letterboxd_uri
        WHERE strftime('%Y', d.watched_date) = ?
          AND m.countries IS NOT NULL AND m.countries != ''
    """,
        (str(year),),
    )

    country_counts = {}
    for row in cursor:
        countries = row[0].split(",")
        for country in countries:
            country = country.strip()
            if country:
                country_counts[country] = country_counts.get(country, 0) + 1

    df = pd.DataFrame(list(country_counts.items()), columns=["country", "count"])
    df = df.sort_values("count", ascending=False).head(10)
    return df


def get_language_distribution(conn: sqlite3.Connection, year: int) -> pd.DataFrame:
    """Get language distribution for a specific year."""
    cursor = conn.execute(
        """
        SELECT m.languages
        FROM movie_metadata m
        JOIN diary d ON m.letterboxd_uri = d.letterboxd_uri
        WHERE strftime('%Y', d.watched_date) = ?
          AND m.languages IS NOT NULL AND m.languages != ''
    """,
        (str(year),),
    )

    lang_counts = {}
    for row in cursor:
        languages = row[0].split(",")
        for lang in languages:
            lang = lang.strip()
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

    df = pd.DataFrame(list(lang_counts.items()), columns=["language", "count"])
    df = df.sort_values("count", ascending=False).head(10)
    return df


def get_total_runtime(conn: sqlite3.Connection, year: int) -> int:
    """Get total runtime for a specific year."""
    cursor = conn.execute(
        """
        SELECT SUM(m.runtime)
        FROM movie_metadata m
        JOIN diary d ON m.letterboxd_uri = d.letterboxd_uri
        WHERE strftime('%Y', d.watched_date) = ?
          AND m.runtime IS NOT NULL
    """,
        (str(year),),
    )
    result = cursor.fetchone()[0]
    return result or 0


def render_genres_countries(conn: sqlite3.Connection, year: int):
    """Render genres, countries, and languages section."""
    section_header("Genres, Countries & Languages", "earth-americas", color="blue")

    col1, col2, col3 = st.columns(3)

    # Genres
    with col1:
        st.subheader("Genres")
        genre_df = get_genre_distribution(conn, year)

        if not genre_df.empty:
            chart = (
                alt.Chart(genre_df)
                .mark_bar(color="#00c030")
                .encode(
                    x=alt.X("count:Q", title="Films"),
                    y=alt.Y("genre:N", sort="-x", title=""),
                    tooltip=["genre", "count"],
                )
                .properties(height=300)
            )
            st.altair_chart(chart, width="stretch")
        else:
            st.info("No genre data")

    # Countries
    with col2:
        st.subheader("Countries")
        country_df = get_country_distribution(conn, year)

        if not country_df.empty:
            chart = (
                alt.Chart(country_df)
                .mark_bar(color="#40bcf4")
                .encode(
                    x=alt.X("count:Q", title="Films"),
                    y=alt.Y("country:N", sort="-x", title=""),
                    tooltip=["country", "count"],
                )
                .properties(height=300)
            )
            st.altair_chart(chart, width="stretch")
        else:
            st.info("No country data")

    # Languages
    with col3:
        st.subheader("Languages")
        lang_df = get_language_distribution(conn, year)

        if not lang_df.empty:
            chart = (
                alt.Chart(lang_df)
                .mark_bar(color="#ff8000")
                .encode(
                    x=alt.X("count:Q", title="Films"),
                    y=alt.Y("language:N", sort="-x", title=""),
                    tooltip=["language", "count"],
                )
                .properties(height=300)
            )
            st.altair_chart(chart, width="stretch")
        else:
            st.info("No language data")

    # Total runtime
    runtime = get_total_runtime(conn, year)
    if runtime > 0:
        hours = runtime // 60
        days = hours // 24
        remaining_hours = hours % 24
        metric_card(
            "Total Runtime",
            f"{hours} hours ({days}d {remaining_hours}h)",
            "clock",
            color="orange",
        )
