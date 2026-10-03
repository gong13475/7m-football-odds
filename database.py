# ============================================================
# database.py
# ⚽ 7M / 축구 배당 분석용 SQLite 데이터베이스
#
# 기능
# ------------------------------------------------------------
# 1. DB 자동 생성
# 2. matches 테이블
# 3. odds 테이블
# 4. 경기 중복 확인
# 5. 경기 저장
# 6. 업체별 최종배당 저장
# 7. 승 / 무 / 패 저장
# 8. 전체 경기 조회
# 9. 전체 배당 조회
# 10. 업체 목록
# 11. DB 통계
# 12. 분석용 데이터 조회
# 13. 기존 DB와 최대한 호환
# ============================================================

import sqlite3
from pathlib import Path
from datetime import datetime


# ============================================================
# DB 경로
# ============================================================

DB_PATH = (
    Path(__file__).resolve().parent
    / "scoreman.db"
)


# ============================================================
# 연결
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

    cursor = conn.cursor()

    # --------------------------------------------------------
    # 경기 테이블
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS matches (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            schedule_id INTEGER UNIQUE,

            match_date TEXT,

            home_team TEXT,

            away_team TEXT,

            home_score INTEGER,

            away_score INTEGER,

            result TEXT,

            source TEXT DEFAULT '7M',

            url TEXT,

            created_at TEXT,

            updated_at TEXT

        )
        """
    )

    # --------------------------------------------------------
    # 배당 테이블
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS odds (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            schedule_id INTEGER,

            bookmaker TEXT,

            home_odds REAL,

            draw_odds REAL,

            away_odds REAL,

            odds_type TEXT DEFAULT 'final',

            created_at TEXT,

            updated_at TEXT,

            UNIQUE(
                schedule_id,
                bookmaker,
                home_odds,
                draw_odds,
                away_odds,
                odds_type
            )

        )
        """
    )

    # --------------------------------------------------------
    # 인덱스
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_matches_schedule_id
        ON matches(schedule_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_matches_result
        ON matches(result)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_odds_schedule_id
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

    conn.close()


# ============================================================
# 초기화 자동 실행
# ============================================================

init_database()


# ============================================================
# 테이블 컬럼 확인
# ============================================================

def get_table_columns(
    table_name
):

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            f"PRAGMA table_info({table_name})"
        )

        rows = cursor.fetchall()

        return [
            row["name"]
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# 경기 존재 여부
# ============================================================

def match_exists(
    schedule_id
):

    try:

        schedule_id = int(
            schedule_id
        )

    except Exception:

        return False

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 1
            FROM matches
            WHERE schedule_id = ?
            LIMIT 1
            """,
            (
                schedule_id,
            )
        )

        return (
            cursor.fetchone()
            is not None
        )

    finally:

        conn.close()


# ============================================================
# 경기 ID로 경기 조회
# ============================================================

def get_match(
    schedule_id
):

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM matches
            WHERE schedule_id = ?
            LIMIT 1
            """,
            (
                int(schedule_id),
            )
        )

        row = cursor.fetchone()

        if row:
            return dict(row)

        return None

    finally:

        conn.close()


# ============================================================
# 경기 저장
# ============================================================

