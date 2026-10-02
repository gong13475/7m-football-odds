# collector.py
# ============================================================
# 7M 축구 최종배당 Collector
# ============================================================

import re
import time
import json
import ssl
import socket
import threading

from datetime import date, datetime, timedelta
from html import unescape
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import database


# ============================================================
# CONFIG
# ============================================================

BASE_URLS = [
    "https://data.7m.com.cn/",
    "https://data.7m.com.cn/index.js",
    "https://data1.7m.com.cn/",
    "https://data1.7m.com.cn/index.js",
]

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/140.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "application/javascript,"
        "text/javascript,"
        "*/*;q=0.8"
    ),
    "Accept-Language": (
        "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

REQUEST_TIMEOUT = 45

MAX_SCRIPT_COUNT = 80


# ============================================================
# LOG
# ============================================================

def log(message, level="INFO"):

    try:
        database.add_log(
            str(message),
            level
        )
    except Exception:
        pass


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


def date_range(start_date, end_date):

    start = normalize_date(start_date)
    end = normalize_date(end_date)

    if not start or not end:
        return

    current = start

    while current <= end:

        yield current

        current += timedelta(days=1)


# ============================================================
# HTTP
# ============================================================

def make_ssl_context():

    context = ssl.create_default_context()

    # Streamlit Cloud 일부 환경에서
    # 인증서/SSL 협상 문제가 발생하는 경우를 완화
    context.check_hostname = True

    return context


def fetch_url(
    url,
    timeout=REQUEST_TIMEOUT,
    referer=None
):

    headers = dict(DEFAULT_HEADERS)

    if referer:
        headers["Referer"] = referer

    request = Request(
        url,
        headers=headers,
        method="GET"
    )

    context = make_ssl_context()

    with urlopen(
        request,
        timeout=timeout,
        context=context
    ) as response:

        status = response.getcode()

        raw = response.read()

        charset = response.headers.get_content_charset()

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
            "status": status,
            "url": response.geturl(),
            "text": text,
            "size": len(text),
            "content_type":
                response.headers.get(
                    "Content-Type",
                    ""
                )
        }


def safe_fetch(
    url,
    referer=None,
    retries=2,
    delay=1.0
):

    last_error = None

    for attempt in range(
        retries + 1
    ):

        try:

            return fetch_url(
                url,
                referer=referer
            )

        except Exception as exc:

            last_error = exc

            log(
                f"HTTP 실패 "
                f"{attempt + 1}/"
                f"{retries + 1}: "
                f"{url} -> {exc}",
                "WARNING"
            )

            if attempt < retries:

                time.sleep(
                    delay * (attempt + 1)
                )

    raise last_error


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

    # --------------------------------------------------------
    # <script src="...">
    # --------------------------------------------------------

    patterns = [

        r'<script[^>]+src\s*=\s*["\']([^"\']+)["\']',

        r'<script[^>]+src\s*=\s*([^>\s]+)',

    ]

    for pattern in patterns:

        for match in re.finditer(
            pattern,
            html,
            re.IGNORECASE
        ):

            src = match.group(1).strip()

            src = src.strip(
                "\"'"
            )

            if not src:
                continue

            absolute = urljoin(
                base_url,
                unescape(src)
            )

            if absolute not in urls:

                urls.append(
                    absolute
                )

    return urls[:MAX_SCRIPT_COUNT]


# ============================================================
# 7M BASE URL DISCOVERY
# ============================================================

def get_base_candidates():

    result = []

    for url in BASE_URLS:

        if url not in result:

            result.append(url)

    return result


def fetch_main_page():

    last_error = None

    for url in get_base_candidates():

        try:

            result = safe_fetch(
                url,
                retries=1
            )

            if result["status"] == 200:

                return result

            log(
                f"7M 응답 {result['status']}: {url}",
                "WARNING"
            )

        except Exception as exc:

            last_error = exc

            log(
                f"7M 접속 실패: "
                f"{url} -> {exc}",
                "WARNING"
            )

    if last_error:

        raise last_error

    raise RuntimeError(
        "7M 서버에 접속할 수 없습니다."
    )


