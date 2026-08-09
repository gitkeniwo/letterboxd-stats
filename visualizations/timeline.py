"""Viewing timeline and GitHub-style calendar heatmap."""

import sqlite3
from datetime import date, timedelta
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from letterboxd_stats.ui_components import insight, section_header


def get_monthly_counts(conn: sqlite3.Connection, year: int) -> pd.DataFrame:
    data = pd.read_sql_query(
        """
        SELECT strftime('%m', watched_date) AS month, COUNT(*) AS count
        FROM diary WHERE strftime('%Y', watched_date)=?
        GROUP BY month ORDER BY month
        """,
        conn,
        params=(str(year),),
    )
    months = pd.DataFrame({"month": [f"{value:02d}" for value in range(1, 13)]})
    data = months.merge(data, on="month", how="left").fillna(0)
    data["count"] = data["count"].astype(int)
    names = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    data["month_name"] = data["month"].map(lambda value: names[int(value) - 1])
    return data


def get_daily_counts(conn: sqlite3.Connection, year: int) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT watched_date AS date, COUNT(*) AS count
        FROM diary
        WHERE strftime('%Y', watched_date)=? AND watched_date IS NOT NULL
        GROUP BY watched_date
        """,
        conn,
        params=(str(year),),
    )


def _level(count: int) -> int:
    if count <= 0:
        return 0
    return min(count, 4)


def calendar_html(daily_df: pd.DataFrame, year: int) -> str:
    counts = {str(row.date): int(row.count) for row in daily_df.itertuples()}
    first = date(year, 1, 1)
    last = date(year, 12, 31)
    grid_start = first - timedelta(days=first.weekday())
    grid_end = last + timedelta(days=6 - last.weekday())
    weeks = ((grid_end - grid_start).days // 7) + 1
    parts = [
        '<div class="lb-calendar-wrap">',
        f'<div class="lb-calendar-grid" style="grid-template-columns:30px repeat({weeks},12px)">',
    ]
    month_names = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    for month, name in enumerate(month_names, start=1):
        month_start = date(year, month, 1)
        column = ((month_start - grid_start).days // 7) + 2
        parts.append(
            f'<span class="lb-calendar-month" style="grid-column:{column}/span 4;grid-row:1">{name}</span>'
        )
    for label, row in (("Mon", 2), ("Wed", 4), ("Fri", 6)):
        parts.append(
            f'<span class="lb-calendar-day" style="grid-column:1;grid-row:{row}">{label}</span>'
        )
    current = grid_start
    while current <= grid_end:
        week = ((current - grid_start).days // 7) + 2
        row = current.weekday() + 2
        count = counts.get(current.isoformat(), 0) if current.year == year else 0
        muted = " opacity:.3" if current.year != year else ""
        title = f"{current.isoformat()}: {count} film{'s' if count != 1 else ''}"
        parts.append(
            f'<span class="lb-calendar-cell lb-level-{_level(count)}" '
            f'style="grid-column:{week};grid-row:{row};{muted}" title="{escape(title)}"></span>'
        )
        current += timedelta(days=1)
    parts.extend(
        [
            "</div>",
            '<div class="lb-calendar-footer"><span style="width:auto">Less</span>',
            *[f'<span class="lb-level-{level}"></span>' for level in range(5)],
            '<span style="width:auto">More</span></div>',
            "</div>",
        ]
    )
    return "".join(parts)


def render_timeline(conn: sqlite3.Connection, year: int) -> None:
    section_header("Timeline", "chart-line", color="green")
    st.subheader("Monthly Viewing Trend")
    monthly_df = get_monthly_counts(conn, year)
    if monthly_df["count"].sum() > 0:
        chart = (
            alt.Chart(monthly_df)
            .mark_bar(color="#00e054", cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
            .encode(
                x=alt.X("month_name:N", sort=None, title=None),
                y=alt.Y("count:Q", title="Films watched"),
                tooltip=["month_name", "count"],
            )
            .properties(height=260)
            .configure(font="DM Sans")
            .configure_view(strokeOpacity=0)
        )
        st.altair_chart(chart, width="stretch")
    else:
        st.info("No viewing data for this year.")

    section_header("Viewing Calendar", "calendar-days", color="blue", level=3)
    daily_df = get_daily_counts(conn, year)
    if daily_df.empty:
        st.info("No daily viewing data available.")
        return
    st.markdown(calendar_html(daily_df, year), unsafe_allow_html=True)
    most_active = daily_df.loc[daily_df["count"].idxmax()]
    insight(
        f"Most active day: <strong>{escape(str(most_active['date']))}</strong> · "
        f"<strong>{int(most_active['count'])}</strong> films",
        "fire",
        color="orange",
    )
