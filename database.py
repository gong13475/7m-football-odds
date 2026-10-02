import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("odds.db")


def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False,
        timeout=30,
    )

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            match_date TEXT NOT NULL,
            league TEXT DEFAULT '',
            home_team TEXT DEFAULT '',
            away_team TEXT DEFAULT '',

            company TEXT DEFAULT '미지정',

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

    # 기존 DB에 새 컬럼이 없는 경우 자동 추가
    columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(matches)"
        ).fetchall()
    }

    for name, definition in [
        ("home_team", "TEXT DEFAULT ''"),
        ("away_team", "TEXT DEFAULT ''"),
        ("company", "TEXT DEFAULT '미지정'"),
    ]:
        if name not in columns:
            conn.execute(
                f"ALTER TABLE matches ADD COLUMN "
                f"{name} {definition}"
            )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS collection_days (
            target_date TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            found INTEGER DEFAULT 0,
            saved INTEGER DEFAULT 0,
            error TEXT DEFAULT '',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
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
            row["match_date"],
            row.get("league", ""),
            row.get("home_team", ""),
            row.get("away_team", ""),
            row.get("company", "미지정"),
            row["home_odds"],
            row["draw_odds"],
            row["away_odds"],
            row["result"],
            row["home_probability"],
            row["draw_probability"],
            row["away_probability"],
            row.get("source", ""),
        ))

        conn.commit()
        return cur.rowcount

    finally:
        conn.close()


def get_count(company=None):
    conn = get_connection()

    try:
        if company and company != "전체":
            return conn.execute(
                "SELECT COUNT(*) FROM matches WHERE company=?",
                (company,),
            ).fetchone()[0]

        return conn.execute(
            "SELECT COUNT(*) FROM matches"
        ).fetchone()[0]

    finally:
        conn.close()


def get_company_counts():
    conn = get_connection()

    try:
        return conn.execute("""
            SELECT
                COALESCE(NULLIF(company, ''), '미지정') AS company,
                COUNT(*) AS count
            FROM matches
            GROUP BY company
            ORDER BY count DESC
        """).fetchall()

    finally:
        conn.close()


def get_companies():
    conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT DISTINCT
                COALESCE(NULLIF(company, ''), '미지정')
            FROM matches
            ORDER BY 1
        """).fetchall()

        return [row[0] for row in rows]

    finally:
        conn.close()


def get_same_odds(
    home_odds,
    draw_odds,
    away_odds,
    company="전체",
):
    conn = get_connection()

    try:
        if company and company != "전체":
            return conn.execute("""
                SELECT result
                FROM matches
                WHERE company=?
                  AND ABS(home_odds - ?) < 0.000001
                  AND ABS(draw_odds - ?) < 0.000001
                  AND ABS(away_odds - ?) < 0.000001
            """, (
                company,
                home_odds,
                draw_odds,
                away_odds,
            )).fetchall()

        return conn.execute("""
            SELECT result
            FROM matches
            WHERE ABS(home_odds - ?) < 0.000001
              AND ABS(draw_odds - ?) < 0.000001
              AND ABS(away_odds - ?) < 0.000001
        """, (
            home_odds,
            draw_odds,
            away_odds,
        )).fetchall()

    finally:
        conn.close()


def get_result_counts(
    home_odds=None,
    draw_odds=None,
    away_odds=None,
    company="전체",
):
    conn = get_connection()

    try:
        clauses = []
        params = []

        if home_odds is not None:
            clauses.append(
                "ABS(home_odds - ?) < 0.000001"
            )
            params.append(home_odds)

        if draw_odds is not None:
            clauses.append(
                "ABS(draw_odds - ?) < 0.000001"
            )
            params.append(draw_odds)

        if away_odds is not None:
            clauses.append(
                "ABS(away_odds - ?) < 0.000001"
            )
            params.append(away_odds)

        if company and company != "전체":
            clauses.append("company=?")
            params.append(company)

        where = ""
        if clauses:
            where = "WHERE " + " AND ".join(clauses)

        rows = conn.execute(
            f"""
            SELECT result, COUNT(*)
            FROM matches
            {where}
            GROUP BY result
            """,
            params,
        ).fetchall()

        result = {
            "H": 0,
            "D": 0,
            "A": 0,
        }

        for outcome, count in rows:
            if outcome in result:
                result[outcome] = count

        result["total"] = sum(result.values())

        return result

    finally:
        conn.close()


def save_collection_day(
    target_date,
    status,
    found=0,
    saved=0,
    error="",
):
    conn = get_connection()

    try:
        conn.execute("""
            INSERT INTO collection_days (
                target_date,
                status,
                found,
                saved,
                error,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(target_date)
            DO UPDATE SET
                status=excluded.status,
                found=excluded.found,
                saved=excluded.saved,
                error=excluded.error,
                updated_at=CURRENT_TIMESTAMP
        """, (
            str(target_date),
            status,
            found,
            saved,
            error or "",
        ))

        conn.commit()

    finally:
        conn.close()


def get_collection_day(target_date):
    conn = get_connection()

    try:
        return conn.execute("""
            SELECT
                target_date,
                status,
                found,
                saved,
                error,
                updated_at
            FROM collection_days
            WHERE target_date=?
        """, (str(target_date),)).fetchone()

    finally:
        conn.close()


def get_last_completed_date():
    conn = get_connection()

    try:
        row = conn.execute("""
            SELECT MAX(target_date)
            FROM collection_days
            WHERE status IN ('success', 'skipped')
        """).fetchone()

        return row[0] if row else None

    finally:
        conn.close()


def get_failed_days():
    conn = get_connection()

    try:
        return conn.execute("""
            SELECT target_date, error
            FROM collection_days
            WHERE status='failed'
            ORDER BY target_date
        """).fetchall()

    finally:
        conn.close()


def get_all_matches():
    conn = get_connection()

    try:
        return conn.execute("""
            SELECT
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
        """).fetchall()

    finally:
        conn.close()
