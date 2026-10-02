import sqlite3
import threading

from pathlib import Path


DB_PATH = Path("odds.db")

_db_lock = threading.RLock()


def get_connection():

    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA journal_mode=WAL"
    )

    conn.execute(
        "PRAGMA synchronous=NORMAL"
    )

    return conn


def init_db():

    with _db_lock:

        conn = get_connection()

        try:

            conn.executescript("""

            CREATE TABLE IF NOT EXISTS matches (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                match_key TEXT NOT NULL UNIQUE,

                match_date TEXT NOT NULL,

                league TEXT DEFAULT '',

                home_team TEXT DEFAULT '',
                away_team TEXT DEFAULT '',

                home_score INTEGER,
                away_score INTEGER,

                result TEXT NOT NULL,

                home_odds REAL NOT NULL,
                draw_odds REAL NOT NULL,
                away_odds REAL NOT NULL,

                home_probability REAL NOT NULL,
                draw_probability REAL NOT NULL,
                away_probability REAL NOT NULL,

                source TEXT DEFAULT '',

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );


            CREATE INDEX IF NOT EXISTS
            idx_matches_date
            ON matches(match_date);


            CREATE INDEX IF NOT EXISTS
            idx_matches_odds
            ON matches(
                home_odds,
                draw_odds,
                away_odds
            );


            CREATE INDEX IF NOT EXISTS
            idx_matches_result
            ON matches(result);


            CREATE TABLE IF NOT EXISTS collection_days (

                match_date TEXT PRIMARY KEY,

                status TEXT NOT NULL,

                found INTEGER DEFAULT 0,

                saved INTEGER DEFAULT 0,

                error TEXT DEFAULT '',

                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );


            CREATE TABLE IF NOT EXISTS collection_state (

                id INTEGER PRIMARY KEY CHECK(id = 1),

                start_date TEXT,

                end_date TEXT,

                last_completed_date TEXT,

                running INTEGER DEFAULT 0,

                stopped INTEGER DEFAULT 0,

                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );


            CREATE TABLE IF NOT EXISTS collection_logs (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                level TEXT DEFAULT 'INFO',

                message TEXT NOT NULL
            );

            """)

            conn.commit()

        finally:

            conn.close()


def save_match(row):

    match_key = row.get("match_key")


    if not match_key:

        match_key = "|".join([

            str(row.get("match_date", "")),

            str(row.get("home_team", "")),

            str(row.get("away_team", "")),

            str(row.get("home_score", "")),

            str(row.get("away_score", "")),

            str(row.get("home_odds", "")),

            str(row.get("draw_odds", "")),

            str(row.get("away_odds", "")),

            str(row.get("result", ""))
        ])


    with _db_lock:

        conn = get_connection()

        try:

            cur = conn.execute("""

                INSERT OR IGNORE INTO matches (

                    match_key,
                    match_date,
                    league,
                    home_team,
                    away_team,
                    home_score,
                    away_score,
                    result,
                    home_odds,
                    draw_odds,
                    away_odds,
                    home_probability,
                    draw_probability,
                    away_probability,
                    source

                )

                VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )

            """, (

                match_key,

                row.get(
                    "match_date",
                    ""
                ),

                row.get(
                    "league",
                    ""
                ),

                row.get(
                    "home_team",
                    ""
                ),

                row.get(
                    "away_team",
                    ""
                ),

                row.get("home_score"),

                row.get("away_score"),

                row.get(
                    "result",
                    "D"
                ),

                float(row["home_odds"]),

                float(row["draw_odds"]),

                float(row["away_odds"]),

                float(
                    row["home_probability"]
                ),

                float(
                    row["draw_probability"]
                ),

                float(
                    row["away_probability"]
                ),

                row.get(
                    "source",
                    "7M"
                )
            ))


            conn.commit()

            return cur.rowcount

        finally:

            conn.close()


def get_match_count():

    conn = get_connection()

    try:

        return conn.execute(
            "SELECT COUNT(*) FROM matches"
        ).fetchone()[0]

    finally:

        conn.close()


def get_odds_count():

    return get_match_count()


def get_all_matches():

    conn = get_connection()

    try:

        rows = conn.execute("""

            SELECT *
            FROM matches
            ORDER BY match_date DESC, id DESC

        """).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


