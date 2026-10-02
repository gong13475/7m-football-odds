import re
import time
import json
import html as html_lib
import threading

from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


DB_PATH = Path("odds.db")

_db_lock = threading.RLock()


# ============================================================
# HTTP
# ============================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "application/javascript;q=0.9,"
        "*/*;q=0.8"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "close",
}


def fetch_url(url, timeout=30):

    request = Request(
        url,
        headers=DEFAULT_HEADERS
    )

    with urlopen(request, timeout=timeout) as response:

        raw = response.read()

        charset = (
            response.headers.get_content_charset()
            or "utf-8"
        )

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

        return text


def fetch_url_with_status(url, timeout=30):

    request = Request(
        url,
        headers=DEFAULT_HEADERS
    )

    try:

        with urlopen(request, timeout=timeout) as response:

            raw = response.read()

            charset = (
                response.headers.get_content_charset()
                or "utf-8"
            )

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

            return {
                "status": response.status,
                "html": text,
                "headers": dict(response.headers),
                "error": ""
            }

    except HTTPError as exc:

        try:
            raw = exc.read()
            text = raw.decode(
                "utf-8",
                errors="ignore"
            )
        except Exception:
            text = ""

        return {
            "status": exc.code,
            "html": text,
            "headers": {},
            "error": f"HTTP 오류: {exc.code}"
        }

    except URLError as exc:

        return {
            "status": 0,
            "html": "",
            "headers": {},
            "error": f"네트워크 오류: {exc}"
        }

    except Exception as exc:

        return {
            "status": 0,
            "html": "",
            "headers": {},
            "error": str(exc)
        }


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


def add_log(message, level="INFO"):

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

    if len(numbers) < 5:
        return None

    try:

        y = int(numbers[0])
        m = int(numbers[1])
        d = int(numbers[2])
        hh = int(numbers[3])
        mm = int(numbers[4])

        ss = (
            int(numbers[5])
            if len(numbers) >= 6
            else 0
        )

        return datetime(
            y,
            m,
            d,
            hh,
            mm,
            ss
        )

    except ValueError:

        return None


# ============================================================
# RESULT
# ============================================================

def get_result(home_score, away_score):

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

    text = (
        str(value)
        .strip()
        .replace(",", "")
    )

    if not text:
        return None

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
# JS / HTML CLEAN
# ============================================================

def clean_js_string(value):

    if value is None:
        return ""

    value = str(value)

    value = (
        value
        .replace("\\'", "'")
        .replace('\\"', '"')
        .replace("\\/", "/")
        .replace("\\n", " ")
        .replace("\\r", " ")
        .replace("\\t", " ")
    )

    return html_lib.unescape(
        value
    ).strip()


# ============================================================
# DT ARRAY
# ============================================================

def extract_dt_blocks(html):

    """
    7M 페이지가 사용하는 dt 배열을 최대한 넓게 탐색한다.

    기존:
        var dt = ["..."];

    대응:
        var dt=[...]
        let dt=[...]
        const dt=[...]
        window.dt=[...]
        dt=[...]
    """

    if not html:
        return []

    patterns = [

        r'(?:var|let|const)\s+dt\s*=\s*(\[[\s\S]*?\])',

        r'window\.dt\s*=\s*(\[[\s\S]*?\])',

        r'\bdt\s*=\s*(\[[\s\S]*?\])',

        r'["\']dt["\']\s*:\s*(\[[\s\S]*?\])',

        r'["\']data["\']\s*:\s*(\[[\s\S]*?\])',

    ]

    blocks = []

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                html,
                re.IGNORECASE
            )

            for block in found:

                if block not in blocks:

                    blocks.append(block)

        except Exception:
            continue

    return blocks


def extract_dt_block(html):

    blocks = extract_dt_blocks(
        html
    )

    if blocks:
        return blocks[0]

    return None


# ============================================================
# JS ARRAY STRING SPLITTER
# ============================================================

def split_js_array_strings(array_text):

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

    depth = 0

    for char in text:

        if escaped:

            current.append(char)
            escaped = False
            continue

        if quote:

            if char == "\\":
                escaped = True
                continue

            if char == quote:
                quote = None
                continue

            current.append(char)

            continue

        if char in (
            '"',
            "'"
        ):

            quote = char
            continue

        if char in "[{(":
            depth += 1

        elif char in "]})":
            depth = max(
                0,
                depth - 1
            )

        if char == "," and depth == 0:

            value = (
                "".join(current)
                .strip()
            )

            if value:
                results.append(value)

            current = []

        else:

            current.append(char)

    value = (
        "".join(current)
        .strip()
    )

    if value:
        results.append(value)

    return [
        clean_js_string(x)
        for x in results
    ]


