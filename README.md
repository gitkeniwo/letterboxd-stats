# Letterboxd Stats

A Streamlit-based visualization dashboard for your Letterboxd viewing data. Get insights into your movie watching habits with beautiful, Letterboxd-styled visualizations.

## Features

- 📊 **Year Overview** - Total films, average rating, rewatches, watch time
- 🏆 **Top Rated Films** - Poster wall for 5-star and 4.5-star movies
- 🔄 **Rewatched Films** - Films you loved enough to watch again
- 📈 **Timeline** - Monthly viewing trends and calendar heatmap
- 🎬 **Directors** - Most watched directors with photos
- 🌍 **Genres, Countries & Languages** - Distribution charts
- ⚙️ **Data Management** - Fix incorrect movie posters via TMDB

## Tech Stack

- **Python 3.11+** with `uv` for package management
- **Streamlit** for the web interface
- **SQLite** for data storage
- **TMDB API** for movie metadata (posters, directors, genres)
- **Altair** for charts

## Setup

### 1. Clone and Install

```bash
git clone <your-repo>
cd letterboxd-stats
uv sync
```

### 2. Export Your Letterboxd Data

1. Go to [letterboxd.com/settings/data/](https://letterboxd.com/settings/data/)
2. Click "Export Your Data"
3. Extract the ZIP file to the project root (folder should be named `letterboxd-*`)

### 3. Get TMDB API Key (Optional but Recommended)

1. Sign up at [themoviedb.org](https://www.themoviedb.org/signup)
2. Get your API key from [Settings > API](https://www.themoviedb.org/settings/api)
3. Create `.env.dev` file:

```env
API_KEY=your_tmdb_api_key_here
```

### 4. Initialize Database

```bash
uv run python db/init_db.py
```

### 5. Enrich Data with TMDB (Optional)

This fetches posters, directors, genres, etc. from TMDB:

```bash
uv run python db/enrich_data.py
```

### 6. Run the App

```bash
uv run streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Project Structure

```
letterboxd-stats/
├── app.py                 # Main Streamlit app
├── db/
│   ├── init_db.py         # CSV to SQLite importer
│   └── enrich_data.py     # TMDB data enrichment
├── visualizations/
│   ├── overview.py        # Stats overview + poster walls
│   ├── timeline.py        # Monthly trends + calendar
│   ├── film_analysis.py   # Rating/decade distribution
│   ├── directors.py       # Director statistics
│   ├── genres_countries.py # Genre/country/language charts
│   └── tags_reviews.py    # Tags and review stats
├── pages/
│   └── data_management.py # Fix incorrect movie data
├── .streamlit/
│   └── config.toml        # Streamlit theme config
├── pyproject.toml         # Project dependencies
└── letterboxd.db          # SQLite database (generated)
```

## Credits

- Data source: [Letterboxd](https://letterboxd.com)
- Movie metadata: [The Movie Database (TMDB)](https://www.themoviedb.org)
- Inspired by [Statsboxd](https://github.com/GiuDiMax/Statsboxd)

## License

MIT
