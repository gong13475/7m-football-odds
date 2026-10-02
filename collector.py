# collector.py
# ============================================================
# 7M Football Collector
# SSL timeout / JS discovery / dt parser / SQLite compatible
# ============================================================

import re
import time
import json
import ssl
import socket
import sqlite3
import threading

from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

from urllib.request import (
    Request,
    urlopen
)

from urllib.error import (
    HTTPError,
    URLError
)


# ============================================================
# OPTIONAL REQUESTS
# ============================================================

try:
    import requests

    REQUESTS_AVAILABLE = True

except Exception:

    requests = None
    REQUESTS_AVAILABLE = False


# ============================================================
# DATABASE
# ============================================================

DB_PATH = Path("odds.db")

_db_lock = threading.RLock()


def get_connection():

    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=60,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    try:
        conn.execute(
            "PRAGMA journal_mode=WAL"
        )

        conn.execute(
            "PRAGMA synchronous=NORMAL"
        )

        conn.execute(
            "PRAGMA busy_timeout=60000"
        )

    except Exception:
        pass

    return conn


def init_db():

    with _db_lock:

        conn = get_connection()

        try:

            conn.executescript(
                """

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

                """
            )

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
                INSERT INTO collection_logs(
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

        except Exception:

            pass

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
            (
                int(limit),
            )
        ).fetchall()

        rows = list(
            reversed(rows)
        )

        return "\n".join(
            (
                f"[{row['created_at']}] "
                f"[{row['level']}] "
                f"{row['message']}"
            )
            for row in rows
        )

    finally:

        conn.close()


# ============================================================
# HTTP HEADERS
# ============================================================

DEFAULT_HEADERS = {

    "User-Agent":
        (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        ),

    "Accept":
        (
            "text/html,"
            "application/xhtml+xml,"
            "application/xml;q=0.9,"
            "image/avif,"
            "image/webp,"
            "image/apng,"
            "*/*;q=0.8"
        ),

    "Accept-Language":
        "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",

    "Cache-Control":
        "no-cache",

    "Pragma":
        "no-cache",

    "Connection":
        "keep-alive",
}


# ============================================================
# 7M URLS
# ============================================================

DEFAULT_7M_URLS = [

    "https://kr.7msport.com/",

    "https://kr.7msport.com/default_odds_kr.aspx",

    "https://live.7msport.com/default_kr.aspx",

    "https://live.7mkr.com/",

    "https://www.7msport.com/",

]


# ============================================================
# URL NORMALIZATION
# ============================================================

def normalize_url(
    url
):

    if not url:
        return ""

    url = str(url).strip()

    if not url:
        return ""

    if url.startswith("//"):

        url = "https:" + url

    elif url.startswith("/"):

        url = urljoin(
            DEFAULT_7M_URLS[0],
            url
        )

    elif not re.match(
        r"^https?://",
        url,
        re.IGNORECASE
    ):

        url = "https://" + url

    return url


# ============================================================
# REQUEST WITH REQUESTS
# ============================================================

def fetch_with_requests(
    url,
    timeout=60
):

    if not REQUESTS_AVAILABLE:

        raise RuntimeError(
            "requests 패키지가 설치되어 있지 않습니다."
        )

    session = requests.Session()

    session.headers.update(
        DEFAULT_HEADERS
    )

    try:

        response = session.get(
            url,
            timeout=(
                20,
                timeout
            ),
            allow_redirects=True
        )

        response.raise_for_status()

        response.encoding = (
            response.apparent_encoding
            or response.encoding
            or "utf-8"
        )

        return {
            "url":
                response.url,

            "status":
                response.status_code,

            "text":
                response.text,

            "headers":
                dict(response.headers)
        }

    finally:

        session.close()


# ============================================================
# REQUEST WITH URLLIB
# ============================================================

def fetch_with_urllib(
    url,
    timeout=60
):

    request = Request(
        normalize_url(url),
        headers=DEFAULT_HEADERS,
        method="GET"
    )

    context = ssl.create_default_context()

    with urlopen(
        request,
        timeout=timeout,
        context=context
    ) as response:

        raw = response.read()

        charset = (
            response.headers
            .get_content_charset()
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
            "url":
                response.geturl(),

            "status":
                getattr(
                    response,
                    "status",
                    200
                ),

            "text":
                text,

            "headers":
                dict(response.headers)
        }


