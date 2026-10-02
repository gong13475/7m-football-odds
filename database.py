# ============================================================
# database.py
# 7M 축구 최종배당 분석 DB
# ============================================================

import sqlite3
from pathlib import Path
from datetime import datetime


# ============================================================
# DB 경로
# ============================================================

DB_PATH = Path(__file__).resolve().parent / "sevenm.db"


# ============================================================
# DB 연결
# ============================================================

def get_connection():

    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# 초기화
# ============================================================

def init_database():

    conn = get_connection()

    cur = conn.cursor()

    # --------------------------------------------------------
    # 경기
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            match_id TEXT UNIQUE,

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
    """)

    # --------------------------------------------------------
    # 최종배당
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            match_id TEXT,

            bookmaker TEXT DEFAULT '7M',

            cid TEXT,

            home_odds REAL,

            draw_odds REAL,

            away_odds REAL,

            odds_type TEXT DEFAULT 'final',

            created_at TEXT,

            UNIQUE(
                match_id,
                bookmaker,
                cid,
                odds_type
            )
        )
    """)

    # --------------------------------------------------------
    # 수집 기록
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS collection_log (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            start_date TEXT,

            end_date TEXT,

            cid TEXT,

            total_matches INTEGER DEFAULT 0,

            saved_matches INTEGER DEFAULT 0,

            saved_odds INTEGER DEFAULT 0,

            failed INTEGER DEFAULT 0,

            started_at TEXT,

            finished_at TEXT,

            status TEXT
        )
    """)

    # --------------------------------------------------------
    # 인덱스
    # --------------------------------------------------------

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_date
        ON matches(match_date)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_result
        ON matches(result)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_values
        ON odds(
            home_odds,
            draw_odds,
            away_odds
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_match
        ON odds(match_id)
    """)

    conn.commit()

    conn.close()


# ============================================================
# 경기 저장
# ============================================================

def save_match(
    match_id,
    match_date,
    home_team,
    away_team,
    home_score=None,
    away_score=None,
    result=None
):

    conn = get_connection()

    cur = conn.cursor()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    cur.execute("""
        INSERT INTO matches (
            match_id,
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
        VALUES (?, ?, ?, ?, ?, ?, ?, '7M', ?, ?)

        ON CONFLICT(match_id)
        DO UPDATE SET

            match_date = excluded.match_date,

            home_team = excluded.home_team,

            away_team = excluded.away_team,

            home_score = excluded.home_score,

            away_score = excluded.away_score,

            result = excluded.result,

            updated_at = excluded.updated_at
    """, (
        str(match_id),
        match_date,
        home_team,
        away_team,
        home_score,
        away_score,
        result,
        now,
        now
    ))

    conn.commit()

    conn.close()


# ============================================================
# 최종배당 저장
# ============================================================

def save_odds(
    match_id,
    home_odds,
    draw_odds,
    away_odds,
    cid="",
    bookmaker="7M"
):

    if (
        home_odds is None
        or draw_odds is None
        or away_odds is None
    ):
        return False

    try:

        home_odds = float(home_odds)
        draw_odds = float(draw_odds)
        away_odds = float(away_odds)

    except Exception:

        return False

    if (
        home_odds <= 1
        or draw_odds <= 1
        or away_odds <= 1
    ):
        return False

    conn = get_connection()

    cur = conn.cursor()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    cur.execute("""
        INSERT INTO odds (
            match_id,
            bookmaker,
            cid,
            home_odds,
            draw_odds,
            away_odds,
            odds_type,
            created_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, 'final', ?
        )

        ON CONFLICT(
            match_id,
            bookmaker,
            cid,
            odds_type
        )
        DO UPDATE SET

            home_odds = excluded.home_odds,

            draw_odds = excluded.draw_odds,

            away_odds = excluded.away_odds,

            created_at = excluded.created_at
    """, (
        str(match_id),
        bookmaker,
        str(cid or ""),
        home_odds,
        draw_odds,
        away_odds,
        now
    ))

    conn.commit()

    conn.close()

    return True


# ============================================================
# 경기 + 배당 한번에 저장
# ============================================================

