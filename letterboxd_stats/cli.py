"""Command-line launcher used by ``uvx letterboxd-wrapped``."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from . import __version__
from .database import connect, ensure_schema
from .paths import DATA_DIR_ENV, database_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch your local Letterboxd Stats dashboard"
    )
    parser.add_argument(
        "--port", type=int, default=8501, help="Local web port (default: 8501)"
    )
    parser.add_argument(
        "--data-dir", type=Path, help="Override the persistent data directory"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Do not open a browser automatically"
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Print paths and verify the database schema",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.data_dir:
        os.environ[DATA_DIR_ENV] = str(args.data_dir.expanduser().resolve())
    if args.doctor:
        path = database_path()
        conn = connect(path)
        try:
            ensure_schema(conn)
        finally:
            conn.close()
        print(f"Letterboxd Stats {__version__}")
        print(f"Database: {path}")
        print("Schema: OK")
        return 0

    from . import streamlit_app

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(Path(streamlit_app.__file__).resolve()),
        "--server.port",
        str(args.port),
        "--server.headless",
        "true" if args.no_browser else "false",
        "--browser.gatherUsageStats",
        "false",
    ]
    process = subprocess.Popen(command, env=os.environ.copy())
    try:
        return process.wait()
    except KeyboardInterrupt:
        # Keep Ctrl-C quiet and make sure the Streamlit child is not orphaned.
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