# ============================================================
# DATETIME
# ============================================================

def parse_match_datetime(value):

    if not value:
        return None

    text = str(value).strip()

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

    # 일반 날짜 형식
    patterns = [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y.%m.%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ]

    for pattern in patterns:

        try:

            return datetime.strptime(
                text,
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

        home_score = int(
            home_score
        )

        away_score = int(
            away_score
        )

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

def parse_odds(value):

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # 쉼표 제거
    text = text.replace(",", "")

    try:

        number = float(text)

    except (
        TypeError,
        ValueError
    ):

        return None

    if (
        number <= 1.0
        or number >= 1000.0
    ):
        return None

    return number


def valid_odds(value):

    number = parse_odds(value)

    return number is not None


# ============================================================
# JS STRING ARRAY
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

            # JS escape
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

        current.append(char)

    value = "".join(
        current
    ).strip()

    if value:

        results.append(
            value
        )

    return results


# ============================================================
# DT BLOCK EXTRACTION
# ============================================================

def extract_balanced_array(
    text,
    start_index
):

    if not text:
        return None

    if start_index >= len(text):
        return None

    if text[start_index] != "[":
        return None

    depth = 0

    quote = None

    escaped = False

    for index in range(
        start_index,
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
                    start_index:
                    index + 1
                ]

    return None


def find_named_arrays(
    text
):

    """
    dt = [...]
    var dt = [...]
    let dt = [...]
    const dt = [...]

    배열 시작부터 balanced bracket으로 추출한다.
    """

    if not text:
        return []

    candidates = []

    patterns = [

        r'\b(?:var|let|const)\s+dt\s*=\s*\[',

        r'\bdt\s*=\s*\[',

        r'["\']dt["\']\s*:\s*\[',

    ]

    for pattern in patterns:

        for match in re.finditer(
            pattern,
            text,
            re.IGNORECASE
        ):

            pos = text.find(
                "[",
                match.start(),
                match.end() + 1
            )

            if pos < 0:
                continue

            block = extract_balanced_array(
                text,
                pos
            )

            if block:

                if block not in candidates:

                    candidates.append(
                        block
                    )

    return candidates


# ============================================================
# GENERIC 7M ROW DISCOVERY
# ============================================================

def looks_like_7m_row(
    raw
):

    if not raw:
        return False

    parts = raw.split("|")

    if len(parts) < 14:
        return False

    # match id
    if not re.fullmatch(
        r"\d+",
        parts[0].strip()
    ):
        return False

    # datetime
    if not parse_match_datetime(
        parts[1].strip()
    ):
        return False

    # score
    try:

        int(parts[8].strip())
        int(parts[9].strip())

    except (
        ValueError,
        TypeError
    ):

        return False

    # 최소 배당 3개
    odds = [
        parse_odds(parts[11]),
        parse_odds(parts[12]),
        parse_odds(parts[13]),
    ]

    return all(
        value is not None
        for value in odds
    )


# ============================================================
# GENERIC ROW SCANNER
# ============================================================

def scan_text_for_rows(
    text
):

    """
    dt 배열 선언명이 바뀌어도
    7M 특유의 | 구분 행을 직접 찾는다.
    """

    if not text:
        return []

    results = []

    seen = set()

    # --------------------------------------------------------
    # 먼저 dt 배열
    # --------------------------------------------------------

    blocks = find_named_arrays(
        text
    )

    for block in blocks:

        rows = split_js_array_strings(
            block
        )

        for raw in rows:

            raw = raw.strip()

            if raw in seen:
                continue

            if looks_like_7m_row(raw):

                seen.add(raw)

                results.append(raw)

    # --------------------------------------------------------
    # dt 이름이 없는 경우
    # --------------------------------------------------------
    #
    # 7M 행의 특징:
    #
    # 숫자 ID | 날짜 | CID | league | ID | ID |
    # 팀 | 팀 | score | score | half | odds...
    #
    # --------------------------------------------------------

    if results:
        return results

    # 너무 짧은 텍스트는 스킵
    if len(text) < 100:
        return []

    # 직접 문자열 리터럴 검색
    pattern = re.compile(
        r'(["\'])(\d{5,}\|'
        r'\d{4}[,./-]\d{1,2}[,./-]\d{1,2}'
        r'[^"\']{30,})\1'
    )

    for match in pattern.finditer(text):

        raw = match.group(2)

        if raw in seen:
            continue

        if looks_like_7m_row(raw):

            seen.add(raw)

            results.append(raw)

    return results


# ============================================================
# ROW PARSER
# ============================================================

def parse_dt_row(
    raw
):

    if not raw:
        return None

    parts = raw.split("|")

    if len(parts) < 14:
        return None

    match_id = parts[0].strip()

    match_datetime = parse_match_datetime(
        parts[1].strip()
    )

    if not match_datetime:
        return None

    cid = parts[2].strip()

    league = parts[3].strip()

    home_id = parts[4].strip()

    away_id = parts[5].strip()

    home_team = parts[6].strip()

    away_team = parts[7].strip()

    try:

        home_score = int(
            parts[8].strip()
        )

        away_score = int(
            parts[9].strip()
        )

    except (
        TypeError,
        ValueError
    ):

        return None

    half_score = parts[10].strip()

    # --------------------------------------------------------
    # 배당
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

    if not all([
        valid_odds(home_odds),
        valid_odds(draw_odds),
        valid_odds(away_odds),
    ]):

        return None

    result = get_result(
        home_score,
        away_score
    )

    # --------------------------------------------------------
    # 배당 암시 확률
    # --------------------------------------------------------

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
            home_score,

        "away_score":
            away_score,

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
            "7M",

    }


