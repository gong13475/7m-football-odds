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
# DATABASE
# ============================================================

DB_PATH = Path("odds.db")

_db_lock = threading.RLock()


def get_connection():

    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=30,
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
        "application/xml;q=0.9,*/*;q=0.8"
    ),

    "Accept-Language":
        "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",

    "Connection":
        "keep-alive",

}


def fetch_url(url, timeout=30):

    request = Request(
        str(url),
        headers=DEFAULT_HEADERS
    )

    try:

        with urlopen(
            request,
            timeout=timeout
        ) as response:

            raw = response.read()

            charset = (
                response.headers
                .get_content_charset()
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

    except HTTPError:

        raise

    except URLError:

        raise


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

    text = str(value).strip()

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
# JAVASCRIPT ARRAY FINDER
# ============================================================

def _find_array_after_position(
    text,
    start
):

    """
    start 이후 가장 먼저 나오는 [ 를 찾고
    문자열 내부를 고려해서 대응하는 ]까지 반환한다.
    """

    if not text:
        return None

    open_pos = text.find(
        "[",
        start
    )

    if open_pos < 0:
        return None

    depth = 0
    quote = None
    escaped = False

    for i in range(
        open_pos,
        len(text)
    ):

        char = text[i]

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

            continue

        if char == "]":

            depth -= 1

            if depth == 0:

                return text[
                    open_pos:i + 1
                ]

    return None


def extract_dt_block(html):

    """
    7M의 dt 배열을 robust하게 찾는다.

    지원:

        var dt = [...]
        let dt = [...]
        const dt = [...]
        dt = [...]
        window.dt = [...]
        this.dt = [...]

    정규식으로 배열 전체를 자르지 않고
    [] 깊이를 직접 계산한다.
    """

    if not html:
        return None

    patterns = [

        r"\bvar\s+dt\s*=",

        r"\blet\s+dt\s*=",

        r"\bconst\s+dt\s*=",

        r"\bdt\s*=",

        r"\bwindow\.dt\s*=",

        r"\bthis\.dt\s*=",

    ]

    positions = []

    for pattern in patterns:

        try:

            for match in re.finditer(
                pattern,
                html,
                re.IGNORECASE
            ):

                positions.append(
                    match.start()
                )

        except Exception:
            continue

    positions = sorted(
        set(positions)
    )

    for position in positions:

        block = _find_array_after_position(
            html,
            position
        )

        if block:

            return block

    # --------------------------------------------------------
    # fallback
    #
    # dt가 공백/괄호 때문에 일반 패턴에 걸리지 않는 경우
    # "dt" 주변을 직접 탐색
    # --------------------------------------------------------

    for match in re.finditer(
        r"\bdt\b",
        html,
        re.IGNORECASE
    ):

        block = _find_array_after_position(
            html,
            match.start()
        )

        if block:

            return block

    return None


# ============================================================
# JS ARRAY STRING SPLITTER
# ============================================================

def split_js_array_strings(array_text):

    """
    JavaScript 배열을 안전하게 문자열 원소 단위로 분리한다.

    문자열 내부의

        ,
        |
        [
        ]

    를 구분자로 오인하지 않는다.
    """

    if not array_text:
        return []

    text = array_text.strip()

    if not text.startswith("["):
        return []

    if not text.endswith("]"):
        return []

    text = text[1:-1]

    results = []

    current = []

    quote = None

    escaped = False

    depth = 0

    for char in text:

        if escaped:

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

                continue

            current.append(char)

            continue

        if char in (
            '"',
            "'",
            "`"
        ):

            quote = char

            continue

        if char in (
            "[",
            "{",
            "("
        ):

            depth += 1

            current.append(char)

            continue

        if char in (
            "]",
            "}",
            ")"
        ):

            if depth > 0:
                depth -= 1

            current.append(char)

            continue

        if char == "," and depth == 0:

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
# DT ROW
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

    except Exception:

        return None

    match_datetime = parse_match_datetime(
        dt_value
    )

    if not match_datetime:
        return None

    # --------------------------------------------------------
    # Odds
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


# ============================================================
# PARSE DT
# ============================================================

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
# SAVE
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
# COLLECTION
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

        "found":
            found,

        "saved":
            saved,

        "rows":
            rows
    }


def collect_url(
    url,
    target_date=None
):

    add_log(
        f"7M 요청: {url}"
    )

    html = fetch_url(
        url
    )

    add_log(
        f"HTML 수신: {len(html):,} bytes"
    )

    result = collect_html(
        html,
        target_date
    )

    add_log(
        f"7M 후보 "
        f"{result['found']}건 / "
        f"신규 저장 "
        f"{result['saved']}건"
    )

    return result


# ============================================================
# 7M URL
# ============================================================

