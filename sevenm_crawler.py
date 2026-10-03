# ============================================================
# sevenm_crawler.py
# ⚽ 7M 축구 최종배당 수집기
#
# 현재 7M 동적 페이지 대응
# - HTML 경기 링크 탐색
# - data-* 경기 ID 탐색
# - JSON/JS 내부 경기 ID 탐색
# - iframe 탐색
# - script 탐색
# - API 후보 탐색
# - 경기 상세 후보 자동 탐색
# - 1X2 배당 추출
# - 스코어/결과 추출
# ============================================================

import re
import time
import json
import html as html_lib
import requests

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import (
    urljoin,
    urlparse,
    parse_qs,
    unquote,
)


# ============================================================
# 기본 설정
# ============================================================

BASE_URL = "https://live.7msport.com"
DATA_URL = "https://data.7msport.com"

START_URLS = [
    f"{BASE_URL}/default_kr.aspx",
    f"{BASE_URL}/default_en.aspx",
    f"{BASE_URL}/default_ms.aspx",
    f"{BASE_URL}/default_vn.aspx",
]

TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept-Language": (
        "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8"
    ),
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
}


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

def request_get(url, referer=None, params=None):

    try:

        headers = {}

        if referer:
            headers["Referer"] = referer

        response = session.get(
            url,
            headers=headers,
            params=params,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        if not response.encoding:
            response.encoding = response.apparent_encoding or "utf-8"

        return response

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
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# ============================================================
# 숫자
# ============================================================

def valid_odd(value):

    try:

        value = (
            str(value)
            .replace(",", "")
            .strip()
        )

        value = value.replace(
            '"',
            ""
        ).replace(
            "'",
            ""
        )

        number = float(value)

        if 1.01 <= number <= 100:
            return number

    except Exception:
        pass

    return None


def valid_score(value):

    try:

        number = int(str(value).strip())

        if 0 <= number <= 99:
            return number

    except Exception:
        pass

    return None


# ============================================================
# 날짜
# ============================================================

def normalize_date(value):

    if isinstance(value, datetime):

        return value.strftime("%Y-%m-%d")

    value = str(value).strip()

    value = value.replace(".", "-")
    value = value.replace("/", "-")

    match = re.search(
        r"(20\d{2})-(\d{1,2})-(\d{1,2})",
        value,
    )

    if not match:
        return value

    return (
        f"{match.group(1)}-"
        f"{int(match.group(2)):02d}-"
        f"{int(match.group(3)):02d}"
    )


# ============================================================
# HTML 링크
# ============================================================

def extract_links(page_url, source_html):

    result = []

    try:

        soup = BeautifulSoup(
            source_html,
            "html.parser",
        )

        for tag in soup.find_all(
            ["a", "area"]
        ):

            href = (
                tag.get("href")
                or tag.get("data-href")
                or tag.get("data-url")
                or tag.get("data-link")
                or ""
            )

            href = href.strip()

            if not href:
                continue

            if href.lower().startswith(
                ("javascript:", "mailto:", "#")
            ):
                continue

            absolute = urljoin(
                page_url,
                href,
            )

            if absolute not in result:
                result.append(absolute)

    except Exception:
        pass

    return result


# ============================================================
# URL 경기 ID
# ============================================================

def extract_match_id_from_url(url):

    if not url:
        return None

    decoded = unquote(str(url))

    # query parameter
    query_patterns = [
        r"[?&](?:id|mid|matchid|match_id)="
        r"(\d{4,12})",

        r"[?&](?:gameid|game_id)="
        r"(\d{4,12})",

        r"[?&](?:eventid|event_id)="
        r"(\d{4,12})",

        r"[?&](?:fid|fixtureid)="
        r"(\d{4,12})",
    ]

    for pattern in query_patterns:

        match = re.search(
            pattern,
            decoded,
            re.I,
        )

        if match:

            value = match.group(1)

            if 1000 <= int(value):
                return value

    # path
    path_patterns = [
        r"/match(?:es)?/(\d{4,12})",
        r"/game(?:s)?/(\d{4,12})",
        r"/event(?:s)?/(\d{4,12})",
        r"/fixture(?:s)?/(\d{4,12})",
        r"/detail/(\d{4,12})",
        r"/odds/(\d{4,12})",
    ]

    for pattern in path_patterns:

        match = re.search(
            pattern,
            decoded,
            re.I,
        )

        if match:
            return match.group(1)

    # 숫자 slug
    slug_patterns = [
        r"(?:match|game|event|fixture)"
        r"[-_/](\d{4,12})",
    ]

    for pattern in slug_patterns:

        match = re.search(
            pattern,
            decoded,
            re.I,
        )

        if match:
            return match.group(1)

    return None


# ============================================================
# HTML 내부 경기 ID
# ============================================================

def extract_match_ids(source_html):

    ids = set()

    patterns = [

        # data attributes
        r'data-(?:match-id|matchid|match_id)'
        r'\s*=\s*["\'](\d{4,12})["\']',

        r'data-(?:game-id|gameid|game_id)'
        r'\s*=\s*["\'](\d{4,12})["\']',

        r'data-(?:event-id|eventid|event_id)'
        r'\s*=\s*["\'](\d{4,12})["\']',

        r'data-(?:fixture-id|fixtureid)'
        r'\s*=\s*["\'](\d{4,12})["\']',

        # JSON
        r'"(?:matchId|matchID|match_id)"'
        r'\s*:\s*["\']?(\d{4,12})',

        r'"(?:gameId|gameID|game_id)"'
        r'\s*:\s*["\']?(\d{4,12})',

        r'"(?:eventId|eventID|event_id)"'
        r'\s*:\s*["\']?(\d{4,12})',

        r'"(?:fixtureId|fixtureID|fixture_id)"'
        r'\s*:\s*["\']?(\d{4,12})',

        # URL embedded
        r'/(?:match|game|event|fixture)/'
        r'(\d{4,12})',

        r'[?&](?:id|mid|matchid|gameid|eventid)='
        r'(\d{4,12})',
    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                source_html,
                re.I,
            )

            for value in found:

                try:

                    number = int(value)

                    if 1000 <= number <= 999999999999:
                        ids.add(str(number))

                except Exception:
                    pass

        except Exception:
            pass

    return ids


# ============================================================
# 경기 링크
# ============================================================

def extract_real_match_links(
    page_url,
    source_html,
):

    result = []

    links = extract_links(
        page_url,
        source_html,
    )

    for url in links:

        match_id = extract_match_id_from_url(
            url
        )

        if not match_id:
            continue

        low = url.lower()

        if any(
            x in low
            for x in (
                ".js",
                ".css",
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".svg",
                ".ico",
            )
        ):
            continue

        result.append(
            {
                "id": match_id,
                "url": url,
            }
        )

    unique = {}

    for item in result:
        unique[item["id"]] = item

    return list(unique.values())


# ============================================================
# iframe
# ============================================================

def extract_iframes(
    page_url,
    source_html,
):

    result = []

    try:

        soup = BeautifulSoup(
            source_html,
            "html.parser",
        )

        for tag in soup.find_all("iframe"):

            src = (
                tag.get("src")
                or tag.get("data-src")
                or tag.get("data-url")
                or ""
            )

            if not src:
                continue

            url = urljoin(
                page_url,
                src,
            )

            if url not in result:
                result.append(url)

    except Exception:
        pass

    return result


# ============================================================
# script
# ============================================================

def extract_scripts(
    page_url,
    source_html,
):

    result = []

    try:

        soup = BeautifulSoup(
            source_html,
            "html.parser",
        )

        for tag in soup.find_all("script"):

            src = tag.get("src")

            if src:

                url = urljoin(
                    page_url,
                    src,
                )

                if url not in result:
                    result.append(url)

    except Exception:
        pass

    return result


# ============================================================
# API 후보
# ============================================================

def extract_api_candidates(
    page_url,
    source_html,
):

    result = []

    # URL 문자열
    url_patterns = [

        r'https?://[^"\'\s<>]+',

        r'["\']([^"\']{1,500}'
        r'(?:/api/|/ajax/|/data/|'
        r'/json/|/service/|/interface/)'
        r'[^"\']*)["\']',

        r'["\']([^"\']{1,500}'
        r'(?:\.json|\.ashx|\.asmx)'
        r'[^"\']*)["\']',
    ]

    for pattern in url_patterns:

        try:

            found = re.findall(
                pattern,
                source_html,
                re.I,
            )

            for value in found:

                if isinstance(value, tuple):
                    value = value[0]

                value = html_lib.unescape(
                    str(value)
                )

                if not value:
                    continue

                if value.startswith(
                    ("//", "/")
                ):

                    value = urljoin(
                        page_url,
                        value,
                    )

                if not value.startswith(
                    ("http://", "https://")
                ):
                    continue

                low = value.lower()

                if any(
                    x in low
                    for x in (
                        ".png",
                        ".jpg",
                        ".jpeg",
                        ".gif",
                        ".svg",
                        ".css",
                    )
                ):
                    continue

                if (
                    "/api/" in low
                    or "/ajax/" in low
                    or "/data/" in low
                    or "/json/" in low
                    or "/service/" in low
                    or "/interface/" in low
                    or ".json" in low
                    or ".ashx" in low
                    or ".asmx" in low
                ):

                    if value not in result:
                        result.append(value)

        except Exception:
            pass

    return result


# ============================================================
# 팀명 추출
# ============================================================

def extract_teams(source_html):

    result = []

    patterns = [

        (
            r'"homeTeam"\s*:\s*"([^"]+)".{0,1500}?'
            r'"awayTeam"\s*:\s*"([^"]+)"'
        ),

        (
            r'"home_team"\s*:\s*"([^"]+)".{0,1500}?'
            r'"away_team"\s*:\s*"([^"]+)"'
        ),

        (
            r'"homeName"\s*:\s*"([^"]+)".{0,1500}?'
            r'"awayName"\s*:\s*"([^"]+)"'
        ),

        (
            r'"HomeTeam"\s*:\s*"([^"]+)".{0,1500}?'
            r'"AwayTeam"\s*:\s*"([^"]+)"'
        ),

        (
            r'"home"\s*:\s*"([^"]+)".{0,1500}?'
            r'"away"\s*:\s*"([^"]+)"'
        ),

        (
            r'"home_name"\s*:\s*"([^"]+)".{0,1500}?'
            r'"away_name"\s*:\s*"([^"]+)"'
        ),
    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                source_html,
                re.I | re.S,
            )

            for pair in found:

                home = clean_text(pair[0])
                away = clean_text(pair[1])

                if (
                    2 <= len(home) <= 150
                    and 2 <= len(away) <= 150
                ):

                    item = (
                        home,
                        away,
                    )

                    if item not in result:
                        result.append(item)

        except Exception:
            pass

    return result


# ============================================================
# 화면 텍스트 팀명
# ============================================================

def extract_teams_from_visible_text(
    source_html
):

    result = []

    try:

        soup = BeautifulSoup(
            source_html,
            "html.parser",
        )

        # script/style 제거
        for tag in soup(
            ["script", "style", "noscript"]
        ):
            tag.decompose()

        text = clean_text(
            soup.get_text(" ")
        )

        patterns = [

            r"([A-Za-zÀ-ÿ0-9가-힣][^|]{1,80})"
            r"\s+(?:vs\.?|VS|v)\s+"
            r"([^|]{1,80})",

            r"([A-Za-zÀ-ÿ0-9가-힣][^]{1,80})"
            r"\s+-\s+"
            r"([^|]{1,80})",
        ]

        for pattern in patterns:

            try:

                found = re.findall(
                    pattern,
                    text,
                    re.I,
                )

                for pair in found:

                    home = clean_text(pair[0])
                    away = clean_text(pair[1])

                    if (
                        2 <= len(home) <= 100
                        and 2 <= len(away) <= 100
                    ):

                        value = (
                            home,
                            away,
                        )

                        if value not in result:
                            result.append(value)

            except Exception:
                pass

    except Exception:
        pass

    return result


# ============================================================
# 스코어
# ============================================================

def extract_score(source_html):

    patterns = [

        (
            r'"homeScore"\s*:\s*["\']?'
            r'(\d{1,2})["\']?.{0,1000}?'
            r'"awayScore"\s*:\s*["\']?'
            r'(\d{1,2})'
        ),

        (
            r'"home_score"\s*:\s*["\']?'
            r'(\d{1,2})["\']?.{0,1000}?'
            r'"away_score"\s*:\s*["\']?'
            r'(\d{1,2})'
        ),

        (
            r'"HomeScore"\s*:\s*["\']?'
            r'(\d{1,2})["\']?.{0,1000}?'
            r'"AwayScore"\s*:\s*["\']?'
            r'(\d{1,2})'
        ),

    ]

    for pattern in patterns:

        try:

            match = re.search(
                pattern,
                source_html,
                re.I | re.S,
            )

            if match:

                home = valid_score(
                    match.group(1)
                )

                away = valid_score(
                    match.group(2)
                )

                if (
                    home is not None
                    and away is not None
                ):
                    return (
                        home,
                        away,
                    )

        except Exception:
            pass

    return None


# ============================================================
# 1X2 배당
# ============================================================

def extract_odds(source_html):

    result = []

    patterns = [

        (
            r'"home"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1200}?'
            r'"draw"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1200}?'
            r'"away"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
        ),

        (
            r'"homeOdds"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1200}?'
            r'"drawOdds"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1200}?'
            r'"awayOdds"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
        ),

        (
            r'"odds1"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1200}?'
            r'"oddsX"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1200}?'
            r'"odds2"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
        ),

        (
            r'"1"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1200}?'
            r'"X"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1200}?'
            r'"2"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
        ),

        (
            r'"win"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1200}?'
            r'"draw"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1200}?'
            r'"lose"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
        ),
    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                source_html,
                re.I | re.S,
            )

            for item in found:

                h = valid_odd(item[0])
                d = valid_odd(item[1])
                a = valid_odd(item[2])

                if (
                    h is None
                    or d is None
                    or a is None
                ):
                    continue

                value = (
                    h,
                    d,
                    a,
                )

                if value not in result:
                    result.append(value)

        except Exception:
            pass

    return result


# ============================================================
# 결과
# ============================================================

def make_result(score):

    if not score:
        return None

    home, away = score

    if home > away:
        return "승"

    if home == away:
        return "무"

    return "패"


# ============================================================
# 상세 페이지
# ============================================================

def inspect_match_url(
    url,
    match_id,
    referer=None,
):

    response = request_get(
        url,
        referer=referer,
    )

    if response is None:
        return None

    if response.status_code != 200:
        return None

    source_html = response.text

    teams = extract_teams(
        source_html
    )

    if not teams:

        teams = extract_teams_from_visible_text(
            source_html
        )

    score = extract_score(
        source_html
    )

    odds = extract_odds(
        source_html
    )

    return {
        "match_id": match_id,
        "url": response.url,
        "html": source_html,
        "teams": teams[0] if teams else None,
        "score": score,
        "odds": odds,
        "size": len(response.content),
        "status_code": response.status_code,
    }


# ============================================================
# 경기 상세 URL 후보
# ============================================================

def candidate_match_urls(match_id):

    return [

        f"{BASE_URL}/match.aspx?id={match_id}",
        f"{BASE_URL}/match.shtml?id={match_id}",

        f"{BASE_URL}/match_data.aspx?id={match_id}",
        f"{BASE_URL}/match_data.shtml?id={match_id}",

        f"{BASE_URL}/odds.aspx?id={match_id}",
        f"{BASE_URL}/odds.shtml?id={match_id}",

        f"{BASE_URL}/game.aspx?id={match_id}",
        f"{BASE_URL}/game.shtml?id={match_id}",

        f"{BASE_URL}/event.aspx?id={match_id}",
        f"{BASE_URL}/event.shtml?id={match_id}",

        f"{DATA_URL}/match/{match_id}",
        f"{DATA_URL}/game/{match_id}",
    ]


# ============================================================
# 경기 가져오기
# ============================================================

def get_match(
    match_id,
    source_url=None,
    retry_count=2,
    retry_delay=0.5,
):

    urls = []

    if source_url:
        urls.append(source_url)

    for url in candidate_match_urls(
        match_id
    ):

        if url not in urls:
            urls.append(url)

    best = None

    for attempt in range(
        retry_count + 1
    ):

        for url in urls:

            detail = inspect_match_url(
                url,
                match_id,
                referer=(
                    source_url
                    or BASE_URL
                ),
            )

            if detail is None:
                continue

            score = 0

            if detail.get("teams"):
                score += 10

            if detail.get("odds"):
                score += 10

            if detail.get("score"):
                score += 5

            if detail.get("size", 0) > 5000:
                score += 2

            detail["_score"] = score

            if (
                best is None
                or score > best["_score"]
            ):
                best = detail

            if (
                detail.get("teams")
                and detail.get("odds")
            ):
                return detail

        if attempt < retry_count:
            time.sleep(retry_delay)

    return best


# ============================================================
# 시작 페이지
# ============================================================

def get_start_page(
    date_string,
    log_callback=None,
):

    best = None

    for base_url in START_URLS:

        candidates = [
            base_url,
            (
                f"{base_url}"
                f"?date={date_string}"
            ),
            (
                f"{base_url}"
                f"?date={date_string}"
                f"&view=all"
            ),
        ]

        for url in candidates:

            response = request_get(url)

            if response is None:
                continue

            if response.status_code != 200:
                continue

            if len(response.content) < 5000:
                continue

            source_html = response.text

            links = extract_real_match_links(
                response.url,
                source_html,
            )

            ids = extract_match_ids(
                source_html
            )

            iframes = extract_iframes(
                response.url,
                source_html,
            )

            scripts = extract_scripts(
                response.url,
                source_html,
            )

            apis = extract_api_candidates(
                response.url,
                source_html,
            )

            score = (
                len(links) * 20
                + len(ids) * 10
                + len(apis) * 3
                + len(iframes) * 2
                + len(scripts)
                + len(response.content) // 100000
            )

            candidate = {
                "url": response.url,
                "html": source_html,
                "links": links,
                "ids": ids,
                "iframes": iframes,
                "scripts": scripts,
                "apis": apis,
                "score": score,
            }

            if (
                best is None
                or score > best["score"]
            ):
                best = candidate

    return best


# ============================================================
# 진단
# ============================================================

def diagnose(
    date_string,
    cid="",
    log_callback=None,
):

    date_string = normalize_date(
        date_string
    )

    log(
        log_callback,
        "",
    )

    log(
        log_callback,
        "==========================================",
    )

    log(
        log_callback,
        "🔎 7M 실제 경기 링크 진단",
    )

    log(
        log_callback,
        f"날짜: {date_string}",
    )

    log(
        log_callback,
        "==========================================",
    )

    page = get_start_page(
        date_string,
        log_callback=log_callback,
    )

    result = {
        "date": date_string,
        "http": 0,
        "html_bytes": 0,
        "js_bytes": 0,
        "match_links": 0,
        "match_ids": 0,
        "match_candidates": 0,
        "iframes": 0,
        "scripts": 0,
        "apis": 0,
        "api_candidates": [],
        "script_urls": [],
        "iframe_urls": [],
        "matches": [],
        "page_url": "",
    }

    if page is None:

        log(
            log_callback,
            "❌ 7M 시작 페이지 실패",
        )

        return result

    source_html = page["html"]

    result["http"] = 200
    result["page_url"] = page["url"]

    result["html_bytes"] = len(
        source_html.encode(
            errors="ignore"
        )
    )

    result["iframes"] = len(
        page["iframes"]
    )

    result["scripts"] = len(
        page["scripts"]
    )

    result["apis"] = len(
        page["apis"]
    )

    result["api_candidates"] = page[
        "apis"
    ]

    result["script_urls"] = page[
        "scripts"
    ]

    result["iframe_urls"] = page[
        "iframes"
    ]

    # JS 총 크기 계산
    js_bytes = 0

    for script_url in page["scripts"]:

        try:

            script_response = request_get(
                script_url,
                referer=page["url"],
            )

            if (
                script_response is not None
                and script_response.status_code == 200
            ):

                js_bytes += len(
                    script_response.content
                )

        except Exception:
            pass

    result["js_bytes"] = js_bytes

    log(
        log_callback,
        f"페이지: {page['url']}",
    )

    log(
        log_callback,
        "HTTP: 200",
    )

    log(
        log_callback,
        f"HTML: {result['html_bytes']:,}",
    )

    log(
        log_callback,
        f"JS: {result['js_bytes']:,}",
    )

    log(
        log_callback,
        f"iframe: {result['iframes']}",
    )

    log(
        log_callback,
        f"script: {result['scripts']}",
    )

    log(
        log_callback,
        f"API 후보: {result['apis']}",
    )

    # --------------------------------------------------------
    # 링크
    # --------------------------------------------------------

    matches = list(
        page["links"]
    )

    # --------------------------------------------------------
    # ID만 발견된 경우
    # --------------------------------------------------------

    existing_ids = {
        item["id"]
        for item in matches
    }

    for match_id in sorted(
        page["ids"],
        key=lambda x: int(x),
    ):

        if match_id in existing_ids:
            continue

        matches.append(
            {
                "id": match_id,
                "url": "",
            }
        )

    # --------------------------------------------------------
    # JS 파일에서도 경기 ID 탐색
    # --------------------------------------------------------

    js_match_ids = set()

    for script_url in page["scripts"]:

        try:

            script_response = request_get(
                script_url,
                referer=page["url"],
            )

            if (
                script_response is None
                or script_response.status_code != 200
            ):
                continue

            found = extract_match_ids(
                script_response.text
            )

            js_match_ids.update(
                found
            )

        except Exception:
            pass

    for match_id in sorted(
        js_match_ids,
        key=lambda x: int(x),
    ):

        if match_id in existing_ids:
            continue

        if any(
            item["id"] == match_id
            for item in matches
        ):
            continue

        matches.append(
            {
                "id": match_id,
                "url": "",
            }
        )

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

    unique = {}

    for item in matches:

        match_id = item.get("id")

        if not match_id:
            continue

        unique[match_id] = item

    matches = list(
        unique.values()
    )

    result["matches"] = matches

    result["match_links"] = len(matches)
    result["match_ids"] = len(matches)
    result["match_candidates"] = len(matches)

    log(
        log_callback,
        f"발견 후보: {len(matches)}",
    )

    if page["apis"]:

        log(
            log_callback,
            "🔌 API 후보:",
        )

        for api in page["apis"][:20]:

            log(
                log_callback,
                f"  {api}",
            )

    # --------------------------------------------------------
    # 샘플
    # --------------------------------------------------------

    log(
        log_callback,
        "",
    )

    log(
        log_callback,
        "🧪 실제 경기 5개 샘플 검사",
    )

    valid = []

    for index, item in enumerate(
        matches[:5],
        1,
    ):

        match_id = item["id"]

        log(
            log_callback,
            (
                f"[샘플 {index}/5] "
                f"ID={match_id}"
            ),
        )

        detail = get_match(
            match_id,
            source_url=item.get("url") or None,
            retry_count=1,
            retry_delay=0.3,
        )

        if detail is None:

            log(
                log_callback,
                "  ❌ 상세 데이터 없음",
            )

            continue

        teams = detail.get(
            "teams"
        )

        odds = detail.get(
            "odds"
        )

        score = detail.get(
            "score"
        )

        log(
            log_callback,
            (
                f"  ✅ 팀={teams} "
                f"배당={odds[-1] if odds else None} "
                f"결과={make_result(score)}"
            ),
        )

        valid.append(detail)

    log(
        log_callback,
        "",
    )

    log(
        log_callback,
        "==========================================",
    )

    log(
        log_callback,
        "진단 결과",
    )

    log(
        log_callback,
        f"발견 후보: {len(matches)}",
    )

    log(
        log_callback,
        f"샘플 성공: {len(valid)}/{min(5, len(matches))}",
    )

    log(
        log_callback,
        "==========================================",
    )

    return result


# ============================================================
# 날짜 1일 수집
# ============================================================

def collect_date(
    date_string,
    cid="",
    retry_count=3,
    retry_delay=1.0,
    log_callback=None,
):

    date_string = normalize_date(
        date_string
    )

    diagnosis = diagnose(
        date_string,
        cid=cid,
        log_callback=log_callback,
    )

    matches = diagnosis.get(
        "matches",
        [],
    )

    if not matches:

        log(
            log_callback,
            "❌ 현재 HTML/JS에서 경기 ID를 발견하지 못했습니다.",
        )

        log(
            log_callback,
            "⚠️ 7M 경기 데이터가 동적으로 로딩되는 구조일 수 있습니다.",
        )

        return []

    results = []

    total = len(matches)

    log(
        log_callback,
        "",
    )

    log(
        log_callback,
        f"🎯 실제 경기 후보 {total}개 수집 시작",
    )

    for index, item in enumerate(
        matches,
        1,
    ):

        match_id = item["id"]

        log(
            log_callback,
            f"[{index}/{total}] ID {match_id}",
        )

        detail = get_match(
            match_id,
            source_url=item.get("url") or None,
            retry_count=retry_count,
            retry_delay=retry_delay,
        )

        if detail is None:

            log(
                log_callback,
                "  ❌ 상세 데이터 없음",
            )

            continue

        teams = detail.get(
            "teams"
        )

        score = detail.get(
            "score"
        )

        odds_list = detail.get(
            "odds"
        )

        home_team = ""
        away_team = ""

        if teams:

            home_team = clean_text(
                teams[0]
            )

            away_team = clean_text(
                teams[1]
            )

        final_odds = None

        if odds_list:
            final_odds = odds_list[-1]

        result_value = make_result(
            score
        )

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

        if (
            not home_team
            and not away_team
            and not final_odds
        ):

            log(
                log_callback,
                "  ⚠️ 경기 정보 부족",
            )

            continue

        results.append(
            item_result
        )

        log(
            log_callback,
            (
                "  ✅ "
                f"{home_team} vs {away_team} | "
                f"{final_odds if final_odds else '-'} | "
                f"{result_value or '-'}"
            ),
        )

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
        "",
    )

    log(
        log_callback,
        "==========================================",
    )

    log(
        log_callback,
        f"🏁 {date_string} 수집 완료",
    )

    log(
        log_callback,
        f"경기 저장 대상: {len(results)}",
    )

    log(
        log_callback,
        "==========================================",
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
    log_callback=None,
):

    start_date = normalize_date(
        start_date
    )

    end_date = normalize_date(
        end_date
    )

    start = datetime.strptime(
        start_date,
        "%Y-%m-%d",
    )

    end = datetime.strptime(
        end_date,
        "%Y-%m-%d",
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
            log_callback=log_callback,
        )

        all_results.extend(
            daily
        )

        current += timedelta(
            days=1
        )

    unique = {}

    for item in all_results:

        key = (
            item.get("match_id"),
            item.get("home_team"),
            item.get("away_team"),
        )

        unique[key] = item

    all_results = list(
        unique.values()
    )

    log(
        log_callback,
        "",
    )

    log(
        log_callback,
        "==========================================",
    )

    log(
        log_callback,
        "🏆 전체 수집 완료",
    )

    log(
        log_callback,
        f"총 경기: {len(all_results)}",
    )

    odds_count = sum(
        1
        for x in all_results
        if (
            x.get("home_odds") is not None
            and x.get("draw_odds") is not None
            and x.get("away_odds") is not None
        )
    )

    result_count = sum(
        1
        for x in all_results
        if x.get("result")
    )

    log(
        log_callback,
        f"최종배당: {odds_count}",
    )

    log(
        log_callback,
        f"실제결과: {result_count}",
    )

    log(
        log_callback,
        "==========================================",
    )

    return all_results


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    print(
        f"7M 테스트: {today}"
    )

    diagnose(
        today,
        log_callback=print,
    )
