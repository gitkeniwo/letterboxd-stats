"""Streamlit setup and import workflow."""

from __future__ import annotations

import sqlite3

import streamlit as st

from .config import AppConfig, load_config, save_config
from .database import enrichment_counts, has_diary_data
from .enrichment import EnrichmentProgress, enrich_library
from .importer import InvalidExport, import_export, inspect_export
from .tmdb import TMDBClient, TMDBError
from .ui_components import section_header


def _run_enrichment(conn: sqlite3.Connection, api_key: str) -> None:
    progress_bar = st.progress(0.0, text="Preparing TMDB enrichment…")
    summary_slot = st.empty()

    def update(event: EnrichmentProgress) -> None:
        ratio = event.completed / event.total if event.total else 1.0
        progress_bar.progress(
            ratio,
            text=f"{event.completed}/{event.total} · {event.movie_name or 'Starting'}",
        )
        summary_slot.caption(f"Matched: {event.found} · Failed: {event.failed}")

    result = enrich_library(conn, api_key, update)
    progress_bar.progress(1.0, text="TMDB enrichment finished")
    st.success(
        f"Finished: {result.found} matched, {result.failed} failed. "
        "Unmatched films can be corrected in Data Management."
    )


def render_setup(conn: sqlite3.Connection) -> None:
    has_data = has_diary_data(conn)
    config = load_config()

    section_header("Set up Letterboxd Stats", "clapperboard", color="blue", level=1)
    st.write(
        "Upload the original ZIP from Letterboxd. Your viewing history and TMDB key "
        "stay on this computer."
    )

    uploaded = st.file_uploader("Letterboxd export ZIP", type=["zip"])
    export_bytes: bytes | None = None
    if uploaded is not None:
        export_bytes = uploaded.getvalue()
        try:
            summary = inspect_export(export_bytes)
            years = (
                f"{summary.first_year}–{summary.last_year}"
                if summary.first_year and summary.last_year
                else "Unknown"
            )
            st.success(
                f"Valid export · {summary.diary_count:,} diary entries · "
                f"years {years}"
                + (f" · @{summary.username}" if summary.username else "")
            )
        except InvalidExport as exc:
            st.error(str(exc))
            export_bytes = None

    api_key = st.text_input(
        "TMDB API key",
        value=config.tmdb_api_key,
        type="password",
        help="Required for posters, directors, cast, genres, countries, and runtime.",
    ).strip()

    counts = enrichment_counts(conn) if has_data else {"remaining": 0}
    action_label = (
        "Import and build dashboard" if export_bytes else "Validate key and resume"
    )
    action_disabled = not api_key or (not has_data and export_bytes is None)

    if st.button(action_label, type="primary", disabled=action_disabled):
        try:
            with st.spinner("Validating TMDB API key…"):
                TMDBClient(api_key).validate_key()
            save_config(AppConfig(tmdb_api_key=api_key))
            if export_bytes is not None:
                with st.spinner("Importing Letterboxd data…"):
                    summary = import_export(conn, export_bytes)
                st.success(f"Imported {summary.diary_count:,} diary entries.")
            _run_enrichment(conn, api_key)
            st.session_state["skip_setup"] = True
            st.rerun()
        except (TMDBError, InvalidExport) as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001 - setup is the application error boundary
            st.error(f"Setup could not finish: {exc}")

    if has_data:
        st.caption(
            f"Existing library found. {counts.get('remaining', 0)} films still need enrichment."
        )
        if config.tmdb_api_key and st.button("View current dashboard"):
            st.session_state["skip_setup"] = True
            st.rerun()
