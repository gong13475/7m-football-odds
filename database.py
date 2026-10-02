import sqlite3
from pathlib import Path

DB_PATH = Path("odds.db")


def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            match_date TEXT NOT NULL,
            league TEXT DEFAULT '',

            home_odds REAL NOT NULL,
            draw_odds REAL NOT NULL,
            away_odds REAL NOT NULL,

            result TEXT NOT NULL,

            home_probability REAL NOT NULL,
            draw_probability REAL NOT NULL,
            away_probability REAL NOT NULL,

            source TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(
                match_date,
                league,
                home_odds,
                draw_odds,
                away_odds,
                result
            )
        )
    """)

    conn.commit()
    return conn


def init_db():
    conn = get_connection()
    conn.close()


def save_match(row):
    conn = get_connection()

    try:
        cur = conn.execute("""
            INSERT OR IGNORE INTO matches (
                match_date,
                league,
                home_odds,
                draw_odds,
                away_odds,
                result,
                home_probability,
                draw_probability,
                away_probability,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["match_date"],
            row.get("league", ""),
            row["home_odds"],
            row["draw_odds"],
            row["away_odds"],
            row["result"],
            row["home_probability"],
            row["draw_probability"],
            row["away_probability"],
            row.get("source", "")
        ))

        conn.commit()

        return cur.rowcount

    finally:
        conn.close()


def get_count():
    conn = get_connection()

    try:
        return conn.execute(
            "SELECT COUNT(*) FROM matches"
        ).fetchone()[0]

    finally:
        conn.close()


def get_same_odds(
    home_odds,
    draw_odds,
    away_odds
):
    conn = get_connection()

    try:
        return conn.execute("""
            SELECT result
            FROM matches
            WHERE home_odds = ?
              AND draw_odds = ?
              AND away_odds = ?
        """, (
            home_odds,
            draw_odds,
            away_odds
        )).fetchall()

    finally:
        conn.close()
