"""Safe, transactional import of a Letterboxd export ZIP."""

from __future__ import annotations

import csv
import hashlib
import io
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from .database import ensure_schema

MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
SNAPSHOT_TABLES = ("diary", "ratings", "reviews", "watched", "watchlist", "profile")


class InvalidExport(ValueError):
    pass


@dataclass(frozen=True)
class ExportSummary:
    export_hash: str
    username: str
    diary_count: int
    first_year: int | None
    last_year: int | None


def _read_source(source: bytes | bytearray | Path | BinaryIO) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, Path):
        return source.read_bytes()
    source.seek(0)
    return source.read()


def _member_map(archive: zipfile.ZipFile) -> dict[str, str]:
    safe_files: list[str] = []
    total_size = 0
    for info in archive.infolist():
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts:
            raise InvalidExport("The ZIP contains an unsafe file path.")
        total_size += info.file_size
        if not info.is_dir():
            safe_files.append(info.filename)
    if total_size > MAX_UNCOMPRESSED_BYTES:
        raise InvalidExport("The uncompressed export is unexpectedly large.")

    result: dict[str, str] = {}
    for filename in (
        "diary.csv",
        "ratings.csv",
        "reviews.csv",
        "watched.csv",
        "watchlist.csv",
        "profile.csv",
    ):
        candidates = [
            name
            for name in safe_files
            if PurePosixPath(name).name == filename
            and "deleted" not in PurePosixPath(name).parts
            and "orphaned" not in PurePosixPath(name).parts
        ]
        if candidates:
            result[filename] = min(
                candidates, key=lambda name: len(PurePosixPath(name).parts)
            )
    if "diary.csv" not in result:
        raise InvalidExport(
            "This does not look like a Letterboxd export: diary.csv is missing."
        )
    return result


def _rows(archive: zipfile.ZipFile, member: str):
    with (
        archive.open(member) as raw,
        io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text,
    ):
        yield from csv.DictReader(text)


def _date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        return None


def _integer(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _rating(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _boolean(value: str | None) -> int:
    return int(bool(value) and value.lower() in {"yes", "true", "1"})


def inspect_export(source: bytes | bytearray | Path | BinaryIO) -> ExportSummary:
    data = _read_source(source)
    digest = hashlib.sha256(data).hexdigest()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = _member_map(archive)
            diary = list(_rows(archive, members["diary.csv"]))
            profile = (
                list(_rows(archive, members["profile.csv"]))
                if "profile.csv" in members
                else []
            )
    except zipfile.BadZipFile as exc:
        raise InvalidExport("The uploaded file is not a valid ZIP archive.") from exc
    years = [
        _integer(row.get("Watched Date", "")[:4])
        for row in diary
        if row.get("Watched Date")
    ]
    valid_years = [year for year in years if year is not None]
    return ExportSummary(
        export_hash=digest,
        username=profile[0].get("Username", "") if profile else "",
        diary_count=len(diary),
        first_year=min(valid_years) if valid_years else None,
        last_year=max(valid_years) if valid_years else None,
    )


def import_export(
    conn: sqlite3.Connection, source: bytes | bytearray | Path | BinaryIO
) -> ExportSummary:
    data = _read_source(source)
    summary = inspect_export(data)
    ensure_schema(conn)
    previous = conn.execute(
        "SELECT 1 FROM import_runs WHERE export_hash=? AND status='success' LIMIT 1",
        (summary.export_hash,),
    ).fetchone()
    if (
        previous
        and conn.execute("SELECT EXISTS(SELECT 1 FROM diary LIMIT 1)").fetchone()[0]
    ):
        return summary
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = _member_map(archive)
        try:
            conn.execute("BEGIN IMMEDIATE")
            for table in SNAPSHOT_TABLES:
                conn.execute(f"DELETE FROM {table}")

            if "diary.csv" in members:
                values = [
                    (
                        _date(r.get("Date")),
                        r.get("Name", ""),
                        _integer(r.get("Year")),
                        r.get("Letterboxd URI", ""),
                        _rating(r.get("Rating")),
                        _boolean(r.get("Rewatch")),
                        r.get("Tags", ""),
                        _date(r.get("Watched Date")),
                    )
                    for r in _rows(archive, members["diary.csv"])
                ]
                conn.executemany(
                    "INSERT INTO diary(date,name,year,letterboxd_uri,rating,rewatch,tags,watched_date) VALUES(?,?,?,?,?,?,?,?)",
                    values,
                )
            if "ratings.csv" in members:
                values = [
                    (
                        _date(r.get("Date")),
                        r.get("Name", ""),
                        _integer(r.get("Year")),
                        r.get("Letterboxd URI", ""),
                        _rating(r.get("Rating")),
                    )
                    for r in _rows(archive, members["ratings.csv"])
                ]
                conn.executemany(
                    "INSERT INTO ratings(date,name,year,letterboxd_uri,rating) VALUES(?,?,?,?,?)",
                    values,
                )
            if "reviews.csv" in members:
                values = [
                    (
                        _date(r.get("Date")),
                        r.get("Name", ""),
                        _integer(r.get("Year")),
                        r.get("Letterboxd URI", ""),
                        _rating(r.get("Rating")),
                        _boolean(r.get("Rewatch")),
                        r.get("Review", ""),
                        r.get("Tags", ""),
                        _date(r.get("Watched Date")),
                    )
                    for r in _rows(archive, members["reviews.csv"])
                ]
                conn.executemany(
                    "INSERT INTO reviews(date,name,year,letterboxd_uri,rating,rewatch,review,tags,watched_date) VALUES(?,?,?,?,?,?,?,?,?)",
                    values,
                )
            for filename, table in (
                ("watched.csv", "watched"),
                ("watchlist.csv", "watchlist"),
            ):
                if filename in members:
                    values = [
                        (
                            _date(r.get("Date")),
                            r.get("Name", ""),
                            _integer(r.get("Year")),
                            r.get("Letterboxd URI", ""),
                        )
                        for r in _rows(archive, members[filename])
                    ]
                    conn.executemany(
                        f"INSERT INTO {table}(date,name,year,letterboxd_uri) VALUES(?,?,?,?)",
                        values,
                    )
            if "profile.csv" in members:
                values = [
                    (
                        _date(r.get("Date Joined")),
                        r.get("Username", ""),
                        r.get("Given Name", ""),
                        r.get("Family Name", ""),
                        r.get("Email Address", ""),
                        r.get("Location", ""),
                        r.get("Website", ""),
                        r.get("Bio", ""),
                        r.get("Pronoun", ""),
                        r.get("Favorite Films", ""),
                    )
                    for r in _rows(archive, members["profile.csv"])
                    if r.get("Username")
                ]
                conn.executemany(
                    "INSERT INTO profile(date_joined,username,given_name,family_name,email,location,website,bio,pronoun,favorite_films) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    values,
                )

            conn.execute(
                "INSERT INTO import_runs(export_hash, diary_count, username) VALUES(?,?,?)",
                (summary.export_hash, summary.diary_count, summary.username),
            )
            # New films are pending; successful/manual matches remain untouched.
            conn.execute(
                """
                INSERT INTO enrichment_status(letterboxd_uri, status)
                SELECT DISTINCT d.letterboxd_uri, 'pending' FROM diary d
                LEFT JOIN enrichment_status e ON e.letterboxd_uri=d.letterboxd_uri
                WHERE d.letterboxd_uri IS NOT NULL AND d.letterboxd_uri != '' AND e.letterboxd_uri IS NULL
                """
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return summary