def save_match_data(
    data
):

    if not isinstance(
        data,
        dict
    ):

        return False

    schedule_id = data.get(
        "schedule_id"
    )

    if schedule_id is None:
        return False

    try:

        schedule_id = int(
            schedule_id
        )

    except Exception:

        return False

    now = datetime.now().isoformat()

    match_date = data.get(
        "match_date",
        ""
    )

    home_team = data.get(
        "home_team",
        ""
    )

    away_team = data.get(
        "away_team",
        ""
    )

    home_score = data.get(
        "home_score"
    )

    away_score = data.get(
        "away_score"
    )

    result = data.get(
        "result",
        ""
    )

    source = data.get(
        "source",
        "7M"
    )

    url = data.get(
        "url",
        ""
    )

    odds_list = data.get(
        "odds",
        []
    )

    conn = get_connection()

    try:

        cursor = conn.cursor()

        # ----------------------------------------------------
        # 경기 저장 / 업데이트
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM matches
            WHERE schedule_id = ?
            LIMIT 1
            """,
            (
                schedule_id,
            )
        )

        existing = cursor.fetchone()

        if existing:

            cursor.execute(
                """
                UPDATE matches
                SET
                    match_date = ?,
                    home_team = ?,
                    away_team = ?,
                    home_score = ?,
                    away_score = ?,
                    result = ?,
                    source = ?,
                    url = ?,
                    updated_at = ?
                WHERE schedule_id = ?
                """,
                (
                    match_date,
                    home_team,
                    away_team,
                    home_score,
                    away_score,
                    result,
                    source,
                    url,
                    now,
                    schedule_id,
                )
            )

        else:

            cursor.execute(
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
                    url,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
                """,
                (
                    schedule_id,
                    match_date,
                    home_team,
                    away_team,
                    home_score,
                    away_score,
                    result,
                    source,
                    url,
                    now,
                    now,
                )
            )

        # ----------------------------------------------------
        # 배당 저장
        # ----------------------------------------------------

        saved_odds = 0

        if isinstance(
            odds_list,
            list
        ):

            for odd in odds_list:

                if not isinstance(
                    odd,
                    dict
                ):
                    continue

                bookmaker = (
                    odd.get(
                        "company"
                    )
                    or odd.get(
                        "bookmaker"
                    )
                    or odd.get(
                        "company_name"
                    )
                    or "7M"
                )

                bookmaker = str(
                    bookmaker
                ).strip()

                if not bookmaker:
                    bookmaker = "7M"

                home_odds = to_float(
                    odd.get(
                        "home"
                    )
                )

                draw_odds = to_float(
                    odd.get(
                        "draw"
                    )
                )

                away_odds = to_float(
                    odd.get(
                        "away"
                    )
                )

                if not (
                    valid_odd(
                        home_odds
                    )
                    and valid_odd(
                        draw_odds
                    )
                    and valid_odd(
                        away_odds
                    )
                ):
                    continue

                odds_type = (
                    odd.get(
                        "odds_type"
                    )
                    or odd.get(
                        "type"
                    )
                    or "final"
                )

                odds_type = str(
                    odds_type
                ).strip()

                # --------------------------------------------
                # 이미 동일 배당이 있는지 확인
                # --------------------------------------------

                cursor.execute(
                    """
                    SELECT id
                    FROM odds
                    WHERE
                        schedule_id = ?
                        AND bookmaker = ?
                        AND home_odds = ?
                        AND draw_odds = ?
                        AND away_odds = ?
                        AND odds_type = ?
                    LIMIT 1
                    """,
                    (
                        schedule_id,
                        bookmaker,
                        home_odds,
                        draw_odds,
                        away_odds,
                        odds_type,
                    )
                )

                exists = (
                    cursor.fetchone()
                    is not None
                )

                if exists:

                    cursor.execute(
                        """
                        UPDATE odds
                        SET updated_at = ?
                        WHERE
                            schedule_id = ?
                            AND bookmaker = ?
                            AND home_odds = ?
                            AND draw_odds = ?
                            AND away_odds = ?
                            AND odds_type = ?
                        """,
                        (
                            now,
                            schedule_id,
                            bookmaker,
                            home_odds,
                            draw_odds,
                            away_odds,
                            odds_type,
                        )
                    )

                else:

                    cursor.execute(
                        """
                        INSERT INTO odds (
                            schedule_id,
                            bookmaker,
                            home_odds,
                            draw_odds,
                            away_odds,
                            odds_type,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            ?, ?, ?, ?, ?,
                            ?, ?, ?
                        )
                        """,
                        (
                            schedule_id,
                            bookmaker,
                            home_odds,
                            draw_odds,
                            away_odds,
                            odds_type,
                            now,
                            now,
                        )
                    )

                    saved_odds += 1

        conn.commit()

        return True

    except Exception:

        conn.rollback()

        return False

    finally:

        conn.close()


# ============================================================
# 기존 코드 호환
# ============================================================

def save_match(
    data
):

    return save_match_data(
        data
    )


def insert_match(
    data
):

    return save_match_data(
        data
    )


def add_match(
    data
):

    return save_match_data(
        data
    )


# ============================================================
# 숫자 변환
# ============================================================

def to_float(
    value
):

    try:

        if value is None:
            return None

        number = float(
            str(value).replace(
                ",",
                ""
            )
        )

        return number

    except Exception:

        return None


# ============================================================
# 배당 검증
# ============================================================

def valid_odd(
    value
):

    if value is None:
        return False

    try:

        value = float(
            value
        )

        return (
            1.01
            <= value
            <= 100
        )

    except Exception:

        return False


# ============================================================
# 전체 경기 수
# ============================================================

def get_total_matches():

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            AS count
            FROM matches
            """
        )

        row = cursor.fetchone()

        return int(
            row["count"]
            or 0
        )

    finally:

        conn.close()


# ============================================================
# 전체 배당 수
# ============================================================

def get_total_odds():

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            AS count
            FROM odds
            """
        )

        row = cursor.fetchone()

        return int(
            row["count"]
            or 0
        )

    finally:

        conn.close()


