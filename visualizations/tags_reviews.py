"""
Tags & Reviews Module - 标签词云和影评统计
"""
import sqlite3
import streamlit as st
import pandas as pd
from io import BytesIO
from collections import Counter


def get_tags_data(conn: sqlite3.Connection, year: int) -> list[str]:
    """Get all tags for a specific year."""
    cursor = conn.execute("""
        SELECT tags FROM diary 
        WHERE strftime('%Y', watched_date) = ?
          AND tags IS NOT NULL AND tags != ''
    """, (str(year),))
    
    all_tags = []
    for row in cursor:
        # Tags are comma-separated
        tags = row[0].split(",")
        all_tags.extend([t.strip() for t in tags if t.strip()])
    
    return all_tags


def get_review_stats(conn: sqlite3.Connection, year: int) -> dict:
    """Get review statistics for a specific year."""
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total_reviews,
            SUM(LENGTH(review)) as total_chars
        FROM reviews 
        WHERE strftime('%Y', watched_date) = ?
          AND review IS NOT NULL AND review != ''
    """, (str(year),))
    row = cursor.fetchone()
    
    return {
        "total_reviews": row[0] or 0,
        "total_chars": row[1] or 0,
    }


def get_longest_reviews(conn: sqlite3.Connection, year: int, limit: int = 5) -> pd.DataFrame:
    """Get longest reviews for a specific year."""
    df = pd.read_sql_query("""
        SELECT 
            name,
            rating,
            LENGTH(review) as review_length,
            SUBSTR(review, 1, 100) as preview
        FROM reviews 
        WHERE strftime('%Y', watched_date) = ?
          AND review IS NOT NULL AND review != ''
        ORDER BY LENGTH(review) DESC
        LIMIT ?
    """, conn, params=(str(year), limit))
    
    return df


def render_tags_reviews(conn: sqlite3.Connection, year: int):
    """Render tags and reviews section."""
    st.header("🏷️ Tags & Reviews")
    
    col1, col2 = st.columns(2)
    
    # Tag cloud
    with col1:
        st.subheader("Popular Tags")
        tags = get_tags_data(conn, year)
        
        if tags:
            tag_counts = Counter(tags)
            top_tags = tag_counts.most_common(15)
            
            # Display as tag pills
            tag_html = " ".join([
                f'<span style="background-color:#333;padding:4px 12px;margin:2px;border-radius:16px;display:inline-block;font-size:14px;">{tag} ({count})</span>'
                for tag, count in top_tags
            ])
            st.markdown(tag_html, unsafe_allow_html=True)
        else:
            st.info("No tags found for this year.")
    
    # Review stats
    with col2:
        st.subheader("Review Stats")
        review_stats = get_review_stats(conn, year)
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric(
                label="📝 Reviews Written",
                value=review_stats["total_reviews"]
            )
        with col_b:
            words = review_stats["total_chars"] // 5  # Rough word estimate
            st.metric(
                label="📖 Est. Words",
                value=f"{words:,}"
            )
        
        # Longest reviews
        if review_stats["total_reviews"] > 0:
            st.subheader("Longest Reviews")
            longest = get_longest_reviews(conn, year)
            
            if not longest.empty:
                for _, row in longest.iterrows():
                    rating_str = f"⭐ {row['rating']}" if pd.notna(row['rating']) else ""
                    st.markdown(f"**{row['name']}** {rating_str}")
                    preview = row['preview'].replace('\n', ' ').replace('\r', ' ')
                    st.caption(f"{preview}... ({row['review_length']} chars)")