def build_url(
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

    ymd = target.strftime(
        "%Y%m%d"
    )

    # --------------------------------------------------------
    # 중요:
    #
    # 실제 7M URL은 사용하는 사이트 구조에 따라 달라질 수 있다.
    # CID가 있으면 query에 포함한다.
    #
    # 현재 진단에서 HTTP 200이 나온 URL을 사용하는 것이 가장
    # 안전하다.
    # --------------------------------------------------------

    base = (
        "https://www.7m.com.cn/"
    )

    if cid:

        return (
            f"{base}?date={ymd}"
            f"&cid={cid}"
        )

    return (
        f"{base}?date={ymd}"
    )


# ============================================================
# DAILY COLLECTION
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

    url = build_url(
        target,
        cid
    )

    return collect_url(
        url,
        target
    )


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


def collect_range(
    start_date,
    end_date,
    url=None,
    cid="",
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

    total_found = 0

    total_saved = 0

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

            break

        success = False

        last_error = ""

        for attempt in range(
            int(retry_count) + 1
        ):

            try:

                if url:

                    result = collect_url(
                        url,
                        target_date
                    )

                else:

                    result = collect_day(
                        target_date,
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

            add_log(
                f"{target_date} 최종 실패: "
                f"{last_error}",
                "ERROR"
            )

    return {

        "found":
            total_found,

        "saved":
            total_saved
    }


# ============================================================
# DIAGNOSTIC
# ============================================================

def diagnose_html(html):

    if not html:

        return {

            "html_length":
                0,

            "dt_found":
                False,

            "dt_length":
                0,

            "raw_count":
                0,

            "candidate_count":
                0,

            "parse_errors":
                0,

            "sample":
                [],

            "error":
                "HTML이 비어 있습니다."
        }

    dt_block = extract_dt_block(
        html
    )

    if not dt_block:

        occurrences = len(
            re.findall(
                r"\bdt\b",
                html,
                re.IGNORECASE
            )
        )

        return {

            "html_length":
                len(html),

            "dt_found":
                False,

            "dt_length":
                0,

            "raw_count":
                0,

            "candidate_count":
                0,

            "parse_errors":
                0,

            "dt_occurrences":
                occurrences,

            "sample":
                [],

            "error":
                (
                    "dt 배열을 찾지 못했습니다. "
                    f"HTML 내 dt 후보: "
                    f"{occurrences}"
                )
        }

    raw_rows = split_js_array_strings(
        dt_block
    )

    rows = []

    parse_errors = 0

    for raw in raw_rows:

        try:

            row = parse_dt_row(
                raw
            )

            if row:

                rows.append(row)

        except Exception:

            parse_errors += 1

    return {

        "html_length":
            len(html),

        "dt_found":
            True,

        "dt_length":
            len(dt_block),

        "raw_count":
            len(raw_rows),

        "candidate_count":
            len(rows),

        "parse_errors":
            parse_errors,

        "sample":
            rows[:5]
    }


# ============================================================
# DIAGNOSE
# ============================================================

def diagnose(
    diagnose_date,
    cid=""
):

    target = normalize_date(
        diagnose_date
    )

    if not target:

        return {

            "status":
                0,

            "html_size":
                0,

            "size":
                0,

            "found":
                0,

            "error":
                "잘못된 진단 날짜",

            "html":
                "",

            "js":
                ""
        }

    url = build_url(
        target,
        cid
    )

    try:

        html = fetch_url(
            url
        )

        diagnostic = diagnose_html(
            html
        )

        return {

            "status":
                200,

            "html_size":
                len(html),

            "size":
                diagnostic.get(
                    "dt_length",
                    0
                ),

            "found":
                diagnostic.get(
                    "candidate_count",
                    0
                ),

            "raw_count":
                diagnostic.get(
                    "raw_count",
                    0
                ),

            "dt_found":
                diagnostic.get(
                    "dt_found",
                    False
                ),

            "dt_length":
                diagnostic.get(
                    "dt_length",
                    0
                ),

            "candidate_count":
                diagnostic.get(
                    "candidate_count",
                    0
                ),

            "parse_errors":
                diagnostic.get(
                    "parse_errors",
                    0
                ),

            "sample":
                diagnostic.get(
                    "sample",
                    []
                ),

            "error":
                diagnostic.get(
                    "error",
                    ""
                ),

            "html":
                html,

            "js":
                (
                    diagnostic.get(
                        "sample",
                        []
                    )
                )
        }

    except HTTPError as exc:

        return {

            "status":
                exc.code,

            "html_size":
                0,

            "size":
                0,

            "found":
                0,

            "error":
                f"HTTP 오류: {exc.code}",

            "html":
                "",

            "js":
                ""
        }

    except URLError as exc:

        return {

            "status":
                0,

            "html_size":
                0,

            "size":
                0,

            "found":
                0,

            "error":
                f"네트워크 오류: {exc}",

            "html":
                "",

            "js":
                ""
        }

    except Exception as exc:

        return {

            "status":
                0,

            "html_size":
                0,

            "size":
                0,

            "found":
                0,

            "error":
                str(exc),

            "html":
                "",

            "js":
                ""
        }


# ============================================================
# DATABASE COMPATIBILITY
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
# COLLECTION DAY STATE
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

        if row:

            return dict(row)

        return {}

    finally:

        conn.close()


# ============================================================
# IMPORTANT
# ============================================================
#
# 여기서는 init_db()를 자동 호출하지 않는다.
#
# app.py에서:
#
#     database.init_db()
#
# 를 호출하므로 Streamlit Cloud에서 collector import 시
# 별도 SQLite 초기화를 하지 않는다.
#
# ============================================================
