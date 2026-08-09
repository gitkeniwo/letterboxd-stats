from __future__ import annotations

import io
import sqlite3
import zipfile

import pytest

from letterboxd_stats.database import connect, ensure_schema
from letterboxd_stats.importer import InvalidExport, import_export, inspect_export


def export_zip(films: list[tuple[str, str, str]], username: str = "viewer") -> bytes:
    diary = "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date\n"
    diary += "".join(
        f"2025-01-02,{name},{year},{uri},4.5,No,,2025-01-01\n"
        for name, year, uri in films
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("diary.csv", diary)
        archive.writestr(
            "profile.csv",
            f"Date Joined,Username,Given Name,Family Name,Email Address,Location,Website,Bio,Pronoun,Favorite Films\n2020-01-01,{username},,,,,,,,\n",
        )
    return buffer.getvalue()


def test_inspect_and_reimport_preserve_metadata(tmp_path):
    conn = connect(tmp_path / "app.db")
    ensure_schema(conn)
    first = export_zip([("First Film", "2001", "https://boxd.it/first")])
    summary = import_export(conn, first)
    assert summary.diary_count == 1
    assert summary.username == "viewer"
    conn.execute(
        "INSERT INTO movie_metadata(letterboxd_uri,name,year,tmdb_id) VALUES(?,?,?,?)",
        ("https://boxd.it/first", "First Film", 2001, 123),
    )
    conn.commit()

    second = export_zip(
        [
            ("First Film", "2001", "https://boxd.it/first"),
            ("Second Film", "2002", "https://boxd.it/second"),
        ]
    )
    import_export(conn, second)
    assert conn.execute("SELECT COUNT(*) FROM diary").fetchone()[0] == 2
    assert (
        conn.execute(
            "SELECT tmdb_id FROM movie_metadata WHERE letterboxd_uri=?",
            ("https://boxd.it/first",),
        ).fetchone()[0]
        == 123
    )
    assert (
        conn.execute(
            "SELECT status FROM enrichment_status WHERE letterboxd_uri=?",
            ("https://boxd.it/second",),
        ).fetchone()[0]
        == "pending"
    )
    conn.close()


def test_same_export_is_idempotent(tmp_path):
    conn = connect(tmp_path / "app.db")
    data = export_zip([("Film", "2001", "https://boxd.it/film")])
    import_export(conn, data)
    import_export(conn, data)
    assert conn.execute("SELECT COUNT(*) FROM diary").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM import_runs").fetchone()[0] == 1


def test_failed_import_rolls_back_to_previous_snapshot(tmp_path):
    conn = connect(tmp_path / "app.db")
    original = export_zip([("Safe Film", "2001", "https://boxd.it/safe")])
    import_export(conn, original)
    conn.execute(
        """
        CREATE TRIGGER reject_broken BEFORE INSERT ON diary
        WHEN NEW.name='Broken Film'
        BEGIN SELECT RAISE(ABORT, 'simulated failure'); END
        """
    )
    conn.commit()
    broken = export_zip([("Broken Film", "2002", "https://boxd.it/broken")])
    with pytest.raises(sqlite3.IntegrityError):
        import_export(conn, broken)
    assert conn.execute("SELECT name FROM diary").fetchone()[0] == "Safe Film"


def test_rejects_missing_diary_and_unsafe_paths():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("profile.csv", "Username\nviewer\n")
    with pytest.raises(InvalidExport):
        inspect_export(buffer.getvalue())

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../diary.csv", "Name\nBad\n")
    with pytest.raises(InvalidExport):
        inspect_export(buffer.getvalue())
