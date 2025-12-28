"""
Timeline Module - 时间线图表
"""
import sqlite3
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta


def get_monthly_counts(conn: sqlite3.Connection, year: int) -> pd.DataFrame:
    """Get monthly film counts for a specific year."""
    df = pd.read_sql_query("""
        SELECT 
            strftime('%m', watched_date) as month,
            COUNT(*) as count
        FROM diary 
        WHERE strftime('%Y', watched_date) = ?
        GROUP BY strftime('%m', watched_date)
        ORDER BY month
    """, conn, params=(str(year),))
    
    # Ensure all 12 months are present
    all_months = pd.DataFrame({
        "month": [f"{i:02d}" for i in range(1, 13)]
    })
    df = all_months.merge(df, on="month", how="left").fillna(0)
    df["count"] = df["count"].astype(int)
    
    # Convert month number to name
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    df["month_name"] = df["month"].apply(lambda x: month_names[int(x) - 1])
    
    return df


def get_daily_counts(conn: sqlite3.Connection, year: int) -> pd.DataFrame:
    """Get daily film counts for calendar heatmap."""
    df = pd.read_sql_query("""
        SELECT 
            watched_date as date,
            COUNT(*) as count
        FROM diary 
        WHERE strftime('%Y', watched_date) = ?
          AND watched_date IS NOT NULL
        GROUP BY watched_date
    """, conn, params=(str(year),))
    
    return df


def render_timeline(conn: sqlite3.Connection, year: int):
    """Render timeline section."""
    st.header("📈 Timeline")
    
    # Monthly trend chart
    st.subheader("Monthly Viewing Trend")
    monthly_df = get_monthly_counts(conn, year)
    
    if not monthly_df.empty and monthly_df["count"].sum() > 0:
        # Create Altair bar chart for better control
        chart = alt.Chart(monthly_df).mark_bar(color="#00c030").encode(
            x=alt.X("month_name:N", sort=None, title="Month"),
            y=alt.Y("count:Q", title="Films Watched"),
            tooltip=["month_name", "count"]
        ).properties(
            height=300
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No viewing data for this year.")
    
    # Calendar heatmap
    st.subheader("📅 Viewing Calendar")
    daily_df = get_daily_counts(conn, year)
    
    if not daily_df.empty:
        # Create full year date range
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        calendar_df = pd.DataFrame({"date": date_range.strftime("%Y-%m-%d")})
        calendar_df = calendar_df.merge(daily_df, on="date", how="left").fillna(0)
        calendar_df["count"] = calendar_df["count"].astype(int)
        calendar_df["date"] = pd.to_datetime(calendar_df["date"])
        calendar_df["week"] = calendar_df["date"].dt.isocalendar().week
        calendar_df["weekday"] = calendar_df["date"].dt.weekday
        calendar_df["month"] = calendar_df["date"].dt.month
        
        # Altair calendar heatmap
        heatmap = alt.Chart(calendar_df).mark_rect(cornerRadius=2).encode(
            x=alt.X("week:O", title="Week"),
            y=alt.Y("weekday:O", title="Day", 
                   sort=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]),
            color=alt.Color("count:Q",
                           scale=alt.Scale(scheme="greens"),
                           legend=alt.Legend(title="Films")),
            tooltip=[
                alt.Tooltip("date:T", title="Date", format="%Y-%m-%d"),
                alt.Tooltip("count:Q", title="Films Watched")
            ]
        ).properties(
            height=150
        )
        st.altair_chart(heatmap, use_container_width=True)
        
        # Find most active day
        if daily_df["count"].max() > 0:
            most_active = daily_df.loc[daily_df["count"].idxmax()]
            st.caption(f"🔥 Most active day: **{most_active['date']}** with **{int(most_active['count'])}** films")
    else:
        st.info("No daily viewing data available.")