# ============================================================
# HTTP FETCH
# ============================================================

def fetch_url(
    url,
    timeout=60,
    retries=3,
    delay=2.0
):

    url = normalize_url(url)

    if not url:

        raise ValueError(
            "URL이 비어 있습니다."
        )


    last_error = None


    for attempt in range(
        int(retries) + 1
    ):

        try:

            add_log(
                f"HTTP 요청 "
                f"{attempt + 1}/"
                f"{int(retries) + 1}: "
                f"{url}"
            )


            # ------------------------------------------------
            # requests 우선
            # ------------------------------------------------

            if REQUESTS_AVAILABLE:

                try:

                    result = fetch_with_requests(
                        url,
                        timeout=timeout
                    )

                    add_log(
                        f"HTTP {result['status']} "
                        f"/ "
                        f"{len(result['text']):,} bytes"
                    )

                    return result

                except Exception as exc:

                    last_error = exc

                    add_log(
                        f"requests 실패: {exc}",
                        "WARNING"
                    )


            # ------------------------------------------------
            # urllib fallback
            # ------------------------------------------------

            try:

                result = fetch_with_urllib(
                    url,
                    timeout=timeout
                )

                add_log(
                    f"urllib HTTP "
                    f"{result['status']} "
                    f"/ "
                    f"{len(result['text']):,} bytes"
                )

                return result

            except Exception as exc:

                last_error = exc

                add_log(
                    f"urllib 실패: {exc}",
                    "WARNING"
                )


        except Exception as exc:

            last_error = exc

            add_log(
                f"HTTP 예외: {exc}",
                "WARNING"
            )


        if attempt < int(retries):

            wait = (
                float(delay)
                * (2 ** attempt)
            )

            add_log(
                f"{wait:.1f}초 후 재시도"
            )

            time.sleep(
                wait
            )


    raise last_error


# ============================================================
# SAFE FETCH
# ============================================================

def safe_fetch(
    url,
    timeout=60,
    retries=3
):

    try:

        return fetch_url(
            url,
            timeout=timeout,
            retries=retries
        )

    except HTTPError as exc:

        message = (
            f"HTTP 오류: "
            f"{getattr(exc, 'code', 0)}"
        )

        add_log(
            message,
            "ERROR"
        )

        return {
            "url":
                url,

            "status":
                getattr(
                    exc,
                    "code",
                    0
                ),

            "text":
                "",

            "headers":
                {},

            "error":
                message
        }

    except Exception as exc:

        message = (
            f"네트워크 오류: {exc}"
        )

        add_log(
            message,
            "ERROR"
        )

        return {
            "url":
                url,

            "status":
                0,

            "text":
                "",

            "headers":
                {},

            "error":
                message
        }


# ============================================================
# DATE
# ============================================================

def normalize_date(
    value
):

    if value is None:
        return None

    if isinstance(
        value,
        datetime
    ):

        return value.date()

    if isinstance(
        value,
        date
    ):

        return value

    text = str(
        value
    ).strip()

    if not text:
        return None

    text = text.replace(
        ".",
        "-"
    )

    text = text.replace(
        "/",
        "-"
    )

    match = re.search(
        r"(\d{4})-(\d{1,2})-(\d{1,2})",
        text
    )

    if not match:
        return None

    try:

        return date(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3))
        )

    except ValueError:

        return None


def parse_match_datetime(
    value
):

    if not value:
        return None

    text = str(
        value
    ).strip()

    # 2026,10,01,13,00,00
    numbers = re.findall(
        r"\d+",
        text
    )

    if len(numbers) >= 6:

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

            pass


    # 2026-10-01 13:00:00
    patterns = [

        "%Y-%m-%d %H:%M:%S",

        "%Y/%m/%d %H:%M:%S",

        "%Y.%m.%d %H:%M:%S",

        "%Y-%m-%dT%H:%M:%S",

    ]


    for pattern in patterns:

        try:

            return datetime.strptime(
                text[:19],
                pattern
            )

        except ValueError:

            continue


    return None


