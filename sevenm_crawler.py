# ============================================================
# sevenm_crawler.py
# 7M 축구 최종배당 수집기
# API / JS 자동 탐색 버전
# 1X2 최종배당 / 경기결과 / 팀명
# ============================================================

import re
import json
import time
import html as html_lib
import requests

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, parse_qs


# ============================================================
# 기본 설정
# ============================================================

BASE_URL = "https://live.7msport.com"
DATA_URL = "https://data.7msport.com"

START_URLS = [
    "https://live.7msport.com/default_en.aspx",
    "https://live.7msport.com/default_kr.aspx",
    "https://live.7msport.com/default_ms.aspx",
    "https://live.7msport.com/default_vn.aspx",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 16; SM-S901N) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": (
        "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Connection": "keep-alive",
}

TIMEOUT = 20

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# 로그
# ============================================================

def log(callback, message):

    if callback:

        try:
            callback(str(message))
        except Exception:
            pass


# ============================================================
# HTTP
# ============================================================

def request_get(url, referer=None, timeout=TIMEOUT):

    try:

        headers = {}

        if referer:
            headers["Referer"] = referer

        r = session.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True
        )

        if not r.encoding:
            r.encoding = "utf-8"

        return r

    except Exception:

        return None


# ============================================================
# 텍스트
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    value = html_lib.unescape(str(value))

    value = re.sub(
        r"\\u([0-9a-fA-F]{4})",
        lambda m: chr(int(m.group(1), 16)),
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# 숫자
# ============================================================

def valid_odd(value):

    try:

        value = str(value)

        value = value.replace(
            ",",
            ""
        ).strip()

        value = value.replace(
            '"',
            ""
        ).replace(
            "'",
            ""
        )

        n = float(value)

        if 1.01 <= n <= 100:
            return n

    except Exception:
        pass

    return None


def valid_match_id(value):

    try:

        n = int(
            str(value)
        )

        if 100000 <= n <= 9999999999:
            return str(n)

    except Exception:
        pass

    return None


# ============================================================
# 날짜
# ============================================================

def normalize_date(value):

    if isinstance(value, datetime):

        return value.strftime(
            "%Y-%m-%d"
        )

    value = str(value).strip()

    value = value.replace(
        ".",
        "-"
    )

    value = value.replace(
        "/",
        "-"
    )

    m = re.search(
        r"(20\d{2})-(\d{1,2})-(\d{1,2})",
        value
    )

    if not m:
        return value

    return (
        f"{m.group(1)}-"
        f"{int(m.group(2)):02d}-"
        f"{int(m.group(3)):02d}"
    )


# ============================================================
# URL 정리
# ============================================================

def normalize_url(
    url,
    base_url=BASE_URL
):

    if not url:
        return None

    url = html_lib.unescape(
        str(url)
    ).strip()

    url = url.replace(
        "\\/",
        "/"
    )

    if url.startswith("//"):

        url = "https:" + url

    elif url.startswith("/"):

        url = urljoin(
            base_url,
            url
        )

    elif not url.startswith(
        ("http://", "https://")
    ):

        url = urljoin(
            base_url + "/",
            url
        )

    return url


# ============================================================
# JSON 문자열 정리
# ============================================================

def decode_json_text(text):

    if not text:
        return ""

    value = str(text)

    value = value.replace(
        "\\/",
        "/"
    )

    value = value.replace(
        "&quot;",
        '"'
    )

    value = value.replace(
        "&#39;",
        "'"
    )

    return value


# ============================================================
# URL 후보 추출
# ============================================================

def extract_urls_from_text(
    text,
    base_url
):

    result = []
    seen = set()

    if not text:
        return result

    text = decode_json_text(
        text
    )

    patterns = [

        # https://...
        r'https?://[^"\'<>\s\\]+',

        # //...
        r'//[A-Za-z0-9._:-]+/[^"\'<>\s\\]+',

        # 상대경로 API
        r'["\']((?:/|\./)[^"\']{2,300})["\']',

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I
            )

        except Exception:
            found = []

        for item in found:

            if isinstance(item, tuple):
                item = item[0]

            url = normalize_url(
                item,
                base_url
            )

            if not url:
                continue

            low = url.lower()

            if any(
                x in low
                for x in (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".svg",
                    ".ico",
                    ".woff",
                    ".woff2",
                    ".ttf",
                )
            ):
                continue

            if url not in seen:

                seen.add(url)

                result.append(url)

    return result


# ============================================================
# API URL 판별
# ============================================================

def looks_like_data_url(url):

    if not url:
        return False

    low = url.lower()

    keywords = [

        "api",
        "ajax",
        "json",
        "match",
        "matches",
        "game",
        "games",
        "event",
        "events",
        "odds",
        "oddsdata",
        "score",
        "fixture",
        "schedule",
        "listed",
        "data",

    ]

    score = 0

    for word in keywords:

        if word in low:
            score += 1

    if (
        "7msport.com" in low
        or "7mkr.com" in low
        or "7mdt.com" in low
    ):

        score += 1

    return score >= 2


# ============================================================
# JS URL 추출
# ============================================================

def extract_script_urls(
    page_url,
    html
):

    result = []
    seen = set()

    try:

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        for script in soup.find_all(
            "script"
        ):

            src = script.get(
                "src"
            )

            if not src:
                continue

            url = normalize_url(
                src,
                page_url
            )

            if not url:
                continue

            low = url.lower()

            if (
                ".js" in low
                and url not in seen
            ):

                seen.add(url)

                result.append(
                    url
                )

    except Exception:
        pass

    return result


# ============================================================
# HTML data-* ID 추출
# ============================================================

def extract_ids_from_html(
    text
):

    result = set()

    if not text:
        return result

    patterns = [

        r'data-(?:match-id|matchid)'
        r'\s*=\s*["\'](\d{5,10})["\']',

        r'data-(?:game-id|gameid)'
        r'\s*=\s*["\'](\d{5,10})["\']',

        r'data-(?:event-id|eventid)'
        r'\s*=\s*["\'](\d{5,10})["\']',

        r'data-(?:schedule-id|scheduleid)'
        r'\s*=\s*["\'](\d{5,10})["\']',

        r'data-id\s*=\s*["\'](\d{5,10})["\']',

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I
            )

        except Exception:
            found = []

        for value in found:

            match_id = valid_match_id(
                value
            )

            if match_id:
                result.add(
                    match_id
                )

    return result


# ============================================================
# JSON / JS 안의 ID 추출
# ============================================================

def extract_match_ids_from_text(
    text
):

    result = set()

    if not text:
        return result

    text = decode_json_text(
        text
    )

    patterns = [

        r'"(?:matchId|match_id|matchID)"'
        r'\s*:\s*["\']?(\d{5,10})',

        r'"(?:gameId|game_id|gameID)"'
        r'\s*:\s*["\']?(\d{5,10})',

        r'"(?:eventId|event_id|eventID)"'
        r'\s*:\s*["\']?(\d{5,10})',

        r'"(?:scheduleId|schedule_id|scheduleID)"'
        r'\s*:\s*["\']?(\d{5,10})',

        r'"(?:id|ID)"'
        r'\s*:\s*["\']?(\d{6,10})',

        r'[?&](?:id|mid|matchid|gameid)'
        r'=(\d{5,10})',

        r'/match(?:es)?/(\d{5,10})',

        r'/game(?:s)?/(\d{5,10})',

        r'/event(?:s)?/(\d{5,10})',

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I
            )

        except Exception:
            found = []

        for value in found:

            match_id = valid_match_id(
                value
            )

            if match_id:
                result.add(
                    match_id
                )

    return result


# ============================================================
# 팀명 추출
# ============================================================

def extract_team_pairs(
    text
):

    result = []

    if not text:
        return result

    text = decode_json_text(
        text
    )

    patterns = [

        (
            r'"homeTeam"\s*:\s*"([^"]+)".{0,2000}?'
            r'"awayTeam"\s*:\s*"([^"]+)"'
        ),

        (
            r'"home_team"\s*:\s*"([^"]+)".{0,2000}?'
            r'"away_team"\s*:\s*"([^"]+)"'
        ),

        (
            r'"homeName"\s*:\s*"([^"]+)".{0,2000}?'
            r'"awayName"\s*:\s*"([^"]+)"'
        ),

        (
            r'"home_name"\s*:\s*"([^"]+)".{0,2000}?'
            r'"away_name"\s*:\s*"([^"]+)"'
        ),

        (
            r'"HomeTeam"\s*:\s*"([^"]+)".{0,2000}?'
            r'"AwayTeam"\s*:\s*"([^"]+)"'
        ),

        (
            r'"home"\s*:\s*"([^"]+)".{0,2000}?'
            r'"away"\s*:\s*"([^"]+)"'
        ),

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I | re.S
            )

        except Exception:
            found = []

        for pair in found:

            if not isinstance(
                pair,
                tuple
            ):
                continue

            if len(pair) < 2:
                continue

            home = clean_text(
                pair[0]
            )

            away = clean_text(
                pair[1]
            )

            if (
                1 < len(home) <= 150
                and 1 < len(away) <= 150
                and home != away
            ):

                item = (
                    home,
                    away
                )

                if item not in result:

                    result.append(
                        item
                    )

    return result


# ============================================================
# 스코어 추출
# ============================================================

def extract_scores(
    text
):

    result = []

    if not text:
        return result

    text = decode_json_text(
        text
    )

    patterns = [

        (
            r'"homeScore"\s*:\s*["\']?'
            r'(\d{1,3})'
            r'["\']?.{0,1000}?'
            r'"awayScore"\s*:\s*["\']?'
            r'(\d{1,3})'
        ),

        (
            r'"home_score"\s*:\s*["\']?'
            r'(\d{1,3})'
            r'["\']?.{0,1000}?'
            r'"away_score"\s*:\s*["\']?'
            r'(\d{1,3})'
        ),

        (
            r'"homeGoals"\s*:\s*["\']?'
            r'(\d{1,3})'
            r'["\']?.{0,1000}?'
            r'"awayGoals"\s*:\s*["\']?'
            r'(\d{1,3})'
        ),

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I | re.S
            )

        except Exception:
            found = []

        for item in found:

            try:

                pair = (
                    int(item[0]),
                    int(item[1])
                )

                if pair not in result:

                    result.append(
                        pair
                    )

            except Exception:
                pass

    return result


# ============================================================
# 배당 추출
# ============================================================

def extract_odds(
    text
):

    result = []

    if not text:
        return result

    text = decode_json_text(
        text
    )

    patterns = [

        (
            r'"homeOdds"\s*:\s*'
            r'["\']?([0-9]+(?:\.[0-9]+)?)'
            r'["\']?.{0,1500}?'
            r'"drawOdds"\s*:\s*'
            r'["\']?([0-9]+(?:\.[0-9]+)?)'
            r'["\']?.{0,1500}?'
            r'"awayOdds"\s*:\s*'
            r'["\']?([0-9]+(?:\.[0-9]+)?)'
        ),

        (
            r'"home"\s*:\s*'
            r'["\']?([0-9]+\.[0-9]+)'
            r'["\']?.{0,1500}?'
            r'"draw"\s*:\s*'
            r'["\']?([0-9]+\.[0-9]+)'
            r'["\']?.{0,1500}?'
            r'"away"\s*:\s*'
            r'["\']?([0-9]+\.[0-9]+)'
        ),

        (
            r'"odds1"\s*:\s*'
            r'["\']?([0-9]+\.[0-9]+)'
            r'["\']?.{0,1500}?'
            r'"oddsX"\s*:\s*'
            r'["\']?([0-9]+\.[0-9]+)'
            r'["\']?.{0,1500}?'
            r'"odds2"\s*:\s*'
            r'["\']?([0-9]+\.[0-9]+)'
        ),

        (
            r'"1"\s*:\s*'
            r'["\']?([0-9]+\.[0-9]+)'
            r'["\']?.{0,1000}?'
            r'"X"\s*:\s*'
            r'["\']?([0-9]+\.[0-9]+)'
            r'["\']?.{0,1000}?'
            r'"2"\s*:\s*'
            r'["\']?([0-9]+\.[0-9]+)'
        ),

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I | re.S
            )

        except Exception:
            found = []

        for item in found:

            if len(item) < 3:
                continue

            h = valid_odd(
                item[0]
            )

            d = valid_odd(
                item[1]
            )

            a = valid_odd(
                item[2]
            )

            if (
                h is not None
                and d is not None
                and a is not None
            ):

                value = (
                    h,
                    d,
                    a
                )

                if value not in result:

                    result.append(
                        value
                    )

    return result


# ============================================================
# 결과
# ============================================================

def make_result(
    score
):

    if not score:
        return None

    home, away = score

    if home > away:
        return "승"

    if home == away:
        return "무"

    return "패"


# ============================================================
# 페이지 구조 분석
# ============================================================

def inspect_page(
    url,
    html
):

    ids = set()

    ids.update(
        extract_ids_from_html(
            html
        )
    )

    ids.update(
        extract_match_ids_from_text(
            html
        )
    )

    teams = extract_team_pairs(
        html
    )

    scores = extract_scores(
        html
    )

    odds = extract_odds(
        html
    )

    scripts = extract_script_urls(
        url,
        html
    )

    urls = extract_urls_from_text(
        html,
        url
    )

    api_urls = []

    for item in urls:

        if looks_like_data_url(
            item
        ):

            if item not in api_urls:

                api_urls.append(
                    item
                )

    return {
        "ids": ids,
        "teams": teams,
        "scores": scores,
        "odds": odds,
        "scripts": scripts,
        "urls": urls,
        "api_urls": api_urls,
    }


# ============================================================
# API 응답에서 데이터 찾기
# ============================================================

def analyze_response(
    url,
    text
):

    ids = extract_match_ids_from_text(
        text
    )

    ids.update(
        extract_ids_from_html(
            text
        )
    )

    teams = extract_team_pairs(
        text
    )

    scores = extract_scores(
        text
    )

    odds = extract_odds(
        text
    )

    return {
        "url": url,
        "ids": ids,
        "teams": teams,
        "scores": scores,
        "odds": odds,
        "size": len(text),
    }


# ============================================================
# JS 파일 분석
# ============================================================

def scan_js_file(
    js_url,
    referer=None
):

    r = request_get(
        js_url,
        referer=referer,
        timeout=20
    )

    if r is None:
        return None

    if r.status_code != 200:
        return None

    text = r.text

    result = analyze_response(
        js_url,
        text
    )

    result[
        "scripts"
    ] = extract_script_urls(
        js_url,
        text
    )

    result[
        "urls"
    ] = extract_urls_from_text(
        text,
        js_url
    )

    result[
        "api_urls"
    ] = [

        x
        for x in result["urls"]
        if looks_like_data_url(x)

    ]

    return result


# ============================================================
# 실제 API 자동 탐색
# ============================================================

def discover_api_candidates(
    page_url,
    html,
    log_callback=None
):

    candidates = []
    seen = set()

    def add_url(
        url,
        source=""
    ):

        url = normalize_url(
            url,
            page_url
        )

        if not url:
            return

        low = url.lower()

        if any(
            x in low
            for x in (
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".svg",
                ".css",
                ".woff",
                ".woff2",
            )
        ):
            return

        if url in seen:
            return

        seen.add(url)

        score = 0

        for word in (
            "api",
            "ajax",
            "json",
            "match",
            "game",
            "event",
            "odds",
            "score",
            "fixture",
            "schedule",
            "listed",
            "data",
        ):

            if word in low:
                score += 2

        if (
            "7msport.com" in low
            or "7mkr.com" in low
            or "7mdt.com" in low
        ):

            score += 1

        candidates.append(
            {
                "url": url,
                "score": score,
                "source": source,
            }
        )

    # HTML 직접 분석
    info = inspect_page(
        page_url,
        html
    )

    for url in info["api_urls"]:

        add_url(
            url,
            "HTML"
        )

    # script
    scripts = info["scripts"]

    log(
        log_callback,
        f"script: {len(scripts)}"
    )

    # script 최대 40개
    for index, js_url in enumerate(
        scripts[:40],
        1
    ):

        js = scan_js_file(
            js_url,
            referer=page_url
        )

        if not js:
            continue

        for url in js.get(
            "api_urls",
            []
        ):

            add_url(
                url,
                f"JS:{index}"
            )

    # 점수순
    candidates.sort(
        key=lambda x: (
            x["score"],
            len(x["url"])
        ),
        reverse=True
    )

    return candidates


# ============================================================
# API 검사
# ============================================================

def scan_api_candidates(
    candidates,
    referer,
    max_api=120,
    log_callback=None
):

    valid = []

    total = min(
        len(candidates),
        max_api
    )

    log(
        log_callback,
        f"API 후보: {len(candidates)}"
    )

    log(
        log_callback,
        f"API 자동검사: {total}개"
    )

    for index, item in enumerate(
        candidates[:max_api],
        1
    ):

        url = item["url"]

        r = request_get(
            url,
            referer=referer,
            timeout=12
        )

        if r is None:
            continue

        if r.status_code != 200:
            continue

        text = r.text

        if not text:
            continue

        result = analyze_response(
            url,
            text
        )

        id_count = len(
            result["ids"]
        )

        team_count = len(
            result["teams"]
        )

        odds_count = len(
            result["odds"]
        )

        score = int(
            item.get(
                "score",
                0
            )
        )

        score += min(
            id_count,
            20
        ) * 4

        score += min(
            team_count,
            20
        ) * 8

        score += min(
            odds_count,
            20
        ) * 10

        # 실제 데이터로 보이는 경우
        if (
            id_count > 0
            or team_count > 0
            or odds_count > 0
        ):

            data = {

                "url":
                    url,

                "score":
                    score,

                "ids":
                    result["ids"],

                "teams":
                    result["teams"],

                "scores":
                    result["scores"],

                "odds":
                    result["odds"],

                "size":
                    result["size"],

            }

            valid.append(
                data
            )

            log(
                log_callback,
                (
                    f"API 발견 {len(valid)} | "
                    f"점수={score} | "
                    f"ID={id_count} | "
                    f"팀={team_count} | "
                    f"배당={odds_count} | "
                    f"{url}"
                )
            )

    valid.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return valid


# ============================================================
# 시작 페이지
# ============================================================

def get_start_page(
    date_string,
    log_callback=None
):

    best = None

    candidates = []

    for base in START_URLS:

        candidates.append(
            base
            + "?classid=&view=all&match=&line=no"
        )

        candidates.append(
            base
        )

    seen = set()

    for url in candidates:

        if url in seen:
            continue

        seen.add(url)

        r = request_get(
            url
        )

        if r is None:
            continue

        if r.status_code != 200:
            continue

        if len(r.content) < 10000:
            continue

        score = (
            len(r.content)
            // 100000
        )

        if (
            "match" in r.text.lower()
        ):
            score += 5

        if (
            "odds" in r.text.lower()
        ):
            score += 5

        if best is None or score > best["score"]:

            best = {

                "url":
                    r.url,

                "html":
                    r.text,

                "score":
                    score,

                "http":
                    r.status_code,

                "bytes":
                    len(r.content),

            }

    return best


# ============================================================
# 7M 실제 경기 ID 탐색
# ============================================================

def discover_matches(
    date_string,
    log_callback=None
):

    log(
        log_callback,
        ""
    )

    log(
        log_callback,
        "=========================================="
    )

    log(
        log_callback,
        "🔎 7M API 경기 데이터 자동 탐색"
    )

    log(
        log_callback,
        f"날짜: {date_string}"
    )

    log(
        log_callback,
        "=========================================="
    )

    page = get_start_page(
        date_string,
        log_callback
    )

    if page is None:

        log(
            log_callback,
            "❌ 7M 페이지 접속 실패"
        )

        return {
            "page": None,
            "candidates": [],
            "api_results": [],
            "matches": [],
        }

    log(
        log_callback,
        f"페이지: {page['url']}"
    )

    log(
        log_callback,
        f"HTTP: {page['http']}"
    )

    log(
        log_callback,
        f"HTML: {page['bytes']:,}"
    )

    # --------------------------------------------------------
    # 페이지 자체 데이터
    # --------------------------------------------------------

    page_info = inspect_page(
        page["url"],
        page["html"]
    )

    log(
        log_callback,
        f"페이지 직접 ID: {len(page_info['ids'])}"
    )

    log(
        log_callback,
        f"페이지 직접 배당: {len(page_info['odds'])}"
    )

    # --------------------------------------------------------
    # API 후보
    # --------------------------------------------------------

    api_candidates = discover_api_candidates(
        page["url"],
        page["html"],
        log_callback
    )

    api_results = scan_api_candidates(
        api_candidates,
        referer=page["url"],
        max_api=150,
        log_callback=log_callback
    )

    # --------------------------------------------------------
    # 경기 ID
    # --------------------------------------------------------

    ids = set()

    ids.update(
        page_info["ids"]
    )

    for item in api_results:

        ids.update(
            item.get(
                "ids",
                set()
            )
        )

    matches = []

    for match_id in sorted(
        ids,
        key=lambda x: int(x)
    ):

        matches.append(
            {
                "id": match_id,
                "source_url": None,
            }
        )

    # --------------------------------------------------------
    # 최적 API
    # --------------------------------------------------------

    if api_results:

        best = api_results[0]

        log(
            log_callback,
            ""
        )

        log(
            log_callback,
            "=========================================="
        )

        log(
            log_callback,
            "🏆 최적 경기 데이터 API"
        )

        log(
            log_callback,
            best["url"]
        )

        log(
            log_callback,
            f"점수: {best['score']}"
        )

        log(
            log_callback,
            f"경기 ID: {len(best['ids'])}"
        )

        log(
            log_callback,
            f"팀명: {len(best['teams'])}"
        )

        log(
            log_callback,
            f"배당: {len(best['odds'])}"
        )

        log(
            log_callback,
            "=========================================="
        )

    log(
        log_callback,
        ""
    )

    log(
        log_callback,
        "=========================================="
    )

    log(
        log_callback,
        "최종 탐색"
    )

    log(
        log_callback,
        f"API 후보: {len(api_candidates)}"
    )

    log(
        log_callback,
        f"실제 데이터 API: {len(api_results)}"
    )

    log(
        log_callback,
        f"경기 ID: {len(matches)}"
    )

    log(
        log_callback,
        "=========================================="
    )

    return {
        "page": page,
        "candidates": api_candidates,
        "api_results": api_results,
        "matches": matches,
    }


# ============================================================
# 경기 ID별 상세 데이터
# ============================================================

def find_match_data(
    match_id,
    api_results,
    referer,
    retry_count=2,
    retry_delay=0.5
):

    # --------------------------------------------------------
    # 1. 이미 API 응답에서 ID 주변 데이터를 찾는다.
    # --------------------------------------------------------

    best = None

    for api in api_results:

        if match_id not in api.get(
            "ids",
            set()
        ):
            continue

        score = 0

        if api.get("teams"):
            score += 20

        if api.get("odds"):
            score += 20

        if api.get("scores"):
            score += 10

        data = {

            "match_id":
                match_id,

            "url":
                api["url"],

            "teams":
                api.get(
                    "teams",
                    []
                ),

            "odds":
                api.get(
                    "odds",
                    []
                ),

            "scores":
                api.get(
                    "scores",
                    []
                ),

            "_score":
                score,

        }

        if (
            best is None
            or score > best["_score"]
        ):

            best = data

    # --------------------------------------------------------
    # 2. API URL에 ID를 넣어 재요청
    # --------------------------------------------------------

    urls = []

    for api in api_results:

        url = api["url"]

        parsed = urlparse(
            url
        )

        query = parse_qs(
            parsed.query
        )

        for key in (
            "id",
            "mid",
            "matchid",
            "gameid",
            "eventid",
            "scheduleid",
        ):

            if key in query:

                new_query = dict(
                    query
                )

                new_query[key] = [
                    match_id
                ]

                parts = list(
                    parsed
                )

                from urllib.parse import urlencode

                parts[4] = urlencode(
                    new_query,
                    doseq=True
                )

                new_url = (
                    parts[0]
                    + "://"
                    + parts[1]
                    + parts[2]
                    + (
                        "?"
                        + parts[4]
                        if parts[4]
                        else ""
                    )
                )

                if new_url not in urls:

                    urls.append(
                        new_url
                    )

    for attempt in range(
        retry_count + 1
    ):

        for url in urls:

            r = request_get(
                url,
                referer=referer,
                timeout=15
            )

            if r is None:
                continue

            if r.status_code != 200:
                continue

            data = analyze_response(
                url,
                r.text
            )

            if (
                data["teams"]
                or data["odds"]
                or data["scores"]
            ):

                score = 0

                if data["teams"]:
                    score += 20

                if data["odds"]:
                    score += 20

                if data["scores"]:
                    score += 10

                candidate = {

                    "match_id":
                        match_id,

                    "url":
                        url,

                    "teams":
                        data["teams"],

                    "odds":
                        data["odds"],

                    "scores":
                        data["scores"],

                    "_score":
                        score,

                }

                if (
                    best is None
                    or score > best["_score"]
                ):

                    best = candidate

                if (
                    data["teams"]
                    and data["odds"]
                ):

                    return candidate

        if attempt < retry_count:

            time.sleep(
                retry_delay
            )

    return best


# ============================================================
# 진단
# ============================================================

def diagnose(
    date_string,
    cid="",
    log_callback=None
):

    date_string = normalize_date(
        date_string
    )

    log(
        log_callback,
        f"7M 연결 진단 시작: {date_string}"
    )

    data = discover_matches(
        date_string,
        log_callback
    )

    page = data.get(
        "page"
    )

    api_candidates = data.get(
        "candidates",
        []
    )

    api_results = data.get(
        "api_results",
        []
    )

    matches = data.get(
        "matches",
        []
    )

    result = {

        "date":
            date_string,

        "http":
            page.get(
                "http",
                0
            )
            if page
            else 0,

        "html_bytes":
            page.get(
                "bytes",
                0
            )
            if page
            else 0,

        "js_bytes":
            0,

        "scripts":
            0,

        "iframes":
            0,

        "api_candidates":
            len(api_candidates),

        "api_results":
            len(api_results),

        "match_ids":
            len(matches),

        "matches":
            matches,

        "api_data":
            api_results,

        "page_url":
            page.get(
                "url",
                ""
            )
            if page
            else "",

    }

    # --------------------------------------------------------
    # JS 크기 계산
    # --------------------------------------------------------

    if page:

        scripts = extract_script_urls(
            page["url"],
            page["html"]
        )

        result[
            "scripts"
        ] = len(scripts)

        js_total = 0

        for js_url in scripts[:20]:

            r = request_get(
                js_url,
                referer=page["url"],
                timeout=10
            )

            if r and r.status_code == 200:

                js_total += len(
                    r.content
                )

        result[
            "js_bytes"
        ] = js_total

    log(
        log_callback,
        ""
    )

    log(
        log_callback,
        "=========================================="
    )

    log(
        log_callback,
        "최종 진단"
    )

    log(
        log_callback,
        f"HTTP: {result['http']}"
    )

    log(
        log_callback,
        f"HTML: {result['html_bytes']:,}"
    )

    log(
        log_callback,
        f"JS: {result['js_bytes']:,}"
    )

    log(
        log_callback,
        f"script: {result['scripts']}"
    )

    log(
        log_callback,
        f"API 후보: {result['api_candidates']}"
    )

    log(
        log_callback,
        f"실제 데이터 API: {result['api_results']}"
    )

    log(
        log_callback,
        f"경기 ID: {result['match_ids']}"
    )

    if result["match_ids"] > 0:

        log(
            log_callback,
            "✅ 7M 경기 데이터를 찾았습니다."
        )

    else:

        log(
            log_callback,
            "⚠️ 경기 ID를 찾지 못했습니다."
        )

    log(
        log_callback,
        "=========================================="
    )

    return result


# ============================================================
# 하루 수집
# ============================================================

def collect_date(
    date_string,
    cid="",
    retry_count=3,
    retry_delay=1.0,
    log_callback=None
):

    date_string = normalize_date(
        date_string
    )

    discovered = discover_matches(
        date_string,
        log_callback
    )

    api_results = discovered.get(
        "api_results",
        []
    )

    matches = discovered.get(
        "matches",
        []
    )

    if not matches:

        log(
            log_callback,
            "❌ 수집 가능한 경기 ID가 없습니다."
        )

        return []

    total = len(matches)

    log(
        log_callback,
        ""
    )

    log(
        log_callback,
        f"🎯 수집 대상: {total}경기"
    )

    results = []

    for index, item in enumerate(
        matches,
        1
    ):

        match_id = item["id"]

        log(
            log_callback,
            f"[{index}/{total}] ID {match_id}"
        )

        detail = find_match_data(
            match_id,
            api_results,
            referer=(
                discovered["page"]["url"]
                if discovered.get("page")
                else BASE_URL
            ),
            retry_count=retry_count,
            retry_delay=retry_delay
        )

        if detail is None:

            log(
                log_callback,
                "  ❌ 데이터 없음"
            )

            continue

        teams = detail.get(
            "teams",
            []
        )

        odds = detail.get(
            "odds",
            []
        )

        scores = detail.get(
            "scores",
            []
        )

        home_team = ""
        away_team = ""

        if teams:

            home_team = clean_text(
                teams[-1][0]
            )

            away_team = clean_text(
                teams[-1][1]
            )

        final_odds = None

        if odds:

            # 마지막 배당 = 최종배당
            final_odds = odds[-1]

        score = None

        if scores:

            score = scores[-1]

        result_value = make_result(
            score
        )

        # ----------------------------------------------------
        # 최소 데이터 조건
        # ----------------------------------------------------

        if (
            not home_team
            and not away_team
            and not final_odds
            and not score
        ):

            log(
                log_callback,
                "  ⚠️ 실제 경기 데이터 없음"
            )

            continue

        item_result = {

            "match_id":
                match_id,

            "match_date":
                date_string,

            "home_team":
                home_team,

            "away_team":
                away_team,

            "home_score":
                score[0]
                if score
                else None,

            "away_score":
                score[1]
                if score
                else None,

            "result":
                result_value,

            "home_odds":
                final_odds[0]
                if final_odds
                else None,

            "draw_odds":
                final_odds[1]
                if final_odds
                else None,

            "away_odds":
                final_odds[2]
                if final_odds
                else None,

            "bookmaker":
                "7M",

            "cid":
                cid or "",

            "url":
                detail.get(
                    "url"
                ),

        }

        results.append(
            item_result
        )

        log(
            log_callback,
            (
                "  ✅ "
                f"{home_team or '-'}"
                " vs "
                f"{away_team or '-'}"
                " | "
                f"{final_odds if final_odds else '-'}"
                " | "
                f"{result_value or '-'}"
            )
        )

    # 중복 제거
    unique = {}

    for item in results:

        unique[
            item["match_id"]
        ] = item

    results = list(
        unique.values()
    )

    log(
        log_callback,
        ""
    )

    log(
        log_callback,
        "=========================================="
    )

    log(
        log_callback,
        f"🏁 {date_string} 수집 완료"
    )

    log(
        log_callback,
        f"경기: {len(results)}"
    )

    odds_count = sum(
        1
        for item in results
        if (
            item.get(
                "home_odds"
            ) is not None
            and item.get(
                "draw_odds"
            ) is not None
            and item.get(
                "away_odds"
            ) is not None
        )
    )

    result_count = sum(
        1
        for item in results
        if item.get(
            "result"
        )
    )

    log(
        log_callback,
        f"최종배당: {odds_count}"
    )

    log(
        log_callback,
        f"실제결과: {result_count}"
    )

    log(
        log_callback,
        "=========================================="
    )

    return results


# ============================================================
# 기간 수집
# ============================================================

def collect(
    start_date,
    end_date,
    cid="",
    retry_count=3,
    retry_delay=1.0,
    log_callback=None
):

    start_date = normalize_date(
        start_date
    )

    end_date = normalize_date(
        end_date
    )

    start = datetime.strptime(
        start_date,
        "%Y-%m-%d"
    )

    end = datetime.strptime(
        end_date,
        "%Y-%m-%d"
    )

    all_results = []

    current = start

    while current <= end:

        date_string = current.strftime(
            "%Y-%m-%d"
        )

        daily = collect_date(
            date_string,
            cid=cid,
            retry_count=retry_count,
            retry_delay=retry_delay,
            log_callback=log_callback
        )

        all_results.extend(
            daily
        )

        current += timedelta(
            days=1
        )

    # 중복 제거
    unique = {}

    for item in all_results:

        key = (
            item.get(
                "match_id"
            ),
            item.get(
                "home_team"
            ),
            item.get(
                "away_team"
            ),
        )

        unique[key] = item

    all_results = list(
        unique.values()
    )

    odds_count = sum(
        1
        for item in all_results
        if (
            item.get(
                "home_odds"
            ) is not None
            and item.get(
                "draw_odds"
            ) is not None
            and item.get(
                "away_odds"
            ) is not None
        )
    )

    result_count = sum(
        1
        for item in all_results
        if item.get(
            "result"
        )
    )

    log(
        log_callback,
        ""
    )

    log(
        log_callback,
        "=========================================="
    )

    log(
        log_callback,
        "🏆 전체 수집 완료"
    )

    log(
        log_callback,
        f"총 경기: {len(all_results)}"
    )

    log(
        log_callback,
        f"최종배당: {odds_count}"
    )

    log(
        log_callback,
        f"실제결과: {result_count}"
    )

    log(
        log_callback,
        "=========================================="
    )

    return all_results


# ============================================================
# 단독 테스트
# ============================================================

if __name__ == "__main__":

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    print(
        f"7M API 테스트: {today}"
    )

    diagnose(
        today,
        log_callback=print
                )