# ============================================================
# 업체 수
# ============================================================

def get_total_bookmakers():

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(
                DISTINCT bookmaker
            ) AS count
            FROM odds
            WHERE bookmaker IS NOT NULL
            AND bookmaker != ''
            """
        )

        row = cursor.fetchone()

        return int(
            row["count"]
            or 0
        )

    finally:

        conn.close()


# ============================================================
# 업체 목록
# ============================================================

def get_bookmakers():

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                bookmaker,
                COUNT(*) AS count
            FROM odds
            WHERE
                bookmaker IS NOT NULL
                AND bookmaker != ''
            GROUP BY bookmaker
            ORDER BY bookmaker
            """
        )

        rows = cursor.fetchall()

        return [
            {
                "bookmaker": row[
                    "bookmaker"
                ],
                "count": int(
                    row["count"]
                    or 0
                ),
            }
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# 경기 전체 조회
# ============================================================

def get_all_matches(
    limit=10000
):

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM matches
            ORDER BY
                match_date DESC,
                schedule_id DESC
            LIMIT ?
            """,
            (
                int(limit),
            )
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# 배당 전체 조회
# ============================================================

def get_all_odds(
    limit=50000
):

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM odds
            ORDER BY
                schedule_id DESC,
                bookmaker ASC
            LIMIT ?
            """,
            (
                int(limit),
            )
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# 경기 + 배당 JOIN
# ============================================================

def get_analysis_data(
    bookmaker=None,
    result=None,
    limit=100000
):

    conn = get_connection()

    try:

        cursor = conn.cursor()

        sql = """
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
                ON m.schedule_id
                = o.schedule_id

            WHERE 1 = 1
        """

        params = []

        if bookmaker:

            sql += """
                AND o.bookmaker = ?
            """

            params.append(
                bookmaker
            )

        if result:

            sql += """
                AND m.result = ?
            """

            params.append(
                result
            )

        sql += """
            ORDER BY
                m.match_date DESC,
                m.schedule_id DESC
            LIMIT ?
        """

        params.append(
            int(limit)
        )

        cursor.execute(
            sql,
            params
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# 업체별 분석 데이터
# ============================================================

def get_bookmaker_data(
    bookmaker,
    limit=100000
):

    return get_analysis_data(
        bookmaker=bookmaker,
        limit=limit
    )


# ============================================================
# 결과별 경기 수
# ============================================================

def get_result_counts():

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                SUM(
                    CASE
                        WHEN result = '승'
                        THEN 1
                        ELSE 0
                    END
                ) AS win_count,

                SUM(
                    CASE
                        WHEN result = '무'
                        THEN 1
                        ELSE 0
                    END
                ) AS draw_count,

                SUM(
                    CASE
                        WHEN result = '패'
                        THEN 1
                        ELSE 0
                    END
                ) AS lose_count

            FROM matches
            """
        )

        row = cursor.fetchone()

        return {
            "승": int(
                row["win_count"]
                or 0
            ),

            "무": int(
                row["draw_count"]
                or 0
            ),

            "패": int(
                row["lose_count"]
                or 0
            ),
        }

    finally:

        conn.close()


# ============================================================
# DB 상태
# ============================================================

def get_database_status():

    return {

        "db_path": str(
            DB_PATH
        ),

        "exists": DB_PATH.exists(),

        "matches": get_total_matches(),

        "odds": get_total_odds(),

        "bookmakers": get_total_bookmakers(),

    }


# ============================================================
# 최근 경기
# ============================================================

def get_recent_matches(
    limit=20
):

    return get_all_matches(
        limit=limit
    )


# ============================================================
# 경기 삭제
# ============================================================

def delete_match(
    schedule_id
):

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM odds
            WHERE schedule_id = ?
            """,
            (
                int(schedule_id),
            )
        )

        cursor.execute(
            """
            DELETE FROM matches
            WHERE schedule_id = ?
            """,
            (
                int(schedule_id),
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
# 전체 DB 삭제
# ============================================================

def clear_database():

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM odds"
        )

        cursor.execute(
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
# 종료
# ============================================================

if __name__ == "__main__":

    init_database()

    print(
        "=" * 60
    )

    print(
        "⚽ SQLite 데이터베이스"
    )

    print(
        "=" * 60
    )

    print(
        "DB:",
        DB_PATH
    )

    print(
        "경기:",
        get_total_matches()
    )

    print(
        "배당:",
        get_total_odds()
    )

    print(
        "업체:",
        get_total_bookmakers()
    )

    print(
        "결과:",
        get_result_counts()
        )
