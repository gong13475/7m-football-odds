import sqlite3
from pathlib import Path
from datetime import datetime


DB_PATH = Path("odds.db")


# =========================================================
# DB 연결
# =========================================================

def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# DB 초기화
# =========================================================

def init_database():

    conn = get_connection()

    try:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS matches (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                schedule_id TEXT NOT NULL UNIQUE,

                match_date TEXT DEFAULT '',

                league TEXT DEFAULT '',

                home_team TEXT DEFAULT '',

                away_team TEXT DEFAULT '',

                home_score INTEGER,

                away_score INTEGER,

                result TEXT DEFAULT '',

                source TEXT DEFAULT '',

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS odds (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                schedule_id TEXT NOT NULL,

                company_name TEXT NOT NULL,

                final_home REAL NOT NULL,

                final_draw REAL NOT NULL,

                final_away REAL NOT NULL,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(
                    schedule_id,
                    company_name
                )
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_odds_company
            ON odds(company_name)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_odds_values
            ON odds(
                final_home,
                final_draw,
                final_away
            )
        """)

        conn.commit()

    finally:

        conn.close()


# =========================================================
# 하위 호환
# =========================================================

def init_db():
    init_database()


# =========================================================
# 경기 저장
# =========================================================

def save_match(row):

    conn = get_connection()

    try:

        schedule_id = str(
            row.get("schedule_id", "")
        ).strip()

        if not schedule_id:
            return False

        cur = conn.execute("""
            INSERT OR IGNORE INTO matches (
                schedule_id,
                match_date,
                league,
                home_team,
                away_team,
                home_score,
                away_score,
                result,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            schedule_id,
            row.get("match_date", ""),
            row.get("league", ""),
            row.get("home_team", ""),
            row.get("away_team", ""),
            row.get("home_score"),
            row.get("away_score"),
            row.get("result", ""),
            row.get("source", "")
        ))

        conn.commit()

        return cur.rowcount > 0

    finally:

        conn.close()


# =========================================================
# 배당 저장
# =========================================================

def save_odds(
    schedule_id,
    company_name,
    final_home,
    final_draw,
    final_away
):

    conn = get_connection()

    try:

        cur = conn.execute("""
            INSERT OR IGNORE INTO odds (
                schedule_id,
                company_name,
                final_home,
                final_draw,
                final_away
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(schedule_id),
            str(company_name),
            float(final_home),
            float(final_draw),
            float(final_away)
        ))

        conn.commit()

        return cur.rowcount > 0

    finally:

        conn.close()


# =========================================================
# 경기 + 배당 한번에 저장
# =========================================================

def save_match_with_odds(
    match,
    company_odds
):

    saved_match = save_match(match)

    saved_odds = 0

    for company, odds in (
        company_odds or {}
    ).items():

        try:

            if save_odds(
                match["schedule_id"],
                company,
                odds["home"],
                odds["draw"],
                odds["away"]
            ):

                saved_odds += 1

        except Exception:
            continue

    return {
        "match_saved": saved_match,
        "odds_saved": saved_odds
    }


# =========================================================
# 경기 수
# =========================================================

def get_match_count():

    conn = get_connection()

    try:

        return conn.execute(
            "SELECT COUNT(*) FROM matches"
        ).fetchone()[0]

    finally:

        conn.close()


# =========================================================
# 배당 수
# =========================================================

def get_odds_count():

    conn = get_connection()

    try:

        return conn.execute(
            "SELECT COUNT(*) FROM odds"
        ).fetchone()[0]

    finally:

        conn.close()


# =========================================================
# 업체 목록
# =========================================================

def get_company_names():

    conn = get_connection()

    try:

        rows = conn.execute("""
            SELECT DISTINCT company_name
            FROM odds
            WHERE company_name <> ''
            ORDER BY company_name
        """).fetchall()

        return [
            row["company_name"]
            for row in rows
        ]

    finally:

        conn.close()


# =========================================================
# 전체 경기
# =========================================================

def get_all_matches():

    conn = get_connection()

    try:

        rows = conn.execute("""
            SELECT *
            FROM matches
            ORDER BY
                match_date DESC,
                id DESC
        """).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# =========================================================
# 전체 배당
# =========================================================

def get_all_odds():

    conn = get_connection()

    try:

        rows = conn.execute("""
            SELECT *
            FROM odds
            ORDER BY
                schedule_id DESC,
                company_name
        """).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# =========================================================
# 업체별 저장량
# =========================================================

def get_company_counts():

    conn = get_connection()

    try:

        rows = conn.execute("""
            SELECT
                company_name,
                COUNT(*) AS cnt
            FROM odds
            GROUP BY company_name
            ORDER BY cnt DESC
        """).fetchall()

        return {
            row["company_name"]:
                row["cnt"]
            for row in rows
        }

    finally:

        conn.close()


# =========================================================
# 특정 경기
# =========================================================

def get_match(schedule_id):

    conn = get_connection()

    try:

        row = conn.execute("""
            SELECT *
            FROM matches
            WHERE schedule_id = ?
        """, (
            str(schedule_id),
        )).fetchone()

        return (
            dict(row)
            if row
            else None
        )

    finally:

        conn.close()


# =========================================================
# 특정 경기 업체별 배당
# =========================================================

def get_match_odds(schedule_id):

    conn = get_connection()

    try:

        rows = conn.execute("""
            SELECT *
            FROM odds
            WHERE schedule_id = ?
            ORDER BY company_name
        """, (
            str(schedule_id),
        )).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# =========================================================
# 동일배당 검색
# =========================================================

def find_same_odds(
    company_name,
    home,
    draw,
    away
):

    conn = get_connection()

    try:

        rows = conn.execute("""
            SELECT
                m.*,

                o.company_name,

                o.final_home,

                o.final_draw,

                o.final_away

            FROM odds o

            INNER JOIN matches m
                ON m.schedule_id =
                   o.schedule_id

            WHERE o.company_name = ?

              AND o.final_home = ?

              AND o.final_draw = ?

              AND o.final_away = ?

            ORDER BY
                m.match_date DESC
        """, (
            company_name,
            float(home),
            float(draw),
            float(away)
        )).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# =========================================================
# 여러 업체 동일배당 분석용
# =========================================================

def find_same_odds_multiple(
    company_odds
):

    if not company_odds:
        return []

    conn = get_connection()

    try:

        conditions = []

        params = []

        for company, odds in (
            company_odds.items()
        ):

            conditions.append("""
                EXISTS (

                    SELECT 1

                    FROM odds x

                    WHERE x.schedule_id =
                          m.schedule_id

                      AND x.company_name = ?

                      AND x.final_home = ?

                      AND x.final_draw = ?

                      AND x.final_away = ?
                )
            """)

            params.extend([
                company,
                float(odds["home"]),
                float(odds["draw"]),
                float(odds["away"])
            ])

        sql = f"""
            SELECT m.*

            FROM matches m

            WHERE {' AND '.join(conditions)}

            ORDER BY
                m.match_date DESC
        """

        rows = conn.execute(
            sql,
            params
        ).fetchall()

        result = []

        for row in rows:

            item = dict(row)

            item["company_odds"] = {}

            odds_rows = conn.execute("""
                SELECT
                    company_name,
                    final_home,
                    final_draw,
                    final_away
                FROM odds
                WHERE schedule_id = ?
            """, (
                item["schedule_id"],
            )).fetchall()

            for odds in odds_rows:

                item["company_odds"][
                    odds["company_name"]
                ] = {
                    "home":
                        odds["final_home"],

                    "draw":
                        odds["final_draw"],

                    "away":
                        odds["final_away"]
                }

            result.append(item)

        return result

    finally:

        conn.close()


# =========================================================
# 날짜별 경기
# =========================================================

def get_matches_by_date(
    match_date
):

    conn = get_connection()

    try:

        rows = conn.execute("""
            SELECT *
            FROM matches
            WHERE match_date = ?
            ORDER BY id
        """, (
            str(match_date),
        )).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# =========================================================
# DB 초기화용
# =========================================================

def clear_database():

    conn = get_connection()

    try:

        conn.execute(
            "DELETE FROM odds"
        )

        conn.execute(
            "DELETE FROM matches"
        )

        conn.commit()

    finally:

        conn.close()


# =========================================================
# 통계
# =========================================================

def get_database_statistics():

    return {
        "matches":
            get_match_count(),

        "odds":
            get_odds_count(),

        "companies":
            len(get_company_names())
    }


# =========================================================
# 프로그램 시작 시 자동 초기화
# =========================================================

init_database()