# ============================================================
# PARSE TEXT
# ============================================================

def parse_dt_from_html(
    html
):

    if not html:
        return []

    raw_rows = scan_text_for_rows(
        html
    )

    results = []

    seen = set()

    for raw in raw_rows:

        try:

            row = parse_dt_row(
                raw
            )

            if not row:
                continue

            key = row["match_key"]

            if key in seen:
                continue

            seen.add(key)

            results.append(row)

        except Exception as exc:

            log(
                f"7M 행 파싱 오류: {exc}",
                "WARNING"
            )

    return results


# ============================================================
# HTML + JS COLLECTOR
# ============================================================

def collect_page_assets(
    main
):

    html = main["text"]

    base_url = main["url"]

    assets = [
        (
            "HTML",
            base_url,
            html
        )
    ]

    scripts = extract_script_urls(
        html,
        base_url
    )

    log(
        f"HTML script 후보: "
        f"{len(scripts)}개"
    )

    for script_url in scripts:

        try:

            result = safe_fetch(
                script_url,
                referer=base_url,
                retries=1
            )

            if result["status"] != 200:
                continue

            assets.append(
                (
                    "JS",
                    script_url,
                    result["text"]
                )
            )

            log(
                f"JS 수신: "
                f"{script_url} "
                f"({result['size']:,})"
            )

        except Exception as exc:

            log(
                f"JS 요청 실패: "
                f"{script_url} -> {exc}",
                "WARNING"
            )

    return assets


# ============================================================
# CID FILTER
# ============================================================

def filter_cid(
    rows,
    cid
):

    cid = str(
        cid or ""
    ).strip()

    if not cid:
        return rows

    return [
        row
        for row in rows
        if str(
            row.get("cid", "")
        ).strip() == cid
    ]


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

            result.append(row)

    return result


# ============================================================
# SAVE
# ============================================================