def save_match_with_odds(data):

    if not data:
        return False

    match_id = data.get(
        "match_id"
    )

    if not match_id:
        return False

    save_match(
        match_id=match_id,
        match_date=data.get(
            "match_date"
        ),
        home_team=data.get(
            "home_team",
            ""
        ),
        away_team=data.get(
            "away_team",
            ""
        ),
        home_score=data.get(
            "home_score"
        ),
        away_score=data.get(
            "away_score"
        ),
        result=data.get(
            "result"
        )
    )

    odds_saved = save_odds(
        match_id=match_id,
        home_odds=data.get(
            "home_odds"
        ),
        draw_odds=data.get(
            "draw_odds"
        ),
        away_odds=data.get(
            "away_odds"
        ),
        cid=data.get(
            "cid",
            ""
        ),
        bookmaker="7M"
    )

    return odds_saved


# ============================================================
# 전체 경기 수
# ============================================================

def get_match_count():

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM matches
    """)

    value = cur.fetchone()[0]

    conn.close()

    return int(value or 0)


# ============================================================
# 최종배당 수
# ============================================================

def get_odds_count():

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM odds
        WHERE odds_type = 'final'
    """)

    value = cur.fetchone()[0]

    conn.close()

    return int(value or 0)


# ============================================================
# 업체 수
# ============================================================

def get_bookmaker_count():

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(
            DISTINCT bookmaker
        )
        FROM odds
    """)

    value = cur.fetchone()[0]

    conn.close()

    return int(value or 0)


# ============================================================
# 최근 경기
# ============================================================

def get_matches(
    limit=100,
    offset=0
):

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT

            m.match_id,
            m.match_date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.result,

            o.bookmaker,
            o.cid,

            o.home_odds,
            o.draw_odds,
            o.away_odds,

            o.odds_type

        FROM matches m

        LEFT JOIN odds o
            ON m.match_id = o.match_id

        ORDER BY
            m.match_date DESC,
            m.id DESC

        LIMIT ?
        OFFSET ?
    """, (
        int(limit),
        int(offset)
    ))

    rows = cur.fetchall()

    conn.close()

    return [dict(row) for row in rows]


# ============================================================
# 특정 경기
# ============================================================

def get_match(match_id):

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM matches
        WHERE match_id = ?
        LIMIT 1
    """, (
        str(match_id),
    ))

    row = cur.fetchone()

    conn.close()

    if row is None:
        return None

    return dict(row)


# ============================================================
# 특정 경기 배당
# ============================================================

def get_match_odds(match_id):

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM odds
        WHERE match_id = ?
        ORDER BY id DESC
    """, (
        str(match_id),
    ))

    rows = cur.fetchall()

    conn.close()

    return [dict(row) for row in rows]


# ============================================================
# 동일배당 검색
# ============================================================

def get_same_odds(
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.01
):

    conn = get_connection()

    cur = conn.cursor()

    low_h = float(home_odds) - tolerance
    high_h = float(home_odds) + tolerance

    low_d = float(draw_odds) - tolerance
    high_d = float(draw_odds) + tolerance

    low_a = float(away_odds) - tolerance
    high_a = float(away_odds) + tolerance

    cur.execute("""
        SELECT

            m.match_id,
            m.match_date,

            m.home_team,
            m.away_team,

            m.home_score,
            m.away_score,

            m.result,

            o.bookmaker,
            o.cid,

            o.home_odds,
            o.draw_odds,
            o.away_odds

        FROM odds o

        JOIN matches m
            ON m.match_id = o.match_id

        WHERE

            o.odds_type = 'final'

            AND o.home_odds
                BETWEEN ? AND ?

            AND o.draw_odds
                BETWEEN ? AND ?

            AND o.away_odds
                BETWEEN ? AND ?

        ORDER BY
            m.match_date DESC
    """, (
        low_h,
        high_h,

        low_d,
        high_d,

        low_a,
        high_a
    ))

    rows = cur.fetchall()

    conn.close()

    return [dict(row) for row in rows]


# ============================================================
# 결과별 통계
# ============================================================