# ============================================================
# RESULT
# ============================================================

def get_result(
    home_score,
    away_score
):

    try:

        hs = int(
            home_score
        )

        aws = int(
            away_score
        )

    except (
        TypeError,
        ValueError
    ):

        return "D"

    if hs > aws:
        return "H"

    if hs < aws:
        return "A"

    return "D"


# ============================================================
# ODDS
# ============================================================

def valid_odds(
    value
):

    try:

        number = float(
            value
        )

        return (
            number > 1.0
            and number < 1000.0
        )

    except (
        TypeError,
        ValueError
    ):

        return False


def parse_odds(
    value
):

    if value is None:
        return None

    text = str(
        value
    ).strip()

    if not text:
        return None

    # 숫자 하나만 추출
    match = re.search(
        r"\d+(?:\.\d+)?",
        text
    )

    if not match:
        return None

    try:

        number = float(
            match.group(0)
        )

    except ValueError:

        return None

    if not valid_odds(
        number
    ):

        return None

    return number


# ============================================================
# JS ARRAY EXTRACTION
# ============================================================

def extract_balanced_array(
    text,
    start
):

    if not text:
        return None

    if start < 0:
        return None

    opening = text.find(
        "[",
        start
    )

    if opening < 0:
        return None

    depth = 0
    quote = None
    escaped = False

    for index in range(
        opening,
        len(text)
    ):

        char = text[index]

        if escaped:

            escaped = False
            continue

        if quote:

            if char == "\\":
                escaped = True
                continue

            if char == quote:
                quote = None

            continue

        if char in (
            '"',
            "'",
            "`"
        ):

            quote = char
            continue

        if char == "[":
            depth += 1

        elif char == "]":

            depth -= 1

            if depth == 0:

                return text[
                    opening:index + 1
                ]

    return None


def extract_dt_block(
    html
):

    if not html:
        return None


    patterns = [

        r"\bvar\s+dt\s*=",

        r"\blet\s+dt\s*=",

        r"\bconst\s+dt\s*=",

        r"\bdt\s*=",

        r"\bDT\s*=",

    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE
        )

        if match:

            result = extract_balanced_array(
                html,
                match.end()
            )

            if result:

                return result


    return None


# ============================================================
# JS STRING ARRAY PARSER
# ============================================================

def split_js_array_strings(
    array_text
):

    if not array_text:
        return []

    text = array_text.strip()

    if text.startswith("["):
        text = text[1:]

    if text.endswith("]"):
        text = text[:-1]


    results = []

    current = []

    quote = None

    escaped = False


    for char in text:

        if escaped:

            # JS escape 처리
            if char == "n":
                current.append("\n")

            elif char == "r":
                current.append("\r")

            elif char == "t":
                current.append("\t")

            else:
                current.append(char)

            escaped = False

            continue


        if quote:

            if char == "\\":

                escaped = True

                continue

            if char == quote:

                quote = None

            else:

                current.append(
                    char
                )

            continue


        if char in (
            '"',
            "'",
            "`"
        ):

            quote = char

            continue


        if char == ",":

            value = "".join(
                current
            ).strip()

            if value:

                results.append(
                    value
                )

            current = []

            continue


        current.append(
            char
        )


    value = "".join(
        current
    ).strip()

    if value:

        results.append(
            value
        )

    return results


# ============================================================
# ROW PARSER
# ============================================================

