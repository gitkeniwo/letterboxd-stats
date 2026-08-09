"""Streamlit presentation layer for the local application."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from letterboxd_stats.config import load_config
from letterboxd_stats.database import (
    connect,
    enrichment_counts,
    ensure_schema,
    has_diary_data,
)
from letterboxd_stats.management_ui import render_management
from letterboxd_stats.paths import database_path, migrate_legacy_database
from letterboxd_stats.setup_ui import render_setup
from letterboxd_stats.ui_components import metric_card, section_header
from visualizations.directors import render_directors
from visualizations.film_analysis import render_film_analysis
from visualizations.genres_countries import render_genres_countries
from visualizations.overview import render_overview
from visualizations.tags_reviews import render_tags_reviews
from visualizations.timeline import render_timeline

STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=PT+Serif:wght@400;700&display=swap');
@import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css');
:root {
  --font-serif:'PT Serif',Georgia,serif; --font-sans:'DM Sans',sans-serif;
  --lb-bg:#14181c; --lb-nav:#0d1117; --lb-card:#1b2228; --lb-line:#2c3440;
  --lb-text:#9ab; --lb-white:#fff; --lb-orange:#ff8000; --lb-green:#00e054; --lb-blue:#40bcf4;
}
html,body,[class*="st-"] { font-family:var(--font-sans) !important; }
[data-testid="stIconMaterial"] { font-family:"Material Symbols Rounded","Material Symbols Outlined" !important; }
.stApp { background:radial-gradient(circle at 50% 0,#202b34 0,var(--lb-bg) 36rem); color:var(--lb-text); }
h1 { color:var(--lb-white) !important; font-weight:500 !important; }
h2,h3 { color:var(--lb-text) !important; text-transform:uppercase; letter-spacing:1.7px; font-weight:700 !important; }
.lb-title-serif { font-family:var(--font-serif) !important; font-weight:700 !important; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#0b1014,var(--lb-nav)); border-right:1px solid #1f2931; }
[data-testid="stSidebar"] > div:first-child { padding-top:1.6rem; }
hr { border-color:var(--lb-line) !important; }
.lb-brand { display:flex;align-items:center;gap:10px;color:#fff;font-size:1.2rem;font-weight:700;margin:0 0 1.35rem;white-space:nowrap; }
.lb-mark { display:flex;align-items:center;width:44px;flex:0 0 44px; }
.lb-mark span { width:18px;height:18px;border-radius:50%;display:block;margin-right:-5px;mix-blend-mode:screen; }
.lb-mark .orange{background:var(--lb-orange)} .lb-mark .green{background:var(--lb-green)} .lb-mark .blue{background:var(--lb-blue)}
.lb-sidebar-tabs { display:flex;flex-direction:column;gap:4px;margin:0 -0.35rem 1.2rem; }
.lb-sidebar-tab { display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:3px;color:#789;text-decoration:none !important;font-size:.82rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;border-left:3px solid transparent;transition:all .16s ease; }
.lb-sidebar-tab:hover { color:#bcd;background:#182129; }
.lb-sidebar-tab.active { color:#fff;background:#24303a;border-left-color:var(--lb-green); }
.lb-sidebar-tab i { width:15px;color:#789; } .lb-sidebar-tab.active i { color:var(--lb-green); }
.lb-sidebar-tabs a.lb-sidebar-tab:not(.active) { color:#789 !important; }
.lb-section-title { display:flex;align-items:center;gap:10px;font-size:1.25rem !important;margin:1.3rem 0 .8rem !important; }
h1.lb-section-title { color:#fff !important;font-size:2.35rem !important;text-transform:none;letter-spacing:-.5px;font-weight:500 !important;margin-top:.35rem !important; }
.lb-section-title i { width:1.2em;flex:0 0 1.2em;text-align:center; }
.lb-metric-card { background:linear-gradient(145deg,#1d252c,#192027);padding:16px 18px;border-radius:4px;border:1px solid #25313a;min-height:105px;box-shadow:0 8px 18px #0002; }
.lb-metric-label { display:flex;align-items:center;gap:9px;color:#89a;font-size:.7rem;text-transform:uppercase;letter-spacing:1.2px;font-weight:700; }
.lb-metric-value { color:#fff;font-family:var(--font-serif);font-size:2rem;font-weight:700;margin-top:9px;line-height:1; }
.lb-insight { display:flex;gap:7px;align-items:center;color:#789;font-size:.78rem;margin:.3rem 0; }
.lb-rating-label { display:flex;align-items:center;gap:8px;color:#9ab;font-weight:700;margin:.65rem 0; }
.lb-rating-label > span { color:var(--lb-green);letter-spacing:2px; }
.lb-poster-card { position:relative;width:100%;height:auto;aspect-ratio:2/3;border-radius:4px;transition:transform .18s ease,box-shadow .18s ease; }
.stHorizontalBlock:has(.lb-poster-card) { gap:12px !important;margin-bottom:16px; }
.lb-poster-card img { width:100%;height:100%;object-fit:cover;border-radius:4px;display:block;box-sizing:border-box;transition:border-color .18s ease,filter .18s ease; }
.lb-poster-card:hover { transform:translateY(-3px) scale(1.025);z-index:5;box-shadow:0 8px 20px #0009; }
.lb-poster-card:hover img,.lb-poster-card:hover .lb-poster-missing { border:3px solid #fff; }
.lb-poster-tooltip { pointer-events:none;position:absolute;z-index:6;left:50%;bottom:calc(100% + 9px);transform:translate(-50%,5px);opacity:0;background:#526578;color:#d9e5ef;font-family:var(--font-serif);font-weight:700;font-size:.72rem;white-space:nowrap;padding:6px 9px;border-radius:4px;transition:opacity .16s ease,transform .16s ease;box-shadow:0 4px 12px #0007; }
.lb-poster-tooltip:after { content:"";position:absolute;left:50%;top:100%;margin-left:-6px;border:6px solid transparent;border-top-color:#526578; }
.lb-poster-card:hover .lb-poster-tooltip { opacity:1;transform:translate(-50%,0); }
.lb-rewatch { position:absolute;right:5px;bottom:5px;display:flex;align-items:center;gap:3px;background:#10161ccc;color:#789;border:1px solid #60708055;border-radius:50%;width:22px;height:22px;justify-content:center;font-size:.62rem;box-shadow:0 2px 5px #0008; }
.lb-rewatch.has-count { width:auto;border-radius:11px;padding:0 6px; }
.lb-poster-missing { width:100%;height:100%;box-sizing:border-box;border:1px dashed #52606d;border-radius:4px;background:#1b2228;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:8px;color:#9ab;transition:border-color .18s ease; }
.lb-poster-missing i { color:var(--lb-blue);font-size:1.25rem;margin-bottom:6px; }
.lb-calendar-wrap { overflow-x:auto;padding:4px 2px 8px; }
.lb-calendar-grid { display:grid;grid-template-columns:30px repeat(53,12px);grid-template-rows:20px repeat(7,12px);gap:3px;width:max-content; }
.lb-calendar-month,.lb-calendar-day { color:#9ab;font-size:.65rem;line-height:12px; }
.lb-calendar-cell { width:12px;height:12px;border-radius:2px;outline:1px solid #ffffff08;transition:transform .1s ease,outline-color .1s ease; }
.lb-calendar-cell:hover { transform:scale(1.25);outline-color:#ffffff88;z-index:2; }
.lb-level-0{background:#161b22}.lb-level-1{background:#0e4429}.lb-level-2{background:#006d32}.lb-level-3{background:#26a641}.lb-level-4{background:#39d353}
.lb-calendar-footer { display:flex;justify-content:flex-end;align-items:center;gap:5px;color:#789;font-size:.68rem;margin-top:7px; }
.lb-calendar-footer span { width:11px;height:11px;border-radius:2px;display:inline-block; }
div[data-testid="stSelectbox"] label { color:#89a !important;text-transform:uppercase;letter-spacing:1px;font-size:.68rem; }
@media (max-width:1100px) {
  .stHorizontalBlock:has(.lb-poster-card) { display:grid !important;grid-template-columns:repeat(5,minmax(0,1fr));gap:16px 12px !important; }
  .stHorizontalBlock:has(.lb-poster-card) > [data-testid="stColumn"] { width:auto !important;min-width:0 !important;flex:none !important; }
}
@media (max-width:640px) {
  .stHorizontalBlock:has(.lb-poster-card) { grid-template-columns:repeat(3,minmax(0,1fr)); }
  .lb-poster-tooltip { max-width:150px;white-space:normal;text-align:center; }
}
</style>
"""


