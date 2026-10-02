import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("odds.db")


def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False,
        timeout=30
    )

    conn.execute("PRAGMA journal_mode=WAL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            match_date TEXT NOT NULL,
            league TEXT DEFAULT '',
            home_team TEXT DEFAULT '',
            away_team TEXT DEFAULT '',

            company TEXT DEFAULT '',

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
                home_team,
                away_team,
                company,
                home_odds,
                draw_odds,
                away_odds,
                result
            )
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS collection_status (
            id INTEGER PRIMARY KEY CHECK(id = 1),

            start_date TEXT,
            end_date TEXT,
            last_date TEXT,

            running INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,

            found INTEGER DEFAULT 0,
            saved INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,

            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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
                home_team,
                away_team,
                company,

                home_odds,
                draw_odds,
                away_odds,

                result,

                home_probability,
                draw_probability,
                away_probability,

                source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row.get("match_date", ""),
            row.get("league", ""),
            row.get("home_team", ""),
            row.get("away_team", ""),
            row.get("company", ""),

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


def save_manual_match(row):
    return save_match(row)


def get_count():
    conn = get_connection()

    try:
        return conn.execute(
            "SELECT COUNT(*) FROM matches"
        ).fetchone()[0]

    finally:
        conn.close()


def get_result_counts():
    conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT result, COUNT(*)
            FROM matches
            GROUP BY result
        """).fetchall()

        data = {
            "H": 0,
            "D": 0,
            "A": 0
        }

        for result, count in rows:
            if result in data:
                data[result] = count

        return data

    finally:
        conn.close()


def get_company_counts():
    conn = get_connection()

    try:
        return conn.execute("""
            SELECT
                CASE
                    WHEN company = '' THEN '미지정'
                    ELSE company
                END AS company,
                COUNT(*)
            FROM matches
            GROUP BY company
            ORDER BY COUNT(*) DESC
        """).fetchall()

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


def get_all_matches(limit=5000):
    conn = get_connection()

    try:
        return conn.execute("""
            SELECT
                id,
                match_date,
                league,
                home_team,
                away_team,
                company,
                home_odds,
                draw_odds,
                away_odds,
                result,
                home_probability,
                draw_probability,
                away_probability,
                source,
                created_at
            FROM matches
            ORDER BY match_date DESC, id DESC
            LIMIT ?
        """, (limit,)).fetchall()

    finally:
        conn.close()


def update_collection_status(
    start_date=None,
    end_date=None,
    last_date=None,
    running=None,
    completed=None,
    found=None,
    saved=None,
    failed=None
):
    conn = get_connection()

    try:
        old = conn.execute("""
            SELECT *
            FROM collection_status
            WHERE id = 1
        """).fetchone()

        if old is None:
            values = {
                "start_date": start_date,
                "end_date": end_date,
                "last_date": last_date,
                "running": int(bool(running)),
                "completed": int(bool(completed)),
                "found": found or 0,
                "saved": saved or 0,
                "failed": failed or 0
            }

            conn.execute("""
                INSERT INTO collection_status (
                    id,
                    start_date,
                    end_date,
                    last_date,
                    running,
                    completed,
                    found,
                    saved,
                    failed
                )
                VALUES (
                    1, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                values["start_date"],
                values["end_date"],
                values["last_date"],
                values["running"],
                values["completed"],
                values["found"],
                values["saved"],
                values["failed"]
            ))

        else:
            conn.execute("""
                UPDATE collection_status
                SET
                    start_date = COALESCE(?, start_date),
                    end_date = COALESCE(?, end_date),
                    last_date = COALESCE(?, last_date),
                    running = COALESCE(?, running),
                    completed = COALESCE(?, completed),
                    found = COALESCE(?, found),
                    saved = COALESCE(?, saved),
                    failed = COALESCE(?, failed),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (
                start_date,
                end_date,
                last_date,
                None if running is None else int(bool(running)),
                None if completed is None else int(bool(completed)),
                found,
                saved,
                failed
            ))

        conn.commit()

    finally:
        conn.close()


def get_collection_status():
    conn = get_connection()

    try:
        row = conn.execute("""
            SELECT
                start_date,
                end_date,
                last_date,
                running,
                completed,
                found,
                saved,
                failed,
                updated_at
            FROM collection_status
            WHERE id = 1
        """).fetchone()

        if not row:
            return {}

        keys = [
            "start_date",
            "end_date",
            "last_date",
            "running",
            "completed",
            "found",
            "saved",
            "failed",
            "updated_at"
        ]

        return dict(zip(keys, row))

    finally:
        conn.close()