# ============================================================
# ROW PARSER
# ============================================================

def parse_dt_row(raw):

    if not raw:
        return None

    raw = clean_js_string(
        raw
    )

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

    except Exception:

        return None

    match_datetime = parse_match_datetime(
        dt_value
    )

    if not match_datetime:
        return None

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

    return {

        "match_id": match_id,

        "match_key": match_id,

        "match_datetime": match_datetime,

        "match_date":
            match_datetime.date().isoformat(),

        "league": league,

        "cid": cid,

        "home_id": home_id,
        "away_id": away_id,

        "home_team": home_team,
        "away_team": away_team,

        "home_score": hs,
        "away_score": aws,

        "half_score": half_score,

        "result": result,

        "home_odds": home_odds,
        "draw_odds": draw_odds,
        "away_odds": away_odds,

        "home_probability":
            1.0 / home_odds,

        "draw_probability":
            1.0 / draw_odds,

        "away_probability":
            1.0 / away_odds,

        "source": "7M",
    }


# ============================================================
# GENERIC PIPE SEARCH
# ============================================================

def extract_pipe_rows(html):

    """
    dt 선언을 찾지 못한 경우,
    HTML 전체에서 실제 7M row처럼 보이는
    긴 | 구분 문자열을 직접 검색한다.
    """

    if not html:
        return []

    results = []

    # match_id|YYYY,M,D,H,M,S|CID|league|...
    pattern = re.compile(
        r'([0-9]{5,12}'
        r'\|'
        r'[0-9]{4}\s*,\s*[0-9]{1,2}\s*,\s*[0-9]{1,2}'
        r'\s*,\s*[0-9]{1,2}\s*,\s*[0-9]{1,2}'
        r'(?:\s*,\s*[0-9]{1,2})?'
        r'\|'
        r'[^"\']{1,300}'
        r')'
    )

    for match in pattern.finditer(html):

        candidate = (
            match.group(1)
            .replace("\\/", "/")
        )

        parts = candidate.split("|")

        if len(parts) >= 10:

            # 충분한 뒤쪽 데이터가 있는 경우
            end = min(
                len(parts),
                18
            )

            row_text = "|".join(
                parts[:end]
            )

            row = parse_dt_row(
                row_text
            )

            if row:

                key = row["match_id"]

                if key not in {
                    x["match_id"]
                    for x in results
                }:

                    results.append(row)

    return results


# ============================================================
# HTML PARSER
# ============================================================

def parse_dt_from_html(html):

    if not html:
        return []

    blocks = extract_dt_blocks(
        html
    )

    results = []

    for block in blocks:

        raw_rows = split_js_array_strings(
            block
        )

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

    # dt를 못 찾거나 dt 결과가 없으면
    # HTML 전체 fallback 검색
    if not results:

        results = extract_pipe_rows(
            html
        )

    # 중복 제거
    unique = {}
    for row in results:
        unique[row["match_id"]] = row

    return list(
        unique.values()
    )


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
# SAVE
# ============================================================

def save_match(row):

    match_key = row.get(
        "match_key"
    )

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
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?
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
                    ?, ?, ?, ?, ?,
                    CURRENT_TIMESTAMP
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

                    (
                        target_date.isoformat()
                        if hasattr(
                            target_date,
                            "isoformat"
                        )
                        else str(target_date)
                    ),

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
# COLLECTION
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

        rows = [
            row
            for row in rows
            if str(
                row.get("cid", "")
            ).strip() == str(cid).strip()
        ]

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
# URL
# ============================================================

def collect_url(
    url,
    target_date=None,
    cid=""
):

    add_log(
        f"7M 요청: {url}"
    )

    result = fetch_url_with_status(
        url
    )

    status = result["status"]
    html = result["html"]

    if result["error"]:

        add_log(
            result["error"],
            "ERROR"
        )

        raise RuntimeError(
            result["error"]
        )

    if status != 200:

        error = (
            f"HTTP 오류: {status}"
        )

        add_log(
            error,
            "ERROR"
        )

        raise RuntimeError(
            error
        )

    add_log(
        f"HTML 수신: {len(html):,} bytes"
    )

    parsed = collect_html(
        html,
        target_date,
        cid
    )

    add_log(
        f"7M 후보 "
        f"{parsed['found']}건 / "
        f"신규 저장 "
        f"{parsed['saved']}건"
    )

    return parsed


# ============================================================
# URL BUILDER
# ============================================================

