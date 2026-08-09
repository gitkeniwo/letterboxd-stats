"""Compatibility CLI for importing a Letterboxd ZIP or extracted directory."""

from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path

from letterboxd_stats.database import connect, ensure_schema
from letterboxd_stats.importer import import_export
from letterboxd_stats.paths import database_path


def _zip_directory(directory: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename in (
            "diary.csv",
            "ratings.csv",
            "reviews.csv",
            "watched.csv",
            "watchlist.csv",
            "profile.csv",
        ):
            path = directory / filename
            if path.exists():
                archive.write(path, filename)
    return buffer.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a Letterboxd export")
    parser.add_argument(
        "source", nargs="?", type=Path, help="Export ZIP or extracted directory"
    )
    parser.add_argument("--database", type=Path, default=database_path())
    args = parser.parse_args()
    source = args.source
    if source is None:
        candidates = sorted(Path.cwd().glob("letterboxd-*.zip"))
        if not candidates:
            candidates = sorted(
                path for path in Path.cwd().glob("letterboxd-*") if path.is_dir()
            )
        if not candidates:
            parser.error("No Letterboxd export found; pass a ZIP path explicitly.")
        source = candidates[-1]
    payload = _zip_directory(source) if source.is_dir() else source
    conn = connect(args.database)
    try:
        ensure_schema(conn)
        summary = import_export(conn, payload)
    finally:
        conn.close()
    print(f"Imported {summary.diary_count} diary entries into {args.database}")


if __name__ == "__main__":
    main()
