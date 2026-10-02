# collector.py

import re
import time
import sqlite3
import threading

from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


# ============================================================
# CONFIG
# ============================================================

DB_PATH = Path("odds.db")

_db_lock = threading.RLock()


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass

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


# ============================================================
# LOG
# ============================================================

def add_log(
    message,
    level="INFO"
):

    with _db_lock:

        conn = get_connection()

        try:

            conn.execute(
                """
                INSERT INTO collection_logs (
                    level,
                    message
                )
                VALUES (?, ?)
                """,
                (
                    str(level),
                    str(message)
                )
            )

            conn.commit()

        finally:

            conn.close()


def get_logs(limit=500):

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT
                created_at,
                level,
                message
            FROM collection_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),)
        ).fetchall()

        rows = list(reversed(rows))

        return "\n".join(
            f"[{row['created_at']}] "
            f"[{row['level']}] "
            f"{row['message']}"
            for row in rows
        )

    finally:

        conn.close()


# ============================================================
# HTTP
# ============================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),

    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,"
        "*/*;q=0.8"
    ),

    "Accept-Language":
        "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",

    "Connection":
        "keep-alive"
}


def fetch_url(
    url,
    timeout=30
):

    request = Request(
        url,
        headers=DEFAULT_HEADERS
    )

    with urlopen(
        request,
        timeout=timeout
    ) as response:

        raw = response.read()

        charset = (
            response.headers.get_content_charset()
        )

        if charset:

            try:

                return raw.decode(
                    charset,
                    errors="ignore"
                )

            except Exception:

                pass

        return raw.decode(
            "utf-8",
            errors="ignore"
        )


def fetch_url_with_status(
    url,
    timeout=30
):

    request = Request(
        url,
        headers=DEFAULT_HEADERS
    )

    with urlopen(
        request,
        timeout=timeout
    ) as response:

        raw = response.read()

        charset = (
            response.headers.get_content_charset()
        )

        if charset:

            try:

                text = raw.decode(
                    charset,
                    errors="ignore"
                )

            except Exception:

                text = raw.decode(
                    "utf-8",
                    errors="ignore"
                )

        else:

            text = raw.decode(
                "utf-8",
                errors="ignore"
            )

        return {
            "status": response.getcode(),
            "html": text
        }


# ============================================================
# 7M URL
# ============================================================

def get_7m_urls():

    return [

        "https://www.7m.com.cn/",

        "https://data.7m.com.cn/",

    ]


# ============================================================
# DATE
# ============================================================