def save_match(
    row
):

    """
    실제 저장은 database.py에 위임.
    기존 프로젝트의 DB 구조와 충돌하지 않도록 한다.
    """

    # database.py에 save_match가 있는 경우
    if hasattr(
        database,
        "save_match"
    ):

        return database.save_match(
            row
        )

    # database.py에 insert_match가 있는 경우
    if hasattr(
        database,
        "insert_match"
    ):

        return database.insert_match(
            row
        )

    raise AttributeError(
        "database.py에 "
        "save_match() 또는 "
        "insert_match()가 없습니다."
    )


# ============================================================
# COLLECT HTML
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

        rows = filter_cid(
            rows,
            cid
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

            value = save_match(
                row
            )

            if isinstance(
                value,
                bool
            ):

                saved += (
                    1
                    if value
                    else 0
                )

            elif value is None:

                saved += 1

            else:

                try:
                    saved += int(
                        value
                    )

                except Exception:

                    saved += 1

        except Exception as exc:

            log(
                f"경기 저장 실패 "
                f"{row.get('match_id')}: "
                f"{exc}",
                "ERROR"
            )

    return {
        "found": found,
        "saved": saved,
        "rows": rows
    }


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
            "잘못된 날짜"
        )

    log(
        f"7M {target} 수집 시작"
    )

    main = fetch_main_page()

    log(
        f"7M 메인 응답: "
        f"{main['status']} / "
        f"{main['size']:,}"
    )

    assets = collect_page_assets(
        main
    )

    all_rows = []

    seen = set()

    # --------------------------------------------------------
    # HTML + JS 전체 탐색
    # --------------------------------------------------------

    for kind, url, text in assets:

        rows = parse_dt_from_html(
            text
        )

        if rows:

            log(
                f"{kind} 경기 후보 발견: "
                f"{len(rows)} / {url}"
            )

        for row in rows:

            key = row.get(
                "match_key"
            )

            if key in seen:
                continue

            seen.add(key)

            all_rows.append(
                row
            )

    # --------------------------------------------------------
    # CID
    # --------------------------------------------------------

    if cid:

        all_rows = filter_cid(
            all_rows,
            cid
        )

    # --------------------------------------------------------
    # 날짜
    # --------------------------------------------------------

    rows = filter_matches_by_date(
        all_rows,
        target
    )

    found = len(rows)

    saved = 0

    for row in rows:

        try:

            value = save_match(
                row
            )

            if isinstance(
                value,
                bool
            ):

                saved += (
                    1
                    if value
                    else 0
                )

            elif value is None:

                saved += 1

            else:

                try:

                    saved += int(
                        value
                    )

                except Exception:

                    saved += 1

        except Exception as exc:

            log(
                f"저장 실패 "
                f"{row.get('match_id')}: "
                f"{exc}",
                "ERROR"
            )

    log(
        f"{target}: "
        f"전체 후보 {len(all_rows)} / "
        f"해당 날짜 {found} / "
        f"신규 저장 {saved}"
    )

    return {
        "found": found,
        "saved": saved,
        "rows": rows
    }


# ============================================================
# RANGE
# ============================================================