def parse_dt_row(
    raw
):

    if not raw:
        return None

    raw = str(
        raw
    ).strip()

    if "|" not in raw:
        return None

    parts = [
        x.strip()
        for x in raw.split("|")
    ]


    if len(parts) < 14:
        return None


    try:

        match_id = parts[0]

        dt_value = parts[1]

        cid = parts[2]

        league = parts[3]

        home_id = parts[4]

        away_id = parts[5]

        home_team = parts[6]

        away_team = parts[7]

        home_score = parts[8]

        away_score = parts[9]

        half_score = parts[10]

    except Exception:

        return None


    match_datetime = parse_match_datetime(
        dt_value
    )

    if not match_datetime:
        return None


    # --------------------------------------------------------
    # odds
    # --------------------------------------------------------

    odds = []

    for index in range(
        11,
        min(
            len(parts),
            30
        )
    ):

        value = parse_odds(
            parts[index]
        )

        if value is not None:

            odds.append(
                value
            )


    if len(odds) < 3:
        return None


    # 기존 7M 구조:
    #
    # [11:14] 초기
    # [14:17] 최종
    #
    # 최종 3개가 존재하면 사용
    # 아니면 첫 3개 사용


    first = odds[:3]

    final = (
        odds[3:6]
        if len(odds) >= 6
        else []
    )


    if len(final) >= 3:

        home_odds = final[0]
        draw_odds = final[1]
        away_odds = final[2]

    else:

        home_odds = first[0]
        draw_odds = first[1]
        away_odds = first[2]


    if not (
        valid_odds(home_odds)
        and valid_odds(draw_odds)
        and valid_odds(away_odds)
    ):

        return None


    try:

        hs = int(
            re.search(
                r"-?\d+",
                home_score
            ).group(0)
        )

        aws = int(
            re.search(
                r"-?\d+",
                away_score
            ).group(0)
        )

    except Exception:

        return None


    result = get_result(
        hs,
        aws
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
            1.0 / home_odds,

        "draw_probability":
            1.0 / draw_odds,

        "away_probability":
            1.0 / away_odds,

        "source":
            "7M",
    }


# ============================================================
# GENERIC PIPE-DATA FINDER
# ============================================================

def find_pipe_rows(
    html
):

    if not html:
        return []

    results = []

    seen = set()


    # --------------------------------------------------------
    # 긴 문자열 안에서
    # ID|YYYY,MM,DD,HH,MM,SS|...
    # 형태를 찾는다.
    # --------------------------------------------------------

    pattern = re.compile(
        r"""
        (?P<quote>["'`])
        (?P<data>
            \d+
            \|
            \d{4}[,\-/.]\d{1,2}[,\-/.]\d{1,2}
            [,\sT]+\d{1,2}[,:]\d{1,2}[,:]\d{1,2}
            \|
            [^"'`]{1,2000}
        )
        (?P=quote)
        """,
        re.VERBOSE
    )


    for match in pattern.finditer(
        html
    ):

        value = (
            match.group("data")
            .strip()
        )

        if "|" not in value:
            continue

        if value in seen:
            continue

        seen.add(value)

        row = parse_dt_row(
            value
        )

        if row:

            results.append(
                row
            )


    return results


# ============================================================
# DT PARSER
# ============================================================