def _years(conn) -> list[int]:
    rows = conn.execute(
        "SELECT DISTINCT strftime('%Y', watched_date) year FROM diary "
        "WHERE watched_date IS NOT NULL ORDER BY year DESC"
    ).fetchall()
    return [int(row[0]) for row in rows if row[0]]


def _render_dashboard(conn) -> None:
    years = _years(conn)
    if not years:
        st.warning("No diary entries with viewing dates were found.")
        return
    with st.sidebar:
        page = st.query_params.get("page", "dashboard")
        if page not in {"dashboard", "data"}:
            page = "dashboard"
        st.markdown(
            '<div class="lb-brand"><span class="lb-mark"><span class="orange"></span>'
            '<span class="green"></span><span class="blue"></span></span>'
            "<span>Letterboxd Stats</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<nav class="lb-sidebar-tabs">'
            f'<a target="_self" class="lb-sidebar-tab {"active" if page == "dashboard" else ""}" href="?page=dashboard">'
            '<i class="fa-solid fa-chart-simple"></i><span>Dashboard</span></a>'
            f'<a target="_self" class="lb-sidebar-tab {"active" if page == "data" else ""}" href="?page=data">'
            '<i class="fa-solid fa-database"></i><span>Data Management</span></a></nav>',
            unsafe_allow_html=True,
        )
        st.divider()
        current_year = datetime.now(UTC).astimezone().year
        default = current_year if current_year in years else years[0]
        selected_year = st.selectbox("Select Year", years, index=years.index(default))
        total, average = conn.execute(
            "SELECT COUNT(*), ROUND(AVG(rating),2) FROM diary"
        ).fetchone()
        metric_card("Total Films", total or 0, "film", color="orange")
        metric_card("Average Rating", f"{average or 0:.1f}", "star", color="green")
        counts = enrichment_counts(conn)
        st.caption(
            f"TMDB: {counts.get('success', 0)}/{counts.get('total', 0)} matched"
            + (
                f" · {counts.get('no_match', 0)} need review"
                if counts.get("no_match")
                else ""
            )
        )
    if page == "data":
        render_management(conn)
        return

    section_header(
        f"{selected_year} Year Wrapped", "clapperboard", color="blue", level=1
    )
    render_overview(conn, selected_year)
    st.divider()
    render_timeline(conn, selected_year)
    st.divider()
    render_film_analysis(conn, selected_year)
    st.divider()
    render_directors(conn, selected_year)
    st.divider()
    render_genres_countries(conn, selected_year)
    st.divider()
    render_tags_reviews(conn, selected_year)


def main() -> None:
    st.set_page_config(page_title="Letterboxd Year Wrapped", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)
    migrate_legacy_database()
    conn = connect(database_path())
    try:
        ensure_schema(conn)
        has_data = has_diary_data(conn)
        config = load_config()
        remaining = enrichment_counts(conn).get("remaining", 0) if has_data else 0
        needs_setup = not has_data or not config.tmdb_api_key or remaining > 0
        if needs_setup and not st.session_state.get("skip_setup", False):
            render_setup(conn)
        else:
            _render_dashboard(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