def collect_range(
    start_date,
    end_date,
    cid="",
    retry_count=3,
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
            "잘못된 날짜 범위"
        )

    if start > end:

        raise ValueError(
            "시작 날짜가 종료 날짜보다 늦습니다."
        )

    total_found = 0
    total_saved = 0

    for target in date_range(
        start,
        end
    ):

        if stop_event:

            if stop_event.is_set():

                log(
                    "수집 중지 요청",
                    "WARNING"
                )

                break

        success = False

        last_error = ""

        for attempt in range(
            int(retry_count)
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

                database.save_collection_day(
                    target,
                    "DONE",
                    result.get(
                        "found",
                        0
                    ),
                    result.get(
                        "saved",
                        0
                    ),
                    ""
                )

                success = True

                break

            except Exception as exc:

                last_error = str(
                    exc
                )

                log(
                    f"{target} "
                    f"수집 실패 "
                    f"{attempt + 1}/"
                    f"{retry_count}: "
                    f"{exc}",
                    "ERROR"
                )

                if attempt < retry_count - 1:

                    time.sleep(
                        float(
                            retry_delay
                        )
                    )

        if not success:

            try:

                database.save_collection_day(
                    target,
                    "ERROR",
                    0,
                    0,
                    last_error
                )

            except Exception:
                pass

    return {
        "found": total_found,
        "saved": total_saved
    }


# ============================================================
# DIAGNOSTIC
# ============================================================

def diagnose(
    diagnose_date,
    cid=""
):

    result = {

        "status": 0,

        "html_size": 0,

        "size": 0,

        "found": 0,

        "error": "",

        "html": "",

        "js": "",

        "url": "",

        "scripts": [],

        "samples": [],

    }

    try:

        target = normalize_date(
            diagnose_date
        )

        main = fetch_main_page()

        result["status"] = main[
            "status"
        ]

        result["html_size"] = main[
            "size"
        ]

        result["html"] = main[
            "text"
        ]

        result["url"] = main[
            "url"
        ]

        assets = collect_page_assets(
            main
        )

        result["scripts"] = [
            {
                "type": kind,
                "url": url,
                "size": len(text)
            }
            for kind, url, text
            in assets
        ]

        # ----------------------------------------------------
        # JS 전체 결합
        # ----------------------------------------------------

        js_parts = []

        for kind, url, text in assets:

            if kind == "JS":

                js_parts.append(
                    text
                )

        combined_js = "\n".join(
            js_parts
        )

        result["js"] = combined_js

        result["size"] = len(
            combined_js
        )

        # ----------------------------------------------------
        # 모든 자산에서 경기 탐색
        # ----------------------------------------------------

        all_rows = []

        seen = set()

        for kind, url, text in assets:

            rows = parse_dt_from_html(
                text
            )

            for row in rows:

                key = row.get(
                    "match_key"
                )

                if key in seen:
                    continue

                seen.add(key)

                all_rows.append(
                    row
                )

        if cid:

            all_rows = filter_cid(
                all_rows,
                cid
            )

        if target:

            target_rows = (
                filter_matches_by_date(
                    all_rows,
                    target
                )
            )

        else:

            target_rows = all_rows

        result["found"] = len(
            target_rows
        )

        result["samples"] = (
            target_rows[:10]
        )

        # ----------------------------------------------------
        # 오류가 아니라 응답 성공
        # ----------------------------------------------------

        if not all_rows:

            result["error"] = (
                "HTTP 200 응답은 성공했지만 "
                "7M 경기 행을 찾지 못했습니다. "
                "scripts 목록과 HTML/JS 내용을 확인하세요."
            )

        else:

            result["error"] = ""

        return result

    except HTTPError as exc:

        result["status"] = exc.code

        result["error"] = (
            f"HTTP 오류: {exc.code}"
        )

        return result

    except URLError as exc:

        result["error"] = (
            f"네트워크 오류: {exc}"
        )

        return result

    except socket.timeout as exc:

        result["error"] = (
            f"연결 시간 초과: {exc}"
        )

        return result

    except Exception as exc:

        result["error"] = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return result


# ============================================================
# COMPATIBILITY
# ============================================================

def diagnose_html(
    html
):

    rows = parse_dt_from_html(
        html
    )

    return {

        "html_length":
            len(html or ""),

        "dt_found":
            bool(
                find_named_arrays(
                    html or ""
                )
            ),

        "candidate_count":
            len(rows),

        "sample":
            rows[:5]
    }


def diagnose_url(
    url
):

    result = safe_fetch(
        url
    )

    return diagnose_html(
        result["text"]
    )


# ============================================================
# DB INITIALIZATION
# ============================================================

try:

    database.init_db()

except Exception as exc:

    # import 시 앱 전체가 죽지 않도록 함
    print(
        f"database.init_db warning: {exc}"
    )
