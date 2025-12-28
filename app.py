"""
Letterboxd Stats - Year Wrapped
"""
import sqlite3
from pathlib import Path
from datetime import datetime

import streamlit as st

from visualizations.overview import render_overview
from visualizations.timeline import render_timeline
from visualizations.film_analysis import render_film_analysis
from visualizations.tags_reviews import render_tags_reviews
from visualizations.directors import render_directors
from visualizations.genres_countries import render_genres_countries


# Page config
st.set_page_config(
    page_title="Letterboxd Year Wrapped",
    page_icon="🎬",
    layout="wide"
)

# Custom CSS for Letterboxd style
st.markdown("""
<style>
    /* Import Google Font - PT Serif for titles */
    @import url('https://fonts.googleapis.com/css2?family=PT+Serif:wght@400;700&display=swap');
    
    /* CSS Variables for easy customization */
    :root {
        --font-serif: 'PT Serif', Georgia, serif;
        --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        --color-bg: #14181c;
        --color-bg-card: #1b2228;
        --color-accent: #00c030;
        --color-text: #9ab;
        --color-text-white: #fff;
    }
    
    /* Metric cards */
    .stMetric {
        background-color: var(--color-bg-card);
        padding: 16px;
        border-radius: 4px;
    }
    .stMetric label {
        color: #89a !important;
        font-size: 11px !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .stMetric [data-testid="stMetricValue"],
    .stMetric [data-testid="stMetricValue"] > div,
    [data-testid="stMetricValue"] {
        color: var(--color-text-white) !important;
        font-weight: 700 !important;
        font-family: var(--font-serif) !important;
        font-size: 2rem !important;
    }
    
    /* Headers */
    h1 {
        color: var(--color-text-white) !important;
        font-weight: 400 !important;
    }
    h2 {
        color: var(--color-text) !important;
        font-size: 1.5rem !important;
        text-transform: uppercase;
        letter-spacing: 2px;
        font-weight: 700 !important;
    }
    h3 {
        color: var(--color-text) !important;
        font-size: 1.2rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Film titles and director names - bold serif */
    .stMarkdown strong, .stMarkdown b {
        font-family: var(--font-serif) !important;
        font-weight: 700;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0d1117;
    }
    [data-testid="stSidebar"] h1 {
        color: var(--color-accent) !important;
    }
    
    /* Tables */
    .stDataFrame {
        border-radius: 4px;
    }
    
    /* Poster wall captions - smaller, single line with ellipsis */
    .stImage + div .stCaption,
    .element-container:has(.stImage) + .element-container .stCaption {
        font-size: 0.7rem !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 100px;
    }
    
    /* Dividers */
    hr {
        border-color: #2c3440 !important;
    }
</style>
""", unsafe_allow_html=True)


def get_db_connection():
    """Get database connection."""
    db_path = Path(__file__).parent / "letterboxd.db"
    if not db_path.exists():
        return None
    return sqlite3.connect(db_path)


def get_available_years(conn: sqlite3.Connection) -> list[int]:
    """Get list of years with viewing data."""
    cursor = conn.execute("""
        SELECT DISTINCT strftime('%Y', watched_date) as year
        FROM diary
        WHERE watched_date IS NOT NULL
        ORDER BY year DESC
    """)
    return [int(row[0]) for row in cursor if row[0]]


def get_total_stats(conn: sqlite3.Connection) -> dict:
    """Get all-time stats for sidebar."""
    cursor = conn.execute("""
        SELECT COUNT(*), ROUND(AVG(rating), 2)
        FROM diary
    """)
    row = cursor.fetchone()
    return {"total": row[0] or 0, "avg_rating": row[1] or 0}


def main():
    conn = get_db_connection()
    
    if conn is None:
        st.error("Database not found. Please run `uv run python db/init_db.py` first.")
        st.code("uv run python db/init_db.py", language="bash")
        return
    
    try:
        available_years = get_available_years(conn)
        
        if not available_years:
            st.warning("No viewing data found in the database.")
            return
        
        # Sidebar
        with st.sidebar:
            st.title("🎬 Letterboxd Stats")
            st.markdown("---")
            
            # Year selector
            current_year = datetime.now().year
            default_year = current_year if current_year in available_years else available_years[0]
            
            selected_year = st.selectbox(
                "📅 Select Year",
                options=available_years,
                index=available_years.index(default_year) if default_year in available_years else 0
            )
            
            st.markdown("---")
            
            # All-time stats
            st.subheader("All-Time Stats")
            total_stats = get_total_stats(conn)
            st.metric("Total Films", total_stats["total"])
            st.metric("Average Rating", f"{total_stats['avg_rating']:.1f} ⭐")
            
            st.markdown("---")
            st.caption("Data from Letterboxd export")
        
        # Main content
        st.title(f"📽️ {selected_year} Year Wrapped")
        
        # Render all sections
        render_overview(conn, selected_year)
        st.markdown("---")
        
        render_timeline(conn, selected_year)
        st.markdown("---")
        
        render_film_analysis(conn, selected_year)
        st.markdown("---")
        
        render_directors(conn, selected_year)
        st.markdown("---")
        
        render_genres_countries(conn, selected_year)
        st.markdown("---")
        
        render_tags_reviews(conn, selected_year)
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
