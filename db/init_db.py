"""
Initialize SQLite database from Letterboxd CSV exports.
"""
import csv
import sqlite3
from pathlib import Path
from datetime import datetime


def parse_date(date_str: str) -> str | None:
    """Parse date string to ISO format."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def parse_rating(rating_str: str) -> float | None:
    """Parse rating string to float."""
    if not rating_str:
        return None
    try:
        return float(rating_str)
    except ValueError:
        return None


def parse_bool(val: str) -> bool:
    """Parse boolean-ish string."""
    return val.lower() in ("yes", "true", "1") if val else False


def create_tables(conn: sqlite3.Connection):
    """Create all tables."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS diary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            name TEXT NOT NULL,
            year INTEGER,
            letterboxd_uri TEXT,
            rating REAL,
            rewatch INTEGER DEFAULT 0,
            tags TEXT,
            watched_date TEXT
        );
        
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            name TEXT NOT NULL,
            year INTEGER,
            letterboxd_uri TEXT,
            rating REAL
        );
        
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            name TEXT NOT NULL,
            year INTEGER,
            letterboxd_uri TEXT,
            rating REAL,
            rewatch INTEGER DEFAULT 0,
            review TEXT,
            tags TEXT,
            watched_date TEXT
        );
        
        CREATE TABLE IF NOT EXISTS watched (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            name TEXT NOT NULL,
            year INTEGER,
            letterboxd_uri TEXT
        );
        
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            name TEXT NOT NULL,
            year INTEGER,
            letterboxd_uri TEXT
        );
        
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_joined TEXT,
            username TEXT,
            given_name TEXT,
            family_name TEXT,
            email TEXT,
            location TEXT,
            website TEXT,
            bio TEXT,
            pronoun TEXT,
            favorite_films TEXT
        );
        
        CREATE INDEX IF NOT EXISTS idx_diary_watched_date ON diary(watched_date);
        CREATE INDEX IF NOT EXISTS idx_diary_year ON diary(year);
        CREATE INDEX IF NOT EXISTS idx_diary_rating ON diary(rating);
    """)


def import_diary(conn: sqlite3.Connection, csv_path: Path):
    """Import diary.csv."""
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append((
                parse_date(row.get("Date", "")),
                row.get("Name", ""),
                int(row["Year"]) if row.get("Year") else None,
                row.get("Letterboxd URI", ""),
                parse_rating(row.get("Rating", "")),
                1 if parse_bool(row.get("Rewatch", "")) else 0,
                row.get("Tags", ""),
                parse_date(row.get("Watched Date", "")),
            ))
        conn.executemany(
            "INSERT INTO diary (date, name, year, letterboxd_uri, rating, rewatch, tags, watched_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows
        )


def import_ratings(conn: sqlite3.Connection, csv_path: Path):
    """Import ratings.csv."""
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append((
                parse_date(row.get("Date", "")),
                row.get("Name", ""),
                int(row["Year"]) if row.get("Year") else None,
                row.get("Letterboxd URI", ""),
                parse_rating(row.get("Rating", "")),
            ))
        conn.executemany(
            "INSERT INTO ratings (date, name, year, letterboxd_uri, rating) VALUES (?, ?, ?, ?, ?)",
            rows
        )


def import_reviews(conn: sqlite3.Connection, csv_path: Path):
    """Import reviews.csv."""
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append((
                parse_date(row.get("Date", "")),
                row.get("Name", ""),
                int(row["Year"]) if row.get("Year") else None,
                row.get("Letterboxd URI", ""),
                parse_rating(row.get("Rating", "")),
                1 if parse_bool(row.get("Rewatch", "")) else 0,
                row.get("Review", ""),
                row.get("Tags", ""),
                parse_date(row.get("Watched Date", "")),
            ))
        conn.executemany(
            "INSERT INTO reviews (date, name, year, letterboxd_uri, rating, rewatch, review, tags, watched_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows
        )


def import_watched(conn: sqlite3.Connection, csv_path: Path):
    """Import watched.csv."""
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append((
                parse_date(row.get("Date", "")),
                row.get("Name", ""),
                int(row["Year"]) if row.get("Year") else None,
                row.get("Letterboxd URI", ""),
            ))
        conn.executemany(
            "INSERT INTO watched (date, name, year, letterboxd_uri) VALUES (?, ?, ?, ?)",
            rows
        )


def import_watchlist(conn: sqlite3.Connection, csv_path: Path):
    """Import watchlist.csv."""
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append((
                parse_date(row.get("Date", "")),
                row.get("Name", ""),
                int(row["Year"]) if row.get("Year") else None,
                row.get("Letterboxd URI", ""),
            ))
        conn.executemany(
            "INSERT INTO watchlist (date, name, year, letterboxd_uri) VALUES (?, ?, ?, ?)",
            rows
        )


def import_profile(conn: sqlite3.Connection, csv_path: Path):
    """Import profile.csv."""
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("Username"):
                continue
            conn.execute(
                """INSERT INTO profile 
                   (date_joined, username, given_name, family_name, email, location, website, bio, pronoun, favorite_films) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    parse_date(row.get("Date Joined", "")),
                    row.get("Username", ""),
                    row.get("Given Name", ""),
                    row.get("Family Name", ""),
                    row.get("Email Address", ""),
                    row.get("Location", ""),
                    row.get("Website", ""),
                    row.get("Bio", ""),
                    row.get("Pronoun", ""),
                    row.get("Favorite Films", ""),
                )
            )


def init_db(data_dir: Path, db_path: Path):
    """Initialize database from CSV files."""
    # Remove existing database
    if db_path.exists():
        db_path.unlink()
    
    conn = sqlite3.connect(db_path)
    try:
        create_tables(conn)
        
        # Import each CSV
        csv_files = {
            "diary.csv": import_diary,
            "ratings.csv": import_ratings,
            "reviews.csv": import_reviews,
            "watched.csv": import_watched,
            "watchlist.csv": import_watchlist,
            "profile.csv": import_profile,
        }
        
        for filename, importer in csv_files.items():
            csv_path = data_dir / filename
            if csv_path.exists():
                print(f"Importing {filename}...")
                importer(conn, csv_path)
        
        conn.commit()
        print(f"Database created at {db_path}")
        
        # Print summary
        cursor = conn.execute("SELECT COUNT(*) FROM diary")
        print(f"  - diary entries: {cursor.fetchone()[0]}")
        cursor = conn.execute("SELECT COUNT(*) FROM ratings")
        print(f"  - ratings: {cursor.fetchone()[0]}")
        cursor = conn.execute("SELECT COUNT(*) FROM reviews")
        print(f"  - reviews: {cursor.fetchone()[0]}")
        
    finally:
        conn.close()


def main():
    """CLI entry point."""
    import sys
    
    # Find data directory (first directory matching letterboxd-*)
    base_dir = Path(__file__).parent.parent
    data_dirs = list(base_dir.glob("letterboxd-*"))
    
    if not data_dirs:
        print("Error: No letterboxd-* data directory found.")
        sys.exit(1)
    
    data_dir = sorted(data_dirs)[-1]  # Use latest
    
    if data_dir.is_file() and data_dir.suffix == ".zip":
        print(f"Found zip file {data_dir}, looking for extracted folder...")
        data_dirs = [d for d in data_dirs if d.is_dir()]
        if not data_dirs:
            print("Error: Please extract the zip file first.")
            sys.exit(1)
        data_dir = sorted(data_dirs)[-1]
    
    print(f"Using data directory: {data_dir}")
    db_path = base_dir / "letterboxd.db"
    init_db(data_dir, db_path)


if __name__ == "__main__":
    main()
