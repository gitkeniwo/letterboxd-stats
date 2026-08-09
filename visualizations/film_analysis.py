"""
Film Analysis Module - 电影分析图表
"""

import sqlite3

import altair as alt
import pandas as pd
import streamlit as st

from letterboxd_stats.ui_components import insight, metric_card, section_header


def get_rating_distribution(conn: sqlite3.Connection, year: int) -> pd.DataFrame:
    """Get rating distribution for a specific year."""
    df = pd.read_sql_query(
        """
        SELECT 
            rating,
            COUNT(*) as count
        FROM diary 
        WHERE strftime('%Y', watched_date) = ?
          AND rating IS NOT NULL
        GROUP BY rating
        ORDER BY rating
    """,
        conn,
        params=(str(year),),
    )

    # Ensure all ratings from 0.5 to 5 in 0.5 increments
    all_ratings = pd.DataFrame({"rating": [i * 0.5 for i in range(1, 11)]})
    df = all_ratings.merge(df, on="rating", how="left").fillna(0)
    df["count"] = df["count"].astype(int)
    df["rating_str"] = df["rating"].apply(lambda x: f"{x:.1f}")

    return df


def get_decade_distribution(conn: sqlite3.Connection, year: int) -> pd.DataFrame:
    """Get film decade distribution for watched films in a specific year."""
    df = pd.read_sql_query(
        """
        SELECT 
            (year / 10) * 10 as decade,
            COUNT(*) as count
        FROM diary 
        WHERE strftime('%Y', watched_date) = ?
          AND year IS NOT NULL
        GROUP BY decade
        ORDER BY decade
    """,
        conn,
        params=(str(year),),
    )

    if not df.empty:
        df["decade_str"] = df["decade"].apply(lambda x: f"{int(x)}s")

    return df


def get_new_vs_old(conn: sqlite3.Connection, year: int) -> dict:
    """Get new vs old film ratio. New = released within 2 years."""
    cursor = conn.execute(
        """
        SELECT 
            SUM(CASE WHEN (? - year) <= 2 THEN 1 ELSE 0 END) as new_films,
            SUM(CASE WHEN (? - year) > 2 THEN 1 ELSE 0 END) as old_films
        FROM diary 
        WHERE strftime('%Y', watched_date) = ?
          AND year IS NOT NULL
    """,
        (year, year, str(year)),
    )
    row = cursor.fetchone()

    return {
        "new": row[0] or 0,
        "old": row[1] or 0,
    }


def render_film_analysis(conn: sqlite3.Connection, year: int):
    """Render film analysis section."""
    section_header("Film Analysis", "film", color="orange")

    col1, col2 = st.columns(2)

    # Rating distribution
    with col1:
        st.subheader("Rating Distribution")
        rating_df = get_rating_distribution(conn, year)

        if not rating_df.empty and rating_df["count"].sum() > 0:
            chart = (
                alt.Chart(rating_df)
                .mark_bar(color="#00c030")
                .encode(
                    x=alt.X("rating_str:N", sort=None, title="Rating"),
                    y=alt.Y("count:Q", title="Films"),
                    tooltip=["rating_str", "count"],
                )
                .properties(height=250)
                .configure(font="DM Sans")
                .configure_view(strokeOpacity=0)
            )
            st.altair_chart(chart, width="stretch")

            # Most common rating
            top_rating = rating_df.loc[rating_df["count"].idxmax()]
            insight(
                f"Most common rating: <strong>{top_rating['rating_str']}</strong> stars",
                "star",
                color="green",
            )
        else:
            st.info("No rating data for this year.")

    # Decade distribution
    with col2:
        st.subheader("Film Decades")
        decade_df = get_decade_distribution(conn, year)

        if not decade_df.empty:
            chart = (
                alt.Chart(decade_df)
                .mark_bar(color="#40bcf4")
                .encode(
                    x=alt.X("decade_str:N", sort=None, title="Decade"),
                    y=alt.Y("count:Q", title="Films"),
                    tooltip=["decade_str", "count"],
                )
                .properties(height=250)
                .configure(font="DM Sans")
                .configure_view(strokeOpacity=0)
            )
            st.altair_chart(chart, width="stretch")

            # Favorite decade
            top_decade = decade_df.loc[decade_df["count"].idxmax()]
            insight(
                f"Favorite decade: <strong>{top_decade['decade_str']}</strong>",
                "clapperboard",
                color="blue",
            )
        else:
            st.info("No decade data for this year.")

    # New vs Old films
    st.subheader("New vs Classic Films")
    new_old = get_new_vs_old(conn, year)
    total = new_old["new"] + new_old["old"]

    if total > 0:
        col1, col2 = st.columns(2)

        with col1:
            new_pct = (new_old["new"] / total) * 100
            metric_card(
                f"New Releases · {new_pct:.0f}%",
                new_old["new"],
                "bolt",
                color="green",
            )

        with col2:
            old_pct = (new_old["old"] / total) * 100
            metric_card(
                f"Classics · {old_pct:.0f}%",
                new_old["old"],
                "clapperboard",
                color="orange",
            )
    else:
        st.info("No film year data available.")
