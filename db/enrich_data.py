"""Compatibility CLI for the restartable TMDB enrichment service."""

from __future__ import annotations

import argparse

from letterboxd_stats.config import load_config
from letterboxd_stats.database import connect, ensure_schema
from letterboxd_stats.enrichment import enrich_library
from letterboxd_stats.paths import database_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich imported films with TMDB")
    parser.add_argument("--api-key", default=load_config().tmdb_api_key)
    parser.add_argument("--database", default=database_path())
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--retry-unmatched", action="store_true")
    args = parser.parse_args()
    if not args.api_key:
        parser.error("A TMDB API key is required.")
    conn = connect(args.database)
    try:
        ensure_schema(conn)
        result = enrich_library(
            conn,
            args.api_key,
            lambda event: (
                print(
                    f"[{event.completed}/{event.total}] {event.movie_name}", flush=True
                )
                if event.completed
                else None
            ),
            force=args.force,
            retry_unmatched=args.retry_unmatched,
        )
    finally:
        conn.close()
    print(f"Done: {result.found} matched, {result.failed} failed")


if __name__ == "__main__":
    main()
