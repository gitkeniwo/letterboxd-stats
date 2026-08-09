"""Overview statistics and Letterboxd-style poster cards."""

import sqlite3
from html import escape

import pandas as pd
import streamlit as st

from letterboxd_stats.ui_components import metric_card, section_header, star_label

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w185"
COLS_PER_ROW = 8


def get_year_stats(conn: sqlite3.Connection, year: int) -> dict:
    row = conn.execute(
        """
        SELECT COUNT(*), ROUND(AVG(rating), 2), SUM(rewatch), MAX(rating)
        FROM diary WHERE strftime('%Y', watched_date) = ?
        """,
        (str(year),),
    ).fetchone()
    return {
        "total_films": row[0] or 0,
        "avg_rating": row[1] or 0,
        "rewatches": row[2] or 0,
        "max_rating": row[3] or 0,
    }


def get_top_rated_films_with_posters(
    conn: sqlite3.Connection, year: int, min_rating: float = 4.5
) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT d.name, d.year, d.rating, m.poster_path, d.rewatch,
               m.tmdb_id, e.status AS enrichment_status
        FROM diary d
        LEFT JOIN movie_metadata m ON d.letterboxd_uri=m.letterboxd_uri
        LEFT JOIN enrichment_status e ON d.letterboxd_uri=e.letterboxd_uri
        WHERE strftime('%Y', d.watched_date)=? AND d.rating>=?
        ORDER BY d.rating DESC, d.watched_date DESC
        """,
        conn,
        params=(str(year), min_rating),
    )


def get_rewatched_films(conn: sqlite3.Connection, year: int) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT d.name, d.year, d.rating, m.poster_path, m.tmdb_id,
               e.status AS enrichment_status, COUNT(*) AS watch_count
        FROM diary d
        LEFT JOIN movie_metadata m ON d.letterboxd_uri=m.letterboxd_uri
        LEFT JOIN enrichment_status e ON d.letterboxd_uri=e.letterboxd_uri
        WHERE strftime('%Y', d.watched_date)=? AND d.rewatch=1
        GROUP BY d.letterboxd_uri
        ORDER BY watch_count DESC, d.rating DESC
        """,
        conn,
        params=(str(year),),
    )


def _rewatch_mark(count: int) -> str:
    if count <= 0:
        return ""
    count_text = f"<span>{count}</span>" if count > 1 else ""
    count_class = " has-count" if count > 1 else ""
    return (
        f'<span class="lb-rewatch{count_class}" title="Rewatched">'
        f'<i class="fa-solid fa-arrows-rotate"></i>{count_text}</span>'
    )


def _poster_tooltip(film: dict) -> str:
    title = escape(str(film.get("name", "Unknown")))
    year = escape(str(film.get("year") or "—"))
    return f'<span class="lb-poster-tooltip">{title} ({year})</span>'


def render_missing_poster_card(film: dict, rewatch_count: int = 0) -> None:
    status = film.get("enrichment_status")
    if status == "failed":
        label = "TMDB failed"
    elif status == "no_match" or not film.get("tmdb_id"):
        label = "Needs TMDB match"
    else:
        label = "Matched · no poster"
    st.markdown(
        f'<div class="lb-poster-card">{_poster_tooltip(film)}'
        '<div class="lb-poster-missing"><i class="fa-solid fa-film"></i>'
        f'<div class="lb-title-serif" style="font-size:11px;line-height:1.2">'
        f"{escape(str(film.get('name', 'Unknown')))}</div>"
        f'<div style="font-size:9px;margin-top:5px">{escape(label)}</div></div>'
        f"{_rewatch_mark(rewatch_count)}</div>",
        unsafe_allow_html=True,
    )


def render_film_poster(film: dict, rewatch_count: int | None = None) -> None:
    count = int(
        rewatch_count if rewatch_count is not None else bool(film.get("rewatch"))
    )
    if not film.get("poster_path"):
        render_missing_poster_card(film, count)
        return
    poster_url = f"{TMDB_IMAGE_BASE}{film['poster_path']}"
    st.markdown(
        f'<div class="lb-poster-card">{_poster_tooltip(film)}'
        f'<img src="{escape(poster_url)}" alt="{escape(str(film.get("name", "Film")))}">'
        f"{_rewatch_mark(count)}</div>",
        unsafe_allow_html=True,
    )


def _render_poster_rows(films: list[dict]) -> None:
    for row_start in range(0, len(films), COLS_PER_ROW):
        row_films = films[row_start : row_start + COLS_PER_ROW]
        columns = st.columns(COLS_PER_ROW)
        for index, film in enumerate(row_films):
            with columns[index]:
                render_film_poster(film)


def render_rewatched_films(conn: sqlite3.Connection, year: int) -> None:
    section_header("Rewatched Films", "arrows-rotate", color="blue", level=3)
    films = get_rewatched_films(conn, year).to_dict("records")
    if not films:
        st.info("No rewatched films this year.")
        return
    for row_start in range(0, len(films), COLS_PER_ROW):
        row_films = films[row_start : row_start + COLS_PER_ROW]
        columns = st.columns(COLS_PER_ROW)
        for index, film in enumerate(row_films):
            with columns[index]:
                render_film_poster(film, int(film["watch_count"]))


def render_overview(conn: sqlite3.Connection, year: int) -> None:
    section_header("Year Overview", "chart-column", color="blue")
    stats = get_year_stats(conn, year)
    columns = st.columns(4)
    cards = (
        ("Total Films", stats["total_films"], "film", "orange"),
        (
            "Average Rating",
            f"{stats['avg_rating']:.1f}" if stats["avg_rating"] else "N/A",
            "star",
            "green",
        ),
        ("Rewatches", stats["rewatches"], "arrows-rotate", "blue"),
        ("Est. Watch Time", f"{stats['total_films'] * 2}h", "clock", "orange"),
    )
    for column, (label, value, icon, color) in zip(columns, cards, strict=True):
        with column:
            metric_card(label, value, icon, color=color)

    section_header("Top Rated Films", "trophy", color="orange", level=3)
    top_films = get_top_rated_films_with_posters(conn, year, min_rating=4.5)
    if top_films.empty:
        st.info("No 4.5+ star films found for this year.")
        return
    five_star = top_films[top_films["rating"] == 5.0].to_dict("records")
    four_half = top_films[top_films["rating"] == 4.5].to_dict("records")
    if five_star:
        star_label(5.0, "5 Stars")
        _render_poster_rows(five_star)
    if four_half:
        star_label(4.5, "4.5 Stars")
        _render_poster_rows(four_half)
    render_rewatched_films(conn, year)
