"""Load SBX Parquet dumps into SQLite with WAL mode enabled.

Target database: data/db/sbx.sqlite
PRAGMA settings:
- journal_mode = WAL (Write-Ahead Logging)
- synchronous = NORMAL
- busy_timeout = 5000
- cache_size = -64000 (64MB)
- foreign_keys = ON
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
import pandas as pd


DB_DIR = Path("data/db")
DB_PATH = DB_DIR / "sbx.sqlite"
DUMP_DIR = Path("sbx_dump")

TABLE_ORDER = ["systems", "orbits", "velocities", "alias", "configurations", "duplicates"]


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Creates connection and configures high-performance SQLite PRAGMAs."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Enable WAL mode and performance tuning
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.execute("PRAGMA cache_size = -64000;")
    cursor.execute("PRAGMA foreign_keys = ON;")

    return conn


def load_parquet_to_sqlite(dump_dir: Path = DUMP_DIR, db_path: Path = DB_PATH) -> None:
    """Loads all extracted Parquet files into SQLite tables."""
    print(f"Connecting to SQLite database at {db_path} ...")
    conn = get_connection(db_path)

    try:
        # Check WAL mode
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        print(f"SQLite PRAGMA journal_mode: {journal_mode.upper()}")

        for table_name in TABLE_ORDER:
            parquet_file = dump_dir / f"{table_name}.parquet"
            if not parquet_file.exists():
                print(f"Warning: {parquet_file} does not exist, skipping.")
                continue

            print(f"Reading {parquet_file.name} ...")
            df = pd.read_parquet(parquet_file)
            print(f"Loading {len(df)} rows into table '{table_name}' ...")

            # Load into SQLite table (replaces table if already existing)
            df.to_sql(table_name, conn, if_exists="replace", index=False)

            # Verification
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name};").fetchone()[0]
            print(f"[OK] Table '{table_name}' loaded successfully with {count} rows.")

        # Optimize SQLite database statistics
        print("Optimizing database (PRAGMA optimize) ...")
        conn.execute("PRAGMA optimize;")
        print("Done.")

    finally:
        conn.close()


if __name__ == "__main__":
    load_parquet_to_sqlite()
