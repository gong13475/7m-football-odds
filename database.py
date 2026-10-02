import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path("odds.db")


def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")

    return conn


def init_db():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_key TEXT NOT NULL UNIQUE,
            match_date TEXT NOT NULL,

            bookmaker TEXT NOT NULL,

            home_odds REAL NOT NULL,
            draw_odds REAL NOT NULL,
            away_odds REAL NOT NULL,

            result TEXT,

            status TEXT NOT NULL DEFAULT 'pending',

            attempts INTEGER NOT NULL DEFAULT 0,

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_match_date
        ON matches(match_date)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds
        ON matches(
            bookmaker,
            home_odds,
            draw_odds,
            away_odds
        )
    """)

    conn.commit()
    conn.close()


def save_match(
    match_key: str,
    match_date: str,
    bookmaker: str,
    home_odds: float,
    draw_odds: float,
    away_odds: float,
    result: Optional[str] = None
):
    conn = get_connection()

    conn.execute("""
        INSERT OR IGNORE INTO matches (
            match_key,
            match_date,
            bookmaker,
            home_odds,
            draw_odds,
            away_odds,
            result,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'completed')
    """, (
        match_key,
        match_date,
        bookmaker,
        home_odds,
        draw_odds,
        away_odds,
        result
    ))

    conn.commit()
    conn.close()


def match_exists(match_key: str) -> bool:
    conn = get_connection()

    row = conn.execute(
        "SELECT 1 FROM matches WHERE match_key = ? LIMIT 1",
        (match_key,)
    ).fetchone()

    conn.close()

    return row is not None


def get_same_odds(
    home_odds: float,
    draw_odds: float,
    away_odds: float
):
    conn = get_connection()

    rows = conn.execute("""
        SELECT
            match_date,
            bookmaker,
            result
        FROM matches
        WHERE
            home_odds = ?
            AND draw_odds = ?
            AND away_odds = ?
            AND status = 'completed'
    """, (
        home_odds,
        draw_odds,
        away_odds
    )).fetchall()

    conn.close()

    return rows


def get_counts(
    home_odds: float,
    draw_odds: float,
    away_odds: float
):
    rows = get_same_odds(
        home_odds,
        draw_odds,
        away_odds
    )

    total = len(rows)

    if total == 0:
        return {
            "total": 0,
            "home": 0,
            "draw": 0,
            "away": 0
        }

    home = sum(1 for r in rows if r[2] == "H")
    draw = sum(1 for r in rows if r[2] == "D")
    away = sum(1 for r in rows if r[2] == "A")

    return {
        "total": total,
        "home": home,
        "draw": draw,
        "away": away
    }


init_db()
