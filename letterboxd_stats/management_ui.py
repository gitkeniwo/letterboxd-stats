"""Import updates and correct uncertain TMDB matches."""

from __future__ import annotations

import sqlite3

import streamlit as st

from .config import AppConfig, load_config, save_config
from .enrichment import enrich_library, save_tmdb_payload
from .importer import InvalidExport, import_export, inspect_export
from .tmdb import TMDBClient, TMDBError
from .ui_components import section_header

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w185"


def _progress_ui():
    bar = st.progress(0.0)

    def update(event):
        bar.progress(
            event.completed / event.total if event.total else 1.0,
            text=f"{event.completed}/{event.total} · {event.movie_name or 'Preparing'}",
        )

    return update


def _render_import(conn: sqlite3.Connection, api_key: str) -> None:
    st.subheader("Import a newer Letterboxd export")
    uploaded = st.file_uploader("New Letterboxd ZIP", type=["zip"], key="update_export")
    if uploaded is None:
        return
    data = uploaded.getvalue()
    try:
        summary = inspect_export(data)
        st.caption(
            f"{summary.diary_count:,} diary entries · export {summary.export_hash[:10]}"
        )
    except InvalidExport as exc:
        st.error(str(exc))
        return
    if st.button("Import update and enrich new films", type="primary"):
        try:
            import_export(conn, data)
        except Exception as exc:  # noqa: BLE001 - surface workflow failures in the UI
            st.error(f"Import failed; previous Letterboxd data was preserved. {exc}")
            return
        try:
            result = enrich_library(conn, api_key, _progress_ui())
            st.success(
                f"Update complete · {result.found} newly matched · {result.failed} failed"
            )
            st.rerun()
        except Exception as exc:  # noqa: BLE001 - imported data remains safely resumable
            st.warning(
                f"The Letterboxd update was imported, but TMDB enrichment paused: {exc}"
            )


