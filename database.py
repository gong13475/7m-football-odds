# ============================================================
# database.py
# ⚽ 7M 축구 최종배당 SQLite 데이터베이스
#
# 기능
# ------------------------------------------------------------
# 1. DB 자동 생성
# 2. 경기 저장
# 3. 최종배당 저장
# 4. 중복 경기 방지
# 5. 업체별 배당 저장
# 6. 전체 경기 조회
# 7. 분석용 데이터 조회
# 8. 업체 목록
# 9. DB 상태
# 10. 기존 DB 호환
# ============================================================

import sqlite3
from pathlib import Path
from datetime import datetime


# ============================================================
# DB 위치
# ============================================================

DB_PATH = (
    Path(__file__).resolve().parent
    / "scoreman.db"
)


# ============================================================
# DB 연결
# ============================================================

def get_connection():

    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=30,
        check_same_thread=False,
    )

    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# DB 초기화
# ============================================================

def init_database():

    conn = get_connection()

    try:

        cursor = conn.cursor()

        # ----------------------------------------------------
        # 경기 테이블
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS matches (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                schedule_id INTEGER UNIQUE NOT NULL,

                match_date TEXT,

                home_team TEXT,

                away_team TEXT,

                home_score INTEGER,

                away_score INTEGER,

                result TEXT,

                source TEXT DEFAULT '7M',

                created_at TEXT,

                updated_at TEXT

            )
            """
        )

        # ----------------------------------------------------
        # 배당 테이블
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS odds (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                schedule_id INTEGER NOT NULL,

                bookmaker TEXT NOT NULL,

                home_odds REAL,

                draw_odds REAL,

                away_odds REAL,

                odds_type TEXT DEFAULT 'final',

                created_at TEXT,

                UNIQUE(
                    schedule_id,
                    bookmaker,
                    odds_type
                )

            )
            """
        )

        # ----------------------------------------------------
        # 인덱스
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_matches_schedule
            ON matches(schedule_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_odds_schedule
            ON odds(schedule_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_odds_bookmaker
            ON odds(bookmaker)
            """
        )

        conn.commit()

    finally:

        conn.close()


# ============================================================
# 컬럼 존재 여부
# ============================================================

def column_exists(
    table,
    column
):

    conn = get_connection()

    try:

        rows = conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()

        return any(
            row["name"] == column
            for row in rows
        )

    finally:

        conn.close()


# ============================================================
# 경기 저장
# ============================================================

def save_match(
    data
):

    init_database()

    conn = get_connection()

    try:

        now = datetime.now().isoformat()

        schedule_id = int(
            data.get(
                "schedule_id"
            )
        )

        # ----------------------------------------------------
        # 경기 정보
        # ----------------------------------------------------

        conn.execute(
            """
            INSERT INTO matches (
                schedule_id,
                match_date,
                home_team,
                away_team,
                home_score,
                away_score,
                result,
                source,
                created_at,
                updated_at
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(schedule_id)
            DO UPDATE SET

                match_date = excluded.match_date,

                home_team = excluded.home_team,

                away_team = excluded.away_team,

                home_score = excluded.home_score,

                away_score = excluded.away_score,

                result = excluded.result,

                source = excluded.source,

                updated_at = excluded.updated_at

            """,
            (
                schedule_id,

                data.get(
                    "match_date",
                    ""
                ),

                data.get(
                    "home_team",
                    ""
                ),

                data.get(
                    "away_team",
                    ""
                ),

                data.get(
                    "home_score"
                ),

                data.get(
                    "away_score"
                ),

                data.get(
                    "result",
                    ""
                ),

                data.get(
                    "source",
                    "7M"
                ),

                now,

                now,
            )
        )

        # ----------------------------------------------------
        # 배당 저장
        # ----------------------------------------------------

        odds_list = data.get(
            "odds",
            []
        )

        saved_odds = 0

        for odd in odds_list:

            bookmaker = (
                odd.get(
                    "company"
                )
                or odd.get(
                    "bookmaker"
                )
                or "7M"
            )

            home_odds = odd.get(
                "home"
            )

            draw_odds = odd.get(
                "draw"
            )

            away_odds = odd.get(
                "away"
            )

            if (
                home_odds is None
                or draw_odds is None
                or away_odds is None
            ):
                continue

            conn.execute(
                """
                INSERT INTO odds (
                    schedule_id,
                    bookmaker,
                    home_odds,
                    draw_odds,
                    away_odds,
                    odds_type,
                    created_at
                )

                VALUES (?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(
                    schedule_id,
                    bookmaker,
                    odds_type
                )

                DO UPDATE SET

                    home_odds =
                        excluded.home_odds,

                    draw_odds =
                        excluded.draw_odds,

                    away_odds =
                        excluded.away_odds,

                    created_at =
                        excluded.created_at

                """,
                (
                    schedule_id,

                    str(
                        bookmaker
                    ).strip(),

                    float(
                        home_odds
                    ),

                    float(
                        draw_odds
                    ),

                    float(
                        away_odds
                    ),

                    "final",

                    now,
                )
            )

            saved_odds += 1

        conn.commit()

        return True

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# 호환용 함수
# ============================================================

def save_match_data(
    data
):

    return save_match(
        data
    )


def insert_match(
    data
):

    return save_match(
        data
    )


def add_match(
    data
):

    return save_match(
        data
    )


# ============================================================
# 경기 저장 여부
# ============================================================

def match_exists(
    schedule_id
):

    init_database()

    conn = get_connection()

    try:

        row = conn.execute(
            """
            SELECT 1
            FROM matches
            WHERE schedule_id = ?
            LIMIT 1
            """,
            (
                int(
                    schedule_id
                ),
            )
        ).fetchone()

        return row is not None

    finally:

        conn.close()


# ============================================================
# 경기 조회
# ============================================================

def get_match(
    schedule_id
):

    init_database()

    conn = get_connection()

    try:

        row = conn.execute(
            """
            SELECT *
            FROM matches
            WHERE schedule_id = ?
            LIMIT 1
            """,
            (
                int(
                    schedule_id
                ),
            )
        ).fetchone()

        if row is None:
            return None

        return dict(
            row
        )

    finally:

        conn.close()


# ============================================================
# 경기 전체 조회
# ============================================================

def get_matches(
    limit=100000
):

    init_database()

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT *
            FROM matches
            ORDER BY
                COALESCE(
                    match_date,
                    ''
                ) DESC,
                schedule_id DESC
            LIMIT ?
            """,
            (
                int(limit),
            )
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# 배당 전체 조회
# ============================================================

def get_odds(
    limit=100000
):

    init_database()

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT *
            FROM odds
            ORDER BY
                schedule_id DESC,
                id DESC
            LIMIT ?
            """,
            (
                int(limit),
            )
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# 업체 목록
# ============================================================

def get_bookmakers():

    init_database()

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT
                bookmaker,
                COUNT(*) AS count
            FROM odds
            GROUP BY bookmaker
            ORDER BY count DESC
            """
        ).fetchall()

        return [
            {
                "bookmaker":
                    row["bookmaker"],

                "count":
                    row["count"],
            }

            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# 분석용 데이터
#
# matches + odds JOIN
# ============================================================

def get_analysis_data(
    bookmaker=None,
    limit=100000
):

    init_database()

    conn = get_connection()

    try:

        if bookmaker:

            rows = conn.execute(
                """
                SELECT

                    m.schedule_id,

                    m.match_date,

                    m.home_team,

                    m.away_team,

                    m.home_score,

                    m.away_score,

                    m.result,

                    m.source,

                    o.bookmaker,

                    o.home_odds,

                    o.draw_odds,

                    o.away_odds,

                    o.odds_type

                FROM matches m

                INNER JOIN odds o
                    ON
                    m.schedule_id =
                    o.schedule_id

                WHERE o.bookmaker = ?

                ORDER BY
                    m.schedule_id DESC

                LIMIT ?

                """,
                (
                    str(
                        bookmaker
                    ),
                    int(limit),
                )
            ).fetchall()

        else:

            rows = conn.execute(
                """
                SELECT

                    m.schedule_id,

                    m.match_date,

                    m.home_team,

                    m.away_team,

                    m.home_score,

                    m.away_score,

                    m.result,

                    m.source,

                    o.bookmaker,

                    o.home_odds,

                    o.draw_odds,

                    o.away_odds,

                    o.odds_type

                FROM matches m

                INNER JOIN odds o
                    ON
                    m.schedule_id =
                    o.schedule_id

                ORDER BY
                    m.schedule_id DESC

                LIMIT ?

                """,
                (
                    int(limit),
                )
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# 최근 경기
# ============================================================

def get_recent_matches(
    limit=100
):

    return get_matches(
        limit=limit
    )


# ============================================================
# 최근 분석 데이터
# ============================================================

def get_recent_analysis(
    limit=100
):

    return get_analysis_data(
        limit=limit
    )


# ============================================================
# DB 통계
# ============================================================

def get_database_status():

    init_database()

    conn = get_connection()

    try:

        match_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM matches
            """
        ).fetchone()[0]

        odds_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM odds
            """
        ).fetchone()[0]

        bookmaker_count = conn.execute(
            """
            SELECT COUNT(
                DISTINCT bookmaker
            )
            FROM odds
            """
        ).fetchone()[0]

        return {

            "matches":
                int(match_count),

            "odds":
                int(odds_count),

            "bookmakers":
                int(bookmaker_count),

        }

    finally:

        conn.close()


# ============================================================
# 별칭
# ============================================================

def database_status():

    return get_database_status()


def get_db_status():

    return get_database_status()


# ============================================================
# 결과별 경기 수
# ============================================================

def get_result_counts():

    init_database()

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT
                result,
                COUNT(*) AS count
            FROM matches
            GROUP BY result
            """
        ).fetchall()

        result = {
            "승": 0,
            "무": 0,
            "패": 0,
        }

        for row in rows:

            value = row["result"]

            if value in result:

                result[value] = int(
                    row["count"]
                )

        return result

    finally:

        conn.close()


# ============================================================
# 업체별 경기 수
# ============================================================

def get_bookmaker_counts():

    init_database()

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT
                bookmaker,
                COUNT(*) AS count
            FROM odds
            GROUP BY bookmaker
            ORDER BY count DESC
            """
        ).fetchall()

        return [
            {
                "bookmaker":
                    row["bookmaker"],

                "count":
                    int(
                        row["count"]
                    ),
            }

            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# 특정 경기 배당
# ============================================================

def get_match_odds(
    schedule_id
):

    init_database()

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT *
            FROM odds
            WHERE schedule_id = ?
            ORDER BY bookmaker
            """,
            (
                int(
                    schedule_id
                ),
            )
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# 데이터 삭제
# ============================================================

def delete_match(
    schedule_id
):

    init_database()

    conn = get_connection()

    try:

        conn.execute(
            """
            DELETE FROM odds
            WHERE schedule_id = ?
            """,
            (
                int(
                    schedule_id
                ),
            )
        )

        conn.execute(
            """
            DELETE FROM matches
            WHERE schedule_id = ?
            """,
            (
                int(
                    schedule_id
                ),
            )
        )

        conn.commit()

        return True

    except Exception:

        conn.rollback()

        return False

    finally:

        conn.close()


# ============================================================
# DB 전체 초기화
# ============================================================

def clear_database():

    init_database()

    conn = get_connection()

    try:

        conn.execute(
            "DELETE FROM odds"
        )

        conn.execute(
            "DELETE FROM matches"
        )

        conn.commit()

        return True

    except Exception:

        conn.rollback()

        return False

    finally:

        conn.close()


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "⚽ 7M SQLite Database"
    )

    print(
        "=" * 60
    )

    init_database()

    status = (
        get_database_status()
    )

    print(
        "DB 위치:",
        DB_PATH
    )

    print(
        "전체 경기:",
        status["matches"]
    )

    print(
        "최종배당:",
        status["odds"]
    )

    print(
        "업체:",
        status["bookmakers"]
    )