def get_result_statistics(
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.01
):

    rows = get_same_odds(
        home_odds,
        draw_odds,
        away_odds,
        tolerance
    )

    total = len(rows)

    win = sum(
        1
        for row in rows
        if row.get("result") == "승"
    )

    draw = sum(
        1
        for row in rows
        if row.get("result") == "무"
    )

    lose = sum(
        1
        for row in rows
        if row.get("result") == "패"
    )

    def percent(value):

        if total == 0:
            return 0.0

        return round(
            value / total * 100,
            2
        )

    return {
        "total": total,

        "승": win,
        "무": draw,
        "패": lose,

        "승률": percent(win),
        "무율": percent(draw),
        "패율": percent(lose),

        "rows": rows
    }


# ============================================================
# 전체 결과 통계
# ============================================================

def get_overall_statistics():

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN result = '승'
                    THEN 1 ELSE 0
                END
            ) AS win,

            SUM(
                CASE
                    WHEN result = '무'
                    THEN 1 ELSE 0
                END
            ) AS draw,

            SUM(
                CASE
                    WHEN result = '패'
                    THEN 1 ELSE 0
                END
            ) AS lose

        FROM matches
        WHERE result IS NOT NULL
    """)

    row = cur.fetchone()

    conn.close()

    total = int(
        row["total"] or 0
    )

    win = int(
        row["win"] or 0
    )

    draw = int(
        row["draw"] or 0
    )

    lose = int(
        row["lose"] or 0
    )

    def pct(value):

        if total == 0:
            return 0.0

        return round(
            value / total * 100,
            2
        )

    return {
        "total": total,

        "win": win,
        "draw": draw,
        "lose": lose,

        "win_pct": pct(win),
        "draw_pct": pct(draw),
        "lose_pct": pct(lose),
    }


# ============================================================
# 날짜별 통계
# ============================================================

def get_date_statistics(
    start_date=None,
    end_date=None
):

    conn = get_connection()

    cur = conn.cursor()

    query = """
        SELECT
            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN result = '승'
                    THEN 1 ELSE 0
                END
            ) AS win,

            SUM(
                CASE
                    WHEN result = '무'
                    THEN 1 ELSE 0
                END
            ) AS draw,

            SUM(
                CASE
                    WHEN result = '패'
                    THEN 1 ELSE 0
                END
            ) AS lose

        FROM matches

        WHERE 1=1
    """

    params = []

    if start_date:

        query += """
            AND match_date >= ?
        """

        params.append(
            start_date
        )

    if end_date:

        query += """
            AND match_date <= ?
        """

        params.append(
            end_date
        )

    cur.execute(
        query,
        params
    )

    row = cur.fetchone()

    conn.close()

    total = int(
        row["total"] or 0
    )

    win = int(
        row["win"] or 0
    )

    draw = int(
        row["draw"] or 0
    )

    lose = int(
        row["lose"] or 0
    )

    def pct(value):

        if total == 0:
            return 0.0

        return round(
            value / total * 100,
            2
        )

    return {
        "total": total,

        "win": win,
        "draw": draw,
        "lose": lose,

        "win_pct": pct(win),
        "draw_pct": pct(draw),
        "lose_pct": pct(lose),
    }


# ============================================================
# 수집 로그 저장
# ============================================================

def save_collection_log(
    start_date,
    end_date,
    cid,
    total_matches,
    saved_matches,
    saved_odds,
    failed,
    started_at,
    finished_at,
    status
):

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO collection_log (

            start_date,
            end_date,
            cid,

            total_matches,
            saved_matches,
            saved_odds,

            failed,

            started_at,
            finished_at,

            status
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        start_date,
        end_date,
        cid,

        total_matches,
        saved_matches,
        saved_odds,

        failed,

        started_at,
        finished_at,

        status
    ))

    conn.commit()

    conn.close()


# ============================================================
# DB 상태
# ============================================================

def get_database_status():

    init_database()

    return {
        "db_path": str(DB_PATH),

        "matches": get_match_count(),

        "odds": get_odds_count(),

        "bookmakers": get_bookmaker_count(),

        "source": "7M"
    }


# ============================================================
# DB 초기화
# ============================================================

init_database()