def get_unmatched_movies(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT d.letterboxd_uri, MIN(d.name) name, MIN(d.year) year,
               m.tmdb_id, m.poster_path, e.status
        FROM diary d
        LEFT JOIN movie_metadata m ON m.letterboxd_uri=d.letterboxd_uri
        LEFT JOIN enrichment_status e ON e.letterboxd_uri=d.letterboxd_uri
        WHERE d.letterboxd_uri IS NOT NULL AND d.letterboxd_uri != ''
          AND (m.tmdb_id IS NULL OR e.status IN ('no_match','failed','pending','running'))
        GROUP BY d.letterboxd_uri
        ORDER BY CASE e.status WHEN 'no_match' THEN 0 WHEN 'failed' THEN 1 ELSE 2 END, name
        """
    ).fetchall()


def _render_corrections(conn: sqlite3.Connection, api_key: str) -> None:
    st.subheader("Films that need a manual match")
    movies = get_unmatched_movies(conn)
    if not movies:
        st.success("Every film in the current library has a TMDB match.")
        return
    st.warning(
        f"{len(movies)} films still need attention. Match these manually before reviewing "
        "already matched films. The first unresolved film is selected below."
    )
    if st.button("Retry automatic movie + TV matching"):
        try:
            result = enrich_library(conn, api_key, _progress_ui(), retry_unmatched=True)
            st.success(
                f"Retry finished · {result.found} matched · {result.failed} failed"
            )
            st.rerun()
        except Exception as exc:  # noqa: BLE001 - keep manual review available
            st.error(f"Automatic retry paused: {exc}")
    selected = st.selectbox(
        "Unmatched film",
        options=range(len(movies)),
        format_func=lambda index: (
            f"{movies[index]['name']} ({movies[index]['year'] or '—'}) · {movies[index]['status'] or 'pending'}"
        ),
        index=0,
    )
    if selected is None:
        return
    movie = movies[selected]
    if st.session_state.get("manual_movie_uri") != movie["letterboxd_uri"]:
        st.session_state["manual_movie_uri"] = movie["letterboxd_uri"]
        st.session_state.pop("manual_tmdb_results", None)
    if movie["poster_path"]:
        st.image(f"{TMDB_IMAGE_BASE}{movie['poster_path']}", width=120)
    query = st.text_input("Search title", value=movie["name"])
    year = st.number_input("Release year", min_value=0, value=movie["year"] or 0)
    if st.button("Search TMDB"):
        try:
            st.session_state["manual_tmdb_results"] = TMDBClient(
                api_key
            ).search_media_candidates(query, year or None, limit=10)
        except TMDBError as exc:
            st.error(str(exc))
    results = st.session_state.get("manual_tmdb_results", [])
    if results:
        result_index = st.selectbox(
            "TMDB result",
            range(len(results)),
            format_func=lambda index: (
                f"{results[index].get('title') or results[index].get('name') or 'Unknown'} "
                f"({(results[index].get('release_date') or results[index].get('first_air_date') or '—')[:4]}) "
                f"· {results[index].get('_media_type', 'movie')}"
            ),
        )
        result = results[result_index]
        col1, col2 = st.columns([1, 3])
        with col1:
            if result.get("poster_path"):
                st.image(f"{TMDB_IMAGE_BASE}{result['poster_path']}", width=120)
        with col2:
            result_title = result.get("title") or result.get("name") or "Unknown"
            result_date = (
                result.get("release_date") or result.get("first_air_date") or ""
            )
            st.write(f"**{result_title}**")
            st.caption(
                f"{result_date[:4]} · {result.get('_media_type', 'movie')} · "
                f"confidence {result.get('_match_score', 0):.0%}"
            )
            if st.button("Use selected match"):
                try:
                    payload = TMDBClient(api_key).full_movie_by_id(
                        int(result["id"]), result.get("_media_type", "movie")
                    )
                    with conn:
                        save_tmdb_payload(
                            conn,
                            movie["letterboxd_uri"],
                            movie["name"],
                            movie["year"],
                            payload,
                            manually_corrected=True,
                        )
                    st.session_state.pop("manual_tmdb_results", None)
                    st.success(
                        "Match updated and protected from automatic replacement."
                    )
                    st.rerun()
                except Exception as exc:  # noqa: BLE001 - surface workflow failures in the UI
                    st.error(str(exc))

    st.markdown("**Or use a TMDB ID directly**")
    id_col, type_col = st.columns([2, 1])
    with id_col:
        direct_id = st.number_input("TMDB ID", min_value=0, step=1)
    with type_col:
        media_type = st.selectbox("Type", ["movie", "tv"])
    if st.button("Use TMDB ID", disabled=direct_id <= 0):
        try:
            payload = TMDBClient(api_key).full_movie_by_id(int(direct_id), media_type)
            with conn:
                save_tmdb_payload(
                    conn,
                    movie["letterboxd_uri"],
                    movie["name"],
                    movie["year"],
                    payload,
                    manually_corrected=True,
                )
            st.success("Match updated and protected from automatic replacement.")
            st.rerun()
        except Exception as exc:  # noqa: BLE001 - surface workflow failures in the UI
            st.error(str(exc))


def _render_settings(api_key: str) -> None:
    st.subheader("TMDB settings")
    replacement = st.text_input(
        "TMDB API key", value=api_key, type="password", key="settings_key"
    )
    if st.button("Validate and save key"):
        try:
            TMDBClient(replacement).validate_key()
            save_config(AppConfig(tmdb_api_key=replacement.strip()))
            st.success("TMDB key saved.")
        except TMDBError as exc:
            st.error(str(exc))


def render_management(conn: sqlite3.Connection) -> None:
    api_key = load_config().tmdb_api_key
    if not api_key:
        st.error("A TMDB API key is required. Return to Setup first.")
        return
    title_col, import_col, settings_col = st.columns([6, 1.4, 1.2])
    with title_col:
        section_header("Data Management", "database", color="blue", level=1)
    with import_col, st.popover("Import update", width="stretch"):
        _render_import(conn, api_key)
    with settings_col, st.popover("TMDB settings", width="stretch"):
        _render_settings(api_key)
    _render_corrections(conn, api_key)
