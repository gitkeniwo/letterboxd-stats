"""Legacy multipage entry point for local development."""

import streamlit as st

from letterboxd_stats.database import connect, ensure_schema
from letterboxd_stats.management_ui import render_management
from letterboxd_stats.paths import database_path, migrate_legacy_database

st.set_page_config(page_title="Data Management", layout="wide")
migrate_legacy_database()
connection = connect(database_path())
try:
    ensure_schema(connection)
    render_management(connection)
finally:
    connection.close()