def parse_dt_from_html(
    html
):

    if not html:
        return []


    results = []

    seen = set()


    # --------------------------------------------------------
    # 1. dt array
    # --------------------------------------------------------

    block = extract_dt_block(
        html
    )


    if block:

        raw_rows = split_js_array_strings(
            block
        )


        for raw in raw_rows:

            try:

                row = parse_dt_row(
                    raw
                )

                if not row:
                    continue

                key = row[
                    "match_key"
                ]

                if key in seen:
                    continue

                seen.add(key)

                results.append(
                    row
                )

            except Exception as exc:

                add_log(
                    f"dt 파싱 오류: {exc}",
                    "WARNING"
                )


    # --------------------------------------------------------
    # 2. generic pipe scan
    # --------------------------------------------------------

    if not results:

        generic_rows = find_pipe_rows(
            html
        )


        for row in generic_rows:

            key = row[
                "match_key"
            ]

            if key in seen:
                continue

            seen.add(key)

            results.append(
                row
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


    result = []


    for row in rows:

        row_date = normalize_date(
            row.get("match_date")
        )

        if row_date == target:

            result.append(
                row
            )


    return result


# ============================================================
# CID FILTER
# ============================================================

def filter_matches_by_cid(
    rows,
    cid=""
):

    cid = str(
        cid or ""
    ).strip()

    if not cid:
        return rows


    result = []


    for row in rows:

        row_cid = str(
            row.get(
                "cid",
                ""
            )
        ).strip()

        if row_cid == cid:

            result.append(
                row
            )


    return result


# ============================================================
# SAVE MATCH
# ============================================================

def save_match(
    row
):

    match_key = row.get(
        "match_key"
    )


    if not match_key:

        match_key = "|".join(

            str(
                row.get(
                    key,
                    ""
                )
            )

            for key in [

                "match_date",
                "home_team",
                "away_team",
                "home_score",
                "away_score",
                "home_odds",
                "draw_odds",
                "away_odds",
                "result"

            ]

        )


    with _db_lock:

        conn = get_connection()

        try:

            cur = conn.execute(
                """
                INSERT OR IGNORE INTO matches(

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

                VALUES(
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
                        row[
                            "home_odds"
                        ]
                    ),

                    float(
                        row[
                            "draw_odds"
                        ]
                    ),

                    float(
                        row[
                            "away_odds"
                        ]
                    ),

                    float(
                        row[
                            "home_probability"
                        ]
                    ),

                    float(
                        row[
                            "draw_probability"
                        ]
                    ),

                    float(
                        row[
                            "away_probability"
                        ]
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
            """
            SELECT COUNT(*)
            FROM matches
            """
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
            ORDER BY
                match_date DESC,
                id DESC
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

            ORDER BY
                match_date DESC,
                id DESC
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

        return [
            "7M"
        ]

    return []


def get_company_counts():

    count = get_match_count()

    if not count:
        return {}

    return {
        "7M":
            count
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

            ORDER BY
                match_date DESC,
                id DESC
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
                INSERT INTO collection_days(

                    match_date,
                    status,
                    found,
                    saved,
                    error,
                    updated_at

                )

                VALUES(
                    ?, ?, ?, ?, ?,
                    CURRENT_TIMESTAMP
                )

                ON CONFLICT(match_date)

                DO UPDATE SET

                    status =
                        excluded.status,

                    found =
                        excluded.found,

                    saved =
                        excluded.saved,

                    error =
                        excluded.error,

                    updated_at =
                        CURRENT_TIMESTAMP
                """,
                (

                    (
                        target_date.isoformat()
                        if hasattr(
                            target_date,
                            "isoformat"
                        )
                        else str(
                            target_date
                        )
                    ),

                    status,

                    int(found),

                    int(saved),

                    str(
                        error or ""
                    )

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
                INSERT INTO collection_state(

                    id,
                    start_date,
                    end_date,
                    last_completed_date,
                    running,
                    stopped

                )

                VALUES(
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

                    int(
                        bool(running)
                    ),

                    int(
                        bool(stopped)
                    )

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
    target_date=None,
    cid=""
):

    rows = parse_dt_from_html(
        html
    )


    if cid:

        rows = filter_matches_by_cid(
            rows,
            cid
        )


    if target_date is not None:

        rows = filter_matches_by_date(
            rows,
            target_date
        )


    found = len(
        rows
    )

    saved = 0


    for row in rows:

        try:

            saved += save_match(
                row
            )

        except Exception as exc:

            add_log(
                (
                    "경기 저장 실패 "
                    f"{row.get('match_id')}: "
                    f"{exc}"
                ),
                "ERROR"
            )


    return {

        "found":
            found,

        "saved":
            saved,

        "rows":
            rows
    }


# ============================================================
# COLLECT URL
# ============================================================

def collect_url(
    url,
    target_date=None,
    cid=""
):

    response = fetch_url(
        url,
        timeout=60,
        retries=3
    )


    html = response[
        "text"
    ]


    add_log(
        (
            f"HTML 수신 "
            f"{len(html):,} bytes"
        )
    )


    result = collect_html(
        html,
        target_date,
        cid
    )


    add_log(
        (
            f"7M 후보 "
            f"{result['found']}건 / "
            f"신규 저장 "
            f"{result['saved']}건"
        )
    )


    return result


# ============================================================
# DATE RANGE
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


# ============================================================
# URL DISCOVERY
# ============================================================

def extract_script_urls(
    html,
    base_url
):

    if not html:
        return []


    urls = []

    seen = set()


    patterns = [

        r'<script[^>]+src\s*=\s*["\']([^"\']+)["\']',

        r'<iframe[^>]+src\s*=\s*["\']([^"\']+)["\']',

        r'<link[^>]+href\s*=\s*["\']([^"\']+)["\']',

    ]


    for pattern in patterns:

        for match in re.finditer(
            pattern,
            html,
            re.IGNORECASE
        ):

            src = (
                match.group(1)
                .strip()
            )


            if not src:
                continue


            full = urljoin(
                base_url,
                src
            )


            if full in seen:
                continue


            seen.add(
                full
            )


            # JS/data 관련 URL 우선
            lower = full.lower()


            if (
                ".js" in lower
                or "data" in lower
                or "score" in lower
                or "odds" in lower
                or "history" in lower
                or "live" in lower
                or "ajax" in lower
                or "match" in lower
            ):

                urls.append(
                    full
                )


    return urls


# ============================================================
# JS CANDIDATE FETCH
# ============================================================

def fetch_candidate_js(
    html,
    base_url,
    max_files=12
):

    urls = extract_script_urls(
        html,
        base_url
    )


    results = []


    for url in urls[:
        max_files
    ]:

        try:

            response = safe_fetch(
                url,
                timeout=30,
                retries=1
            )


            if response.get(
                "status"
            ) != 200:

                continue


            text = response.get(
                "text",
                ""
            )


            if not text:
                continue


            results.append({

                "url":
                    response.get(
                        "url",
                        url
                    ),

                "status":
                    response.get(
                        "status",
                        0
                    ),

                "text":
                    text,

                "size":
                    len(text)

            })


        except Exception as exc:

            add_log(
                (
                    f"JS 요청 실패 "
                    f"{url}: {exc}"
                ),
                "WARNING"
            )


    return results


# ============================================================
# FIND BEST URL
# ============================================================

def find_working_7m_url():

    errors = []


    for url in DEFAULT_7M_URLS:

        response = safe_fetch(
            url,
            timeout=30,
            retries=1
        )


        if response.get(
            "status"
        ) == 200:

            text = response.get(
                "text",
                ""
            )


            if len(text) > 1000:

                return {
                    "url":
                        response.get(
                            "url",
                            url
                        ),

                    "status":
                        200,

                    "html":
                        text
                }


        if response.get(
            "error"
        ):

            errors.append(
                response[
                    "error"
                ]
            )


    return {

        "url":
            "",

        "status":
            0,

        "html":
            "",

        "error":
            (
                errors[-1]
                if errors
                else
                "7M URL을 찾지 못했습니다."
            )
    }


# ============================================================
# DIAGNOSTIC
# ============================================================

def diagnose_html(
    html,
    base_url=""
):

    if not html:

        return {

            "html_length":
                0,

            "dt_found":
                False,

            "dt_length":
                0,

            "candidate_count":
                0,

            "sample":
                [],

            "js":
                "",

            "js_size":
                0,

            "script_count":
                0,

            "script_urls":
                []

        }


    dt_block = extract_dt_block(
        html
    )


    rows = parse_dt_from_html(
        html
    )


    js_results = []


    if base_url:

        try:

            js_results = fetch_candidate_js(
                html,
                base_url
            )

        except Exception as exc:

            add_log(
                f"JS 탐색 실패: {exc}",
                "WARNING"
            )


    # --------------------------------------------------------
    # HTML 자체에서 발견되지 않은 경우
    # JS 후보에서도 파싱
    # --------------------------------------------------------

    all_js_rows = []


    for item in js_results:

        text = item.get(
            "text",
            ""
        )


        parsed = parse_dt_from_html(
            text
        )


        if parsed:

            all_js_rows.extend(
                parsed
            )


    combined = []

    seen = set()


    for row in (
        rows
        + all_js_rows
    ):

        key = row.get(
            "match_key"
        )


        if key in seen:
            continue


        seen.add(
            key
        )


        combined.append(
            row
        )


    js_text = ""


    if js_results:

        # 진단 화면에서 너무 큰 응답을
        # 그대로 반환하지 않도록 제한
        js_text = max(
            js_results,
            key=lambda x:
                x.get(
                    "size",
                    0
                )
        ).get(
            "text",
            ""
        )


    return {

        "html_length":
            len(html),

        "dt_found":
            bool(dt_block),

        "dt_length":
            (
                len(dt_block)
                if dt_block
                else 0
            ),

        "candidate_count":
            len(combined),

        "sample":
            combined[:5],

        "js":
            js_text,

        "js_size":
            len(js_text),

        "script_count":
            len(js_results),

        "script_urls":
            [
                item.get(
                    "url",
                    ""
                )
                for item in js_results
            ]

    }


def diagnose_url(
    url
):

    response = safe_fetch(
        url,
        timeout=60,
        retries=3
    )


    if response.get(
        "status"
    ) != 200:

        return {

            "status":
                response.get(
                    "status",
                    0
                ),

            "html_size":
                0,

            "size":
                0,

            "found":
                0,

            "error":
                response.get(
                    "error",
                    "HTTP 오류"
                ),

            "html":
                "",

            "js":
                ""

        }


    html = response.get(
        "text",
        ""
    )


    detail = diagnose_html(
        html,
        response.get(
            "url",
            url
        )
    )


    return {

        "status":
            response.get(
                "status",
                200
            ),

        "html_size":
            detail[
                "html_length"
            ],

        "size":
            detail[
                "js_size"
            ],

        "found":
            detail[
                "candidate_count"
            ],

        "error":
            "",

        "html":
            html,

        "js":
            detail[
                "js"
            ],

        "script_count":
            detail[
                "script_count"
            ],

        "script_urls":
            detail[
                "script_urls"
            ],

        "sample":
            detail[
                "sample"
            ]

    }


# ============================================================
# APP COMPATIBLE DIAGNOSE
# ============================================================

def diagnose(
    target_date=None,
    cid=""
):

    """
    app.py 호환:

        collector.diagnose(
            diagnose_date,
            cid
        )
    """

    result = find_working_7m_url()


    if result.get(
        "status"
    ) != 200:

        return {

            "status":
                result.get(
                    "status",
                    0
                ),

            "html_size":
                0,

            "size":
                0,

            "found":
                0,

            "error":
                result.get(
                    "error",
                    "7M 접속 실패"
                ),

            "html":
                "",

            "js":
                ""

        }


    html = result.get(
        "html",
        ""
    )


    detail = diagnose_html(
        html,
        result.get(
            "url",
            ""
        )
    )


    rows = detail.get(
        "sample",
        []
    )


    # 날짜/CID 필터
    if target_date is not None:

        rows = filter_matches_by_date(
            rows,
            target_date
        )


    if cid:

        rows = filter_matches_by_cid(
            rows,
            cid
        )


    return {

        "status":
            result.get(
                "status",
                200
            ),

        "html_size":
            len(html),

        "size":
            detail.get(
                "js_size",
                0
            ),

        "found":
            len(rows),

        "error":
            "",

        "html":
            html,

        "js":
            detail.get(
                "js",
                ""
            ),

        "url":
            result.get(
                "url",
                ""
            ),

        "script_count":
            detail.get(
                "script_count",
                0
            ),

        "script_urls":
            detail.get(
                "script_urls",
                []
            )

    }


# ============================================================
# COLLECT DAY
# ============================================================

def collect_day(
    target_date,
    cid=""
):

    """
    CollectorWorker 호환 함수.

    날짜 하나를 받아
    7M 페이지/JS를 찾고 해당 날짜 경기만 저장한다.
    """

    target = normalize_date(
        target_date
    )


    if not target:

        raise ValueError(
            f"잘못된 날짜: {target_date}"
        )


    add_log(
        f"{target} 7M 일일 수집 시작"
    )


    # --------------------------------------------------------
    # 메인 페이지 자동 탐색
    # --------------------------------------------------------

    result = find_working_7m_url()


    if result.get(
        "status"
    ) != 200:

        error = result.get(
            "error",
            "7M 접속 실패"
        )

        save_collection_day(
            target,
            "ERROR",
            0,
            0,
            error
        )

        raise RuntimeError(
            error
        )


    base_url = result.get(
        "url",
        ""
    )

    html = result.get(
        "html",
        ""
    )


    # --------------------------------------------------------
    # HTML + script
    # --------------------------------------------------------

    rows = parse_dt_from_html(
        html
    )


    # --------------------------------------------------------
    # JS 후보
    # --------------------------------------------------------

    js_results = fetch_candidate_js(
        html,
        base_url,
        max_files=20
    )


    seen = set()


    for row in rows:

        seen.add(
            row.get(
                "match_key"
            )
        )


    for item in js_results:

        js_text = item.get(
            "text",
            ""
        )


        js_rows = parse_dt_from_html(
            js_text
        )


        for row in js_rows:

            key = row.get(
                "match_key"
            )


            if key in seen:
                continue


            seen.add(
                key
            )

            rows.append(
                row
            )


    # --------------------------------------------------------
    # filter
    # --------------------------------------------------------

    rows = filter_matches_by_date(
        rows,
        target
    )


    rows = filter_matches_by_cid(
        rows,
        cid
    )


    found = len(
        rows
    )

    saved = 0


    # --------------------------------------------------------
    # save
    # --------------------------------------------------------

    for row in rows:

        try:

            saved += save_match(
                row
            )

        except Exception as exc:

            add_log(
                (
                    f"{target} 저장 실패 "
                    f"{row.get('match_id')}: "
                    f"{exc}"
                ),
                "ERROR"
            )


    save_collection_day(
        target,
        "DONE",
        found,
        saved,
        ""
    )


    add_log(
        (
            f"{target} 완료: "
            f"발견 {found}, "
            f"신규 {saved}"
        )
    )


    return {

        "found":
            found,

        "saved":
            saved,

        "rows":
            rows

    }


# ============================================================
# RANGE COLLECTION
# ============================================================

def collect_range(
    start_date,
    end_date,
    url=None,
    retry_count=3,
    retry_delay=2.0,
    stop_event=None,
    cid=""
):

    start = normalize_date(
        start_date
    )

    end = normalize_date(
        end_date
    )


    if not start or not end:

        raise ValueError(
            "잘못된 날짜"
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


    stopped = False


    try:

        for target in date_range(
            start,
            end
        ):


            if (
                stop_event is not None
                and stop_event.is_set()
            ):

                stopped = True

                add_log(
                    "수집 중지 요청",
                    "WARNING"
                )

                break


            success = False

            last_error = ""


            save_collection_day(
                target,
                "RUNNING",
                0,
                0,
                ""
            )


            for attempt in range(
                int(retry_count) + 1
            ):

                try:

                    result = collect_day(
                        target,
                        cid
                    )


                    total_found += int(
                        result.get(
                            "found",
                            0
                        )
                    )


                    total_saved += int(
                        result.get(
                            "saved",
                            0
                        )
                    )


                    save_collection_state(
                        start_date=start.isoformat(),
                        end_date=end.isoformat(),
                        last_completed_date=target.isoformat(),
                        running=True,
                        stopped=False
                    )


                    success = True

                    break


                except Exception as exc:

                    last_error = str(
                        exc
                    )


                    add_log(
                        (
                            f"{target} "
                            f"수집 실패 "
                            f"({attempt + 1}/"
                            f"{int(retry_count) + 1}): "
                            f"{exc}"
                        ),
                        "ERROR"
                    )


                    if attempt < int(
                        retry_count
                    ):

                        time.sleep(
                            float(
                                retry_delay
                            )
                            * (
                                2 ** attempt
                            )
                        )


            if not success:

                save_collection_day(
                    target,
                    "ERROR",
                    0,
                    0,
                    last_error
                )


                add_log(
                    f"{target} 최종 실패",
                    "ERROR"
                )


    finally:

        save_collection_state(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            last_completed_date=(
                get_collection_state().get(
                    "last_completed_date"
                )
            ),
            running=False,
            stopped=stopped
        )


    return {

        "found":
            total_found,

        "saved":
            total_saved

    }


# ============================================================
# IMPORTANT
# ============================================================
#
# 여기에서 init_db()를 호출하지 않는다.
#
# app.py에서:
#
#     database.init_db()
#
# 를 이미 호출하기 때문이다.
#
# Streamlit Cloud에서는 collector.py import 시
# SQLite를 열지 않는 것이 안전하다.
# ============================================================
