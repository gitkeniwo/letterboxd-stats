# Letterboxd Stats

A simple Streamlit dashboard for your Letterboxd viewing history. Upload your Letterboxd export ZIP file, fetch posters and credits from TMDB, and explore your yearly wrapped stats.

<img width="75%" height="926" alt="image" src="https://github.com/user-attachments/assets/68ed35f1-d3af-4c52-8741-9f487e14933a" />

## Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```bash
uvx letterboxd-wrapped
```

Or run it directly from GitHub:

```bash
uvx --from git+https://github.com/gitkeniwo/letterboxd-stats letterboxd-stats
```

The web app opens a setup wizard page, where you only need:

1. Your Letterboxd ZIP file from [Letterboxd data export](https://letterboxd.com/settings/data/).
2. A [TMDB API key](https://developer.themoviedb.org/docs/getting-started) for displaying posters, directors, cast, genres, countries, and runtime, as these cannot be directly fetched from Letterboxd.

Do not extract or rename the Letterboxd ZIP.
Data and the TMDB key stay in your local user data/configuration directories.

## What changed in 0.2

- Direct Letterboxd ZIP upload with validation and preview.
- Transactional imports: a failed update leaves the previous library intact.
- Incremental TMDB enrichment that resumes after interruption.
- Movie-first matching with a confidence check and automatic TV fallback.
- Explicit placeholder cards instead of unexplained gaps when a poster is missing.
- Existing metadata and manual corrections survive newer Letterboxd exports.
- First-run setup and ongoing data management inside the app.
- Persistent storage outside the source tree and uvx environment.
- One `letterboxd-wrapped` command for launching the app (`letterboxd-stats` remains an alias).

## Updating your data

Open **Data Management → Import update**, upload a newer Letterboxd ZIP, and confirm. Letterboxd tables are replaced as a snapshot while existing TMDB metadata is retained. Only new or previously failed films are sent to TMDB.

**Data Management** opens directly on the unresolved-film queue. It selects the first unmatched film, searches both movie and TV results, and also accepts a direct TMDB ID. A manual correction is protected from future automatic replacement. Import and TMDB-key controls live in compact popovers at the top of the page.

Libraries enriched by an older version can use **Retry automatic movie + TV matching** once before reviewing the remaining films manually.

## Command options

```bash
letterboxd-wrapped --port 8502
letterboxd-wrapped --no-browser
letterboxd-wrapped --data-dir /path/to/portable-data
letterboxd-wrapped --doctor
```

`--doctor` creates or migrates the schema and prints the active database location without starting Streamlit.

## Development

```bash
git clone <repository-url>
cd letterboxd-stats
uv sync
uv run pytest
uv run streamlit run app.py
```

The old commands remain available for compatibility, but are no longer part of the normal user flow:

```bash
uv run python db/init_db.py /path/to/letterboxd-export.zip
uv run python db/enrich_data.py --api-key YOUR_KEY
```

On its first normal launch from the repository, version 0.2 copies a legacy project-local `letterboxd.db` into the user data directory. The original database is not removed.

## Architecture

```text
Streamlit UI
    ↓
transactional ZIP importer ── persistent SQLite database
    ↓                             ↑
restartable TMDB enrichment ──────┘
```

The visualization modules remain presentation-focused. Importing, storage, TMDB access, and enrichment can run independently of Streamlit and are covered by automated tests.

## Privacy

Letterboxd exports contain personal profile, viewing, rating, and review data. The app runs locally and does not upload the export to an application server. Movie identifiers and titles are sent to TMDB as required for enrichment.

## License

MIT