def normalize_date(value):

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()

    if not text:
        return None

    text = text.replace(".", "-")
    text = text.replace("/", "-")

    try:

        return datetime.strptime(
            text[:10],
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return None


def parse_match_datetime(value):

    if not value:
        return None

    text = str(value).strip()

    numbers = re.findall(
        r"\d+",
        text
    )

    if len(numbers) < 6:
        return None

    try:

        return datetime(
            int(numbers[0]),
            int(numbers[1]),
            int(numbers[2]),
            int(numbers[3]),
            int(numbers[4]),
            int(numbers[5])
        )

    except ValueError:

        return None


# ============================================================
# RESULT
# ============================================================

def get_result(
    home_score,
    away_score
):

    try:

        home_score = int(home_score)
        away_score = int(away_score)

    except (
        TypeError,
        ValueError
    ):

        return "D"

    if home_score > away_score:
        return "H"

    if home_score < away_score:
        return "A"

    return "D"


# ============================================================
# ODDS
# ============================================================

def valid_odds(value):

    try:

        number = float(value)

        return (
            number > 1.0
            and number < 1000.0
        )

    except (
        TypeError,
        ValueError
    ):

        return False


def parse_odds(value):

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    text = text.replace(
        ",",
        ""
    )

    try:

        number = float(text)

        if not valid_odds(number):
            return None

        return number

    except (
        TypeError,
        ValueError
    ):

        return None


# ============================================================
# JS ARRAY
# ============================================================

def extract_dt_block(html):

    if not html:
        return None

    patterns = [

        r'\bvar\s+dt\s*=\s*(\[[\s\S]*?\])\s*;',

        r'\blet\s+dt\s*=\s*(\[[\s\S]*?\])\s*;',

        r'\bconst\s+dt\s*=\s*(\[[\s\S]*?\])\s*;',

        r'\bdt\s*=\s*(\[[\s\S]*?\])\s*;',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE
        )

        if match:

            return match.group(1)

    return None


def extract_script_blocks(html):

    if not html:
        return []

    return re.findall(
        r"<script[^>]*>([\s\S]*?)</script>",
        html,
        re.IGNORECASE
    )


def split_js_array_strings(
    array_text
):

    if not array_text:
        return []

    results = []

    current = []

    quote = None

    escaped = False

    text = array_text.strip()

    if text.startswith("["):
        text = text[1:]

    if text.endswith("]"):
        text = text[:-1]

    for char in text:

        if escaped:

            current.append(char)

            escaped = False

            continue

        if char == "\\" and quote:

            escaped = True

            continue

        if quote:

            if char == quote:

                quote = None

            else:

                current.append(char)

            continue

        if char in (
            '"',
            "'"
        ):

            quote = char

            continue

        if char == ",":

            value = "".join(
                current
            ).strip()

            if value:

                results.append(value)

            current = []

            continue

        current.append(char)

    value = "".join(
        current
    ).strip()

    if value:

        results.append(value)

    return results


# ============================================================
# ROW PARSER
# ============================================================

def parse_dt_row(raw):

    if not raw:
        return None

    parts = raw.split("|")

    if len(parts) < 14:
        return None

    try:

        match_id = parts[0].strip()

        dt_value = parts[1].strip()

        cid = parts[2].strip()

        league = parts[3].strip()

        home_id = parts[4].strip()

        away_id = parts[5].strip()

        home_team = parts[6].strip()

        away_team = parts[7].strip()

        home_score = parts[8].strip()

        away_score = parts[9].strip()

        half_score = parts[10].strip()

    except IndexError:

        return None

    match_datetime = parse_match_datetime(
        dt_value
    )

    if not match_datetime:
        return None

    # --------------------------------------------------------
    # 초기 배당
    # --------------------------------------------------------

    first_home = (
        parse_odds(parts[11])
        if len(parts) > 11
        else None
    )

    first_draw = (
        parse_odds(parts[12])
        if len(parts) > 12
        else None
    )

    first_away = (
        parse_odds(parts[13])
        if len(parts) > 13
        else None
    )

    # --------------------------------------------------------
    # 최종 배당
    # --------------------------------------------------------

    final_home = (
        parse_odds(parts[14])
        if len(parts) > 14
        else None
    )

    final_draw = (
        parse_odds(parts[15])
        if len(parts) > 15
        else None
    )

    final_away = (
        parse_odds(parts[16])
        if len(parts) > 16
        else None
    )

    # 최종배당 우선
    home_odds = (
        final_home
        if final_home is not None
        else first_home
    )

    draw_odds = (
        final_draw
        if final_draw is not None
        else first_draw
    )

    away_odds = (
        final_away
        if final_away is not None
        else first_away
    )

    if not (
        valid_odds(home_odds)
        and valid_odds(draw_odds)
        and valid_odds(away_odds)
    ):

        return None

    try:

        hs = int(home_score)

        aws = int(away_score)

    except (
        TypeError,
        ValueError
    ):

        return None

    result = get_result(
        hs,
        aws
    )

    home_probability = (
        1.0 / home_odds
    )

    draw_probability = (
        1.0 / draw_odds
    )

    away_probability = (
        1.0 / away_odds
    )

    return {

        "match_id":
            match_id,

        "match_key":
            match_id,

        "match_datetime":
            match_datetime,

        "match_date":
            match_datetime.date().isoformat(),

        "league":
            league,

        "cid":
            cid,

        "home_id":
            home_id,

        "away_id":
            away_id,

        "home_team":
            home_team,

        "away_team":
            away_team,

        "home_score":
            hs,

        "away_score":
            aws,

        "half_score":
            half_score,

        "result":
            result,

        "home_odds":
            home_odds,

        "draw_odds":
            draw_odds,

        "away_odds":
            away_odds,

        "home_probability":
            home_probability,

        "draw_probability":
            draw_probability,

        "away_probability":
            away_probability,

        "source":
            "7M"
    }


def parse_dt_from_html(html):

    block = extract_dt_block(
        html
    )

    if not block:

        return []

    raw_rows = split_js_array_strings(
        block
    )

    results = []

    for raw in raw_rows:

        try:

            row = parse_dt_row(
                raw
            )

            if row:

                results.append(row)

        except Exception as exc:

            add_log(
                f"dt 행 파싱 오류: {exc}",
                "WARNING"
            )

    return results


# ============================================================
# DATE FILTER
# ============================================================

def filter_matches_by_date(
    rows,
    target_date
):

    target = normalize_date(
        target_date
    )

    if not target:
        return []

    results = []

    for row in rows:

        row_date = normalize_date(
            row.get("match_date")
        )

        if row_date == target:

            results.append(row)

    return results


# ============================================================
# SAVE MATCH
# ============================================================

def save_match(row):

    match_key = row.get(
        "match_key"
    )

    if not match_key:

        match_key = "|".join([

            str(row.get(
                "match_date",
                ""
            )),

            str(row.get(
                "home_team",
                ""
            )),

            str(row.get(
                "away_team",
                ""
            )),

            str(row.get(
                "home_score",
                ""
            )),

            str(row.get(
                "away_score",
                ""
            )),

            str(row.get(
                "home_odds",
                ""
            )),

            str(row.get(
                "draw_odds",
                ""
            )),

            str(row.get(
                "away_odds",
                ""
            )),

            str(row.get(
                "result",
                ""
            ))
        ])

    with _db_lock:

        conn = get_connection()

        try:

            cur = conn.execute(
                """
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
                """,
                (

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

                    row.get(
                        "home_score"
                    ),

                    row.get(
                        "away_score"
                    ),

                    row.get(
                        "result",
                        "D"
                    ),

                    float(
                        row["home_odds"]
                    ),

                    float(
                        row["draw_odds"]
                    ),

                    float(
                        row["away_odds"]
                    ),

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
                )
            )

            conn.commit()

            return cur.rowcount

        finally:

            conn.close()


# ============================================================
# QUERY
# ============================================================

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

        rows = conn.execute(
            """
            SELECT *
            FROM matches
            ORDER BY match_date DESC, id DESC
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


def get_all_odds():

    conn = get_connection()

    try:

        rows = conn.execute(
            """
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
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


def get_company_names():

    if get_match_count():

        return ["7M"]

    return []


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

        rows = conn.execute(
            """
            SELECT *
            FROM matches

            WHERE ABS(home_odds - ?) < ?
              AND ABS(draw_odds - ?) < ?
              AND ABS(away_odds - ?) < ?

            ORDER BY match_date DESC, id DESC
            """,
            (

                float(home_odds),
                tolerance,

                float(draw_odds),
                tolerance,

                float(away_odds),
                tolerance
            )
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# COLLECTION DAY
# ============================================================

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

            conn.execute(
                """
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
                """,
                (

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
                )
            )

            conn.commit()

        finally:

            conn.close()


# ============================================================
# COLLECTION STATE
# ============================================================

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

            conn.execute(
                """
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

                    start_date =
                        excluded.start_date,

                    end_date =
                        excluded.end_date,

                    last_completed_date =
                        excluded.last_completed_date,

                    running =
                        excluded.running,

                    stopped =
                        excluded.stopped,

                    updated_at =
                        CURRENT_TIMESTAMP
                """,
                (

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
                )
            )

            conn.commit()

        finally:

            conn.close()


def get_collection_state():

    conn = get_connection()

    try:

        row = conn.execute(
            """
            SELECT *
            FROM collection_state
            WHERE id = 1
            """
        ).fetchone()

        return (
            dict(row)
            if row
            else {}
        )

    finally:

        conn.close()


# ============================================================
# HTML COLLECTION
# ============================================================

def collect_html(
    html,
    target_date=None
):

    rows = parse_dt_from_html(
        html
    )

    if target_date is not None:

        rows = filter_matches_by_date(
            rows,
            target_date
        )

    found = len(rows)

    saved = 0

    for row in rows:

        try:

            saved += save_match(
                row
            )

        except Exception as exc:

            add_log(
                f"경기 저장 실패 "
                f"{row.get('match_id')}: {exc}",
                "ERROR"
            )

    return {
        "found": found,
        "saved": saved,
        "rows": rows
    }


# ============================================================
# URL COLLECTION
# ============================================================

def collect_url(
    url,
    target_date=None
):

    add_log(
        f"7M 요청: {url}"
    )

    try:

        response = fetch_url_with_status(
            url
        )

        status = response["status"]

        html = response["html"]

    except HTTPError as exc:

        add_log(
            f"HTTP 오류: {exc.code}",
            "ERROR"
        )

        raise

    except URLError as exc:

        add_log(
            f"네트워크 오류: {exc}",
            "ERROR"
        )

        raise

    except Exception as exc:

        add_log(
            f"페이지 요청 실패: {exc}",
            "ERROR"
        )

        raise

    if status != 200:

        raise RuntimeError(
            f"HTTP {status}"
        )

    add_log(
        f"HTML 수신: {len(html):,} bytes"
    )

    result = collect_html(
        html,
        target_date
    )

    add_log(
        f"7M 후보 {result['found']}건 / "
        f"신규 저장 {result['saved']}건"
    )

    return result


# ============================================================
# COLLECT DAY
# ============================================================

def collect_day(
    target_date,
    cid=""
):

    target = normalize_date(
        target_date
    )

    if not target:

        raise ValueError(
            "잘못된 날짜입니다."
        )

    save_collection_day(
        target,
        "RUNNING",
        0,
        0,
        ""
    )

    last_error = ""

    # --------------------------------------------------------
    # 메인 페이지 후보
    # --------------------------------------------------------

    urls = get_7m_urls()

    for url in urls:

        try:

            result = collect_url(
                url,
                target
            )

            found = result["found"]

            saved = result["saved"]

            # 데이터가 발견되면 종료
            if found > 0:

                save_collection_day(
                    target,
                    "DONE",
                    found,
                    saved,
                    ""
                )

                return {
                    "found": found,
                    "saved": saved,
                    "rows": result["rows"]
                }

            # 200인데 데이터가 없는 경우
            # 다음 URL도 확인

        except Exception as exc:

            last_error = str(exc)

            add_log(
                f"{target} "
                f"{url} 실패: {exc}",
                "WARNING"
            )

    # --------------------------------------------------------
    # 모든 URL에서 데이터 없음
    # --------------------------------------------------------

    if last_error:

        save_collection_day(
            target,
            "ERROR",
            0,
            0,
            last_error
        )

        raise RuntimeError(
            last_error
        )

    save_collection_day(
        target,
        "DONE",
        0,
        0,
        ""
    )

    return {
        "found": 0,
        "saved": 0,
        "rows": []
    }


# ============================================================
# RANGE COLLECTION
# ============================================================

def date_range(
    start_date,
    end_date
):

    current = normalize_date(
        start_date
    )

    end = normalize_date(
        end_date
    )

    if not current or not end:
        return

    while current <= end:

        yield current

        current += timedelta(
            days=1
        )


def collect_range(
    start_date,
    end_date,
    url=None,
    retry_count=1,
    retry_delay=1.0,
    stop_event=None
):

    start = normalize_date(
        start_date
    )

    end = normalize_date(
        end_date
    )

    if not start or not end:

        raise ValueError(
            "잘못된 시작/종료 날짜"
        )

    if start > end:

        raise ValueError(
            "시작 날짜가 종료 날짜보다 늦습니다."
        )

    save_collection_state(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        last_completed_date=None,
        running=True,
        stopped=False
    )

    total_found = 0
    total_saved = 0

    last_completed = None
    stopped = False

    try:

        for target_date in date_range(
            start,
            end
        ):

            if stop_event is not None:

                if stop_event.is_set():

                    stopped = True

                    add_log(
                        "수집 중지 요청",
                        "WARNING"
                    )

                    break

            success = False
            last_error = ""

            for attempt in range(
                retry_count + 1
            ):

                try:

                    if url:

                        result = collect_url(
                            url,
                            target_date
                        )

                    else:

                        result = collect_day(
                            target_date
                        )

                    found = int(
                        result.get(
                            "found",
                            0
                        )
                    )

                    saved = int(
                        result.get(
                            "saved",
                            0
                        )
                    )

                    total_found += found
                    total_saved += saved

                    last_completed = (
                        target_date.isoformat()
                    )

                    save_collection_state(
                        start_date=start.isoformat(),
                        end_date=end.isoformat(),
                        last_completed_date=(
                            last_completed
                        ),
                        running=True,
                        stopped=False
                    )

                    success = True

                    break

                except Exception as exc:

                    last_error = str(exc)

                    add_log(
                        f"{target_date} "
                        f"수집 실패 "
                        f"({attempt + 1}/"
                        f"{retry_count + 1}): "
                        f"{exc}",
                        "ERROR"
                    )

                    if attempt < retry_count:

                        time.sleep(
                            float(retry_delay)
                        )

            if not success:

                save_collection_day(
                    target_date,
                    "ERROR",
                    0,
                    0,
                    last_error
                )

                add_log(
                    f"{target_date} 최종 실패",
                    "ERROR"
                )

                # 다음 날짜로 진행

    finally:

        save_collection_state(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            last_completed_date=last_completed,
            running=False,
            stopped=stopped
        )

    return {
        "found": total_found,
        "saved": total_saved
    }


# ============================================================
# DIAGNOSTIC
# ============================================================

def diagnose(
    target_date,
    cid=""
):

    target = normalize_date(
        target_date
    )

    if not target:

        return {
            "status": 0,
            "html_size": 0,
            "size": 0,
            "found": 0,
            "html": "",
            "js": "",
            "error": "잘못된 진단 날짜입니다."
        }

    last_error = ""

    html = ""

    status = 0

    used_url = ""

    # --------------------------------------------------------
    # 중요:
    # 별도의 History JS URL을 추측해서 요청하지 않는다.
    # 404의 원인이 되었던 잘못된 URL을 제거한다.
    # --------------------------------------------------------

    for url in get_7m_urls():

        try:

            result = fetch_url_with_status(
                url
            )

            status = result["status"]

            candidate_html = result["html"]

            if status == 200 and candidate_html:

                html = candidate_html

                used_url = url

                break

            last_error = (
                f"HTTP 오류: {status}"
            )

        except HTTPError as exc:

            status = exc.code

            last_error = (
                f"HTTP 오류: {exc.code}"
            )

        except URLError as exc:

            last_error = (
                f"네트워크 오류: {exc}"
            )

        except Exception as exc:

            last_error = str(exc)

    if not html:

        return {
            "status": status,
            "html_size": 0,
            "size": 0,
            "found": 0,
            "html": "",
            "js": "",
            "error": last_error or "HTML 수신 실패"
        }

    # --------------------------------------------------------
    # dt
    # --------------------------------------------------------

    dt_block = extract_dt_block(
        html
    )

    rows = parse_dt_from_html(
        html
    )

    # --------------------------------------------------------
    # script
    # --------------------------------------------------------

    scripts = extract_script_blocks(
        html
    )

    js_text = "\n\n".join(
        scripts
    )

    if dt_block:

        js_text = dt_block

    # --------------------------------------------------------
    # 진단 로그
    # --------------------------------------------------------

    add_log(
        f"진단 URL: {used_url}"
    )

    add_log(
        f"진단 HTTP: {status}"
    )

    add_log(
        f"진단 HTML: {len(html):,}"
    )

    add_log(
        f"dt 발견: {bool(dt_block)}"
    )

    add_log(
        f"경기 후보: {len(rows):,}"
    )

    return {

        "status":
            status,

        "html_size":
            len(html),

        "size":
            len(js_text),

        "found":
            len(rows),

        "html":
            html,

        "js":
            js_text,

        "error":
            ""
    }


def diagnose_html(
    html
):

    if not html:

        return {
            "html_length": 0,
            "dt_found": False,
            "dt_length": 0,
            "candidate_count": 0,
            "sample": []
        }

    dt_block = extract_dt_block(
        html
    )

    rows = parse_dt_from_html(
        html
    )

    return {

        "html_length":
            len(html),

        "dt_found":
            bool(dt_block),

        "dt_length":
            len(dt_block)
            if dt_block
            else 0,

        "candidate_count":
            len(rows),

        "sample":
            rows[:5]
    }


def diagnose_url(
    url
):

    html = fetch_url(
        url
    )

    return diagnose_html(
        html
    )


# ============================================================
# NOTE
# ============================================================
#
# 여기에서 init_db()를 실행하지 않는다.
#
# app.py에서:
#
#     database.init_db()
#
# 를 실행한다.
#
# ============================================================