def get_all_odds():

    conn = get_connection()

    try:

        rows = conn.execute("""

            SELECT

                match_key,
                match_date,
                home_team,
                away_team,

                home_odds AS final_home,
                draw_odds AS final_draw,
                away_odds AS final_away,

                result

            FROM matches

            ORDER BY match_date DESC, id DESC

        """).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


def get_company_names():

    return (
        ["7M"]
        if get_match_count()
        else []
    )


def get_company_counts():

    count = get_match_count()

    if not count:
        return {}

    return {
        "7M": count
    }


def get_same_odds(
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.00001
):

    conn = get_connection()

    try:

        rows = conn.execute("""

            SELECT *

            FROM matches

            WHERE ABS(home_odds - ?) < ?
              AND ABS(draw_odds - ?) < ?
              AND ABS(away_odds - ?) < ?

            ORDER BY match_date DESC, id DESC

        """, (

            float(home_odds),
            tolerance,

            float(draw_odds),
            tolerance,

            float(away_odds),
            tolerance
        )).fetchall()


        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


def save_collection_day(
    target_date,
    status,
    found=0,
    saved=0,
    error=""
):

    with _db_lock:

        conn = get_connection()

        try:

            conn.execute("""

                INSERT INTO collection_days (

                    match_date,
                    status,
                    found,
                    saved,
                    error,
                    updated_at

                )

                VALUES (
                    ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
                )

                ON CONFLICT(match_date)

                DO UPDATE SET

                    status=excluded.status,
                    found=excluded.found,
                    saved=excluded.saved,
                    error=excluded.error,
                    updated_at=CURRENT_TIMESTAMP

            """, (

                target_date.isoformat()
                if hasattr(
                    target_date,
                    "isoformat"
                )
                else str(target_date),

                status,

                int(found),

                int(saved),

                str(error or "")
            ))

            conn.commit()

        finally:

            conn.close()


def save_collection_state(
    start_date=None,
    end_date=None,
    last_completed_date=None,
    running=False,
    stopped=False
):

    with _db_lock:

        conn = get_connection()

        try:

            conn.execute("""

                INSERT INTO collection_state (

                    id,
                    start_date,
                    end_date,
                    last_completed_date,
                    running,
                    stopped

                )

                VALUES (
                    1, ?, ?, ?, ?, ?
                )

                ON CONFLICT(id)

                DO UPDATE SET

                    start_date=
                        excluded.start_date,

                    end_date=
                        excluded.end_date,

                    last_completed_date=
                        excluded.last_completed_date,

                    running=
                        excluded.running,

                    stopped=
                        excluded.stopped,

                    updated_at=
                        CURRENT_TIMESTAMP

            """, (

                str(start_date)
                if start_date
                else None,

                str(end_date)
                if end_date
                else None,

                str(last_completed_date)
                if last_completed_date
                else None,

                int(bool(running)),

                int(bool(stopped))
            ))

            conn.commit()

        finally:

            conn.close()


def get_collection_state():

    conn = get_connection()

    try:

        row = conn.execute("""

            SELECT *
            FROM collection_state
            WHERE id = 1

        """).fetchone()

        return (
            dict(row)
            if row
            else {}
        )

    finally:

        conn.close()


def add_log(
    message,
    level="INFO"
):

    with _db_lock:

        conn = get_connection()

        try:

            conn.execute("""

                INSERT INTO collection_logs (
                    level,
                    message
                )

                VALUES (?, ?)

            """, (
                level,
                str(message)
            ))

            conn.commit()

        finally:

            conn.close()


def get_logs(limit=500):

    conn = get_connection()

    try:

        rows = conn.execute("""

            SELECT
                created_at,
                level,
                message

            FROM collection_logs

            ORDER BY id DESC

            LIMIT ?

        """, (
            int(limit),
        )).fetchall()


        rows = list(
            reversed(rows)
        )


        return "\n".join(

            f"[{row['created_at']}] "
            f"[{row['level']}] "
            f"{row['message']}"

            for row in rows
        )

    finally:

        conn.close()
# ============================================================
# INITIALIZE
# ============================================================

init_db()