def build_default_url(
    target_date=None,
    cid=""
):

    """
    실제 사용 중인 7M 주소가 별도로 있다면
    여기만 수정하면 된다.

    기존 앱에서 index.js를 요청하는 경우를 고려한다.
    """

    # CID가 있으면 기존 구조 우선
    if cid:

        return (
            "https://data.7m.com.cn/"
            "index.js"
        )

    return (
        "https://data.7m.com.cn/"
        "index.js"
    )


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
            "잘못된 수집 날짜"
        )

    url = build_default_url(
        target,
        cid
    )

    result = collect_url(
        url,
        target,
        cid
    )

    save_collection_day(
        target,
        "DONE",
        result["found"],
        result["saved"],
        ""
    )

    return result


# ============================================================
# RANGE
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

    try:

        for target_date in date_range(
            start,
            end
        ):

            if (
                stop_event is not None
                and stop_event.is_set()
            ):

                add_log(
                    "수집 중지 요청",
                    "WARNING"
                )

                save_collection_state(
                    start_date=start.isoformat(),
                    end_date=end.isoformat(),
                    last_completed_date=(
                        last_completed
                    ),
                    running=False,
                    stopped=True
                )

                break

            save_collection_day(
                target_date,
                "RUNNING",
                0,
                0,
                ""
            )

            success = False
            last_error = ""

            for attempt in range(
                retry_count + 1
            ):

                try:

                    if url:

                        result = collect_url(
                            url,
                            target_date,
                            cid
                        )

                    else:

                        result = collect_day(
                            target_date,
                            cid
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

                    save_collection_day(
                        target_date,
                        "DONE",
                        found,
                        saved,
                        ""
                    )

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

        return {
            "found": total_found,
            "saved": total_saved
        }

    finally:

        stopped = bool(
            stop_event
            and stop_event.is_set()
        )

        save_collection_state(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            last_completed_date=(
                last_completed
            ),
            running=False,
            stopped=stopped
        )


# ============================================================
# DIAGNOSTIC
# ============================================================

def diagnose_html(html):

    if html is None:
        html = ""

    blocks = extract_dt_blocks(
        html
    )

    rows = parse_dt_from_html(
        html
    )

    # 실제 7M 형태의 날짜 문자열 존재 여부
    date_patterns = re.findall(
        r"\d{4},\d{1,2},\d{1,2},"
        r"\d{1,2},\d{1,2}(?:,\d{1,2})?",
        html
    )

    # pipe 데이터 후보
    pipe_candidates = re.findall(
        r"\d{5,12}\|"
        r"\d{4},\d{1,2},\d{1,2},"
        r"\d{1,2},\d{1,2}",
        html
    )

    # dt라는 단어의 등장 횟수
    dt_count = len(
        re.findall(
            r"\bdt\b",
            html,
            re.IGNORECASE
        )
    )

    return {

        "html_length": len(html),

        "dt_found":
            bool(blocks),

        "dt_block_count":
            len(blocks),

        "dt_length":
            (
                len(blocks[0])
                if blocks
                else 0
            ),

        "dt_keyword_count":
            dt_count,

        "candidate_count":
            len(rows),

        "date_pattern_count":
            len(date_patterns),

        "pipe_candidate_count":
            len(pipe_candidates),

        "sample":
            rows[:5],

        "html_head":
            html[:3000],

        "dt_sample":
            (
                blocks[0][:5000]
                if blocks
                else ""
            )
    }


def diagnose_url(
    url,
    target_date=None,
    cid=""
):

    response = fetch_url_with_status(
        url
    )

    html = response["html"]

    result = diagnose_html(
        html
    )

    result["status"] = (
        response["status"]
    )

    result["error"] = (
        response["error"]
    )

    result["url"] = url

    if target_date is not None:

        rows = parse_dt_from_html(
            html
        )

        rows = filter_matches_by_date(
            rows,
            target_date
        )

        if cid:

            rows = [
                row
                for row in rows
                if str(
                    row.get("cid", "")
                ).strip()
                == str(cid).strip()
            ]

        result[
            "target_candidate_count"
        ] = len(rows)

        result["target_sample"] = rows[:5]

    return result


# ============================================================
# APP COMPATIBILITY DIAGNOSE
# ============================================================

def diagnose(
    diagnose_date,
    cid=""
):

    url = build_default_url(
        diagnose_date,
        cid
    )

    result = diagnose_url(
        url,
        diagnose_date,
        cid
    )

    return {

        "status":
            result.get(
                "status",
                0
            ),

        "html_size":
            result.get(
                "html_length",
                0
            ),

        "size":
            result.get(
                "dt_length",
                0
            ),

        "found":
            result.get(
                "target_candidate_count",
                result.get(
                    "candidate_count",
                    0
                )
            ),

        "error":
            result.get(
                "error",
                ""
            ),

        "html":
            result.get(
                "html_head",
                ""
            ),

        "js":
            result.get(
                "dt_sample",
                ""
            ),

        "details":
            result
    }
