# ============================================================
# sevenm_crawler.py
# 7M 축구 최종배당 수집 · 분석기
# 구조 진단 + API/iframe/script 실제 URL 표시
# ============================================================

import re
import json
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# 기본 설정
# ============================================================

BASE_URLS = [
    "https://data.7msport.com",
    "https://live.7msport.com",
    "https://www.7msport.com",
    "https://kr.7msport.com",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 16; K) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,image/webp,"
        "*/*;q=0.8"
    ),
    "Accept-Language": (
        "ko-KR,ko;q=0.9,"
        "en-US;q=0.8,en;q=0.7"
    ),
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
}

TIMEOUT = 15

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# 로그
# ============================================================

def _log(callback, message):

    if callback is None:
        return

    try:
        callback(str(message))
    except Exception:
        pass


# ============================================================
# HTTP
# ============================================================

def _get(
    url,
    timeout=TIMEOUT,
    referer=None
):

    headers = {}

    if referer:
        headers["Referer"] = referer

    try:

        response = session.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True
        )

        if not response.encoding:

            response.encoding = "utf-8"

        return response

    except Exception:

        return None


# ============================================================
# 문자열
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    value = str(value)

    value = re.sub(
        r"<[^>]+>",
        " ",
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

def safe_float(value):

    try:

        value = str(
            value
        ).replace(
            ",",
            ""
        ).strip()

        m = re.search(
            r"\d+(?:\.\d+)?",
            value
        )

        if not m:
            return None

        number = float(
            m.group(0)
        )

        if number <= 1:
            return None

        if number > 100:
            return None

        return number

    except Exception:

        return None


# ============================================================
# 결과
# ============================================================

def calculate_result(
    home_score,
    away_score
):

    try:

        home = int(
            home_score
        )

        away = int(
            away_score
        )

    except Exception:

        return None

    if home > away:
        return "승"

    if home == away:
        return "무"

    return "패"


# ============================================================
# 날짜
# ============================================================

def normalize_date(
    value
):

    if isinstance(
        value,
        datetime
    ):

        return value.strftime(
            "%Y-%m-%d"
        )

    value = str(
        value
    ).strip()

    value = value.replace(
        "/",
        "-"
    )

    value = value.replace(
        ".",
        "-"
    )

    value = re.sub(
        r"-+",
        "-",
        value
    )

    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d",
    ):

        try:

            return datetime.strptime(
                value,
                fmt
            ).strftime(
                "%Y-%m-%d"
            )

        except Exception:

            pass

    return value


# ============================================================
# 날짜 URL 후보
# ============================================================

def date_url_candidates(
    date_string
):

    date_string = normalize_date(
        date_string
    )

    d = datetime.strptime(
        date_string,
        "%Y-%m-%d"
    )

    y = d.year
    m = d.month
    day = d.day

    formats = [
        f"{y}-{m:02d}-{day:02d}",
        f"{y}-{m}-{day}",
        f"{y}/{m:02d}/{day:02d}",
        f"{y}/{m}/{day}",
    ]

    urls = []

    for date_value in formats:

        urls.extend([

            f"https://data.7msport.com/"
            f"result_data/default_en.shtml"
            f"?date={date_value}",

            f"https://data.7msport.com/"
            f"fixture_data/default_en.shtml"
            f"?date={date_value}",

            f"https://data.7msport.com/"
            f"result/default_en.shtml"
            f"?date={date_value}",

            f"https://data.7msport.com/"
            f"fixture/default_en.shtml"
            f"?date={date_value}",

            f"https://live.7msport.com/"
            f"default_en.aspx"
            f"?date={date_value}",

            f"https://live.7msport.com/"
            f"default.aspx"
            f"?date={date_value}",

            f"https://kr.7msport.com/"
            f"default_en.aspx"
            f"?date={date_value}",

            f"https://kr.7msport.com/"
            f"default_kr.aspx"
            f"?date={date_value}",

        ])

    return list(
        dict.fromkeys(
            urls
        )
    )


# ============================================================
# URL 정리
# ============================================================

def normalize_url(
    base_url,
    value
):

    if not value:
        return ""

    value = str(
        value
    ).strip()

    value = value.replace(
        "\\/",
        "/"
    )

    if value.startswith(
        "//"
    ):

        parsed = urlparse(
            base_url
        )

        return (
            parsed.scheme
            + ":"
            + value
        )

    return urljoin(
        base_url,
        value
    )


# ============================================================
# Script URL 추출
# ============================================================

def find_script_urls(
    page_url,
    page_html
):

    urls = []

    try:

        soup = BeautifulSoup(
            page_html,
            "html.parser"
        )

    except Exception:

        return urls

    for tag in soup.find_all(
        "script"
    ):

        src = (
            tag.get("src")
            or tag.get("data-src")
            or ""
        ).strip()

        if not src:
            continue

        full = normalize_url(
            page_url,
            src
        )

        if (
            full
            and full not in urls
        ):

            urls.append(
                full
            )

    return urls


# ============================================================
# iframe URL 추출
# ============================================================

def find_iframe_urls(
    page_url,
    page_html
):

    urls = []

    try:

        soup = BeautifulSoup(
            page_html,
            "html.parser"
        )

    except Exception:

        return urls

    for tag in soup.find_all(
        "iframe"
    ):

        src = (

            tag.get("src")

            or tag.get("data-src")

            or tag.get("data-url")

            or ""

        ).strip()

        if not src:
            continue

        full = normalize_url(
            page_url,
            src
        )

        if (
            full
            and full not in urls
        ):

            urls.append(
                full
            )

    return urls


# ============================================================
# API 후보 추출
# ============================================================

def find_api_urls(
    page_url,
    page_html
):

    urls = []

    # --------------------------------------------------------
    # HTML / JS에서 URL 문자열 탐색
    # --------------------------------------------------------

    patterns = [

        r'["\']([^"\']{1,500}'
        r'(?:ajax|api|json|ashx|odds|match|fixture|schedule)'
        r'[^"\']{0,500})["\']',

        r'["\']([^"\']+\.json'
        r'(?:\?[^"\']*)?)["\']',

        r'["\']([^"\']+\.ashx'
        r'(?:\?[^"\']*)?)["\']',

        r'["\']([^"\']+\.aspx'
        r'(?:\?[^"\']*)?)["\']',

        r'["\']([^"\']+ajax[^"\']*)["\']',

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                page_html,
                re.I
            )

        except Exception:

            continue

        for value in found:

            value = (
                str(value)
                .strip()
            )

            if not value:
                continue

            if len(value) > 1000:
                continue

            full = normalize_url(
                page_url,
                value
            )

            if not full:
                continue

            low = full.lower()

            if any(
                key in low
                for key in (
                    "ajax",
                    "api",
                    "json",
                    "ashx",
                    "odds",
                    "match",
                    "fixture",
                    "schedule",
                )
            ):

                if full not in urls:

                    urls.append(
                        full
                    )

    # --------------------------------------------------------
    # JS 변수 안의 endpoint
    # --------------------------------------------------------

    endpoint_patterns = [

        r'(?:url|api|endpoint|ajaxUrl|apiUrl)'
        r'\s*[:=]\s*["\']([^"\']+)["\']',

        r'(?:get|post|ajax)'
        r'\s*\(\s*["\']([^"\']+)["\']',

    ]

    for pattern in endpoint_patterns:

        try:

            found = re.findall(
                pattern,
                page_html,
                re.I
            )

        except Exception:

            continue

        for value in found:

            full = normalize_url(
                page_url,
                value
            )

            if full and full not in urls:

                urls.append(
                    full
                )

    return urls


# ============================================================
# 경기 ID 추출
# ============================================================

def find_match_ids(
    page_html
):

    ids = set()

    patterns = [

        r'[?&](?:id|sid|mid|fid)'
        r'=(\d{4,12})',

        r'(?:matchid|match_id)'
        r'\s*[=:]\s*["\']?'
        r'(\d{4,12})',

        r'(?:gameid|game_id)'
        r'\s*[=:]\s*["\']?'
        r'(\d{4,12})',

        r'(?:scheduleid|schedule_id)'
        r'\s*[=:]\s*["\']?'
        r'(\d{4,12})',

        r'(?:eventid|event_id)'
        r'\s*[=:]\s*["\']?'
        r'(\d{4,12})',

        r'data-(?:id|match-id|game-id)'
        r'=["\'](\d{4,12})',

        r'/(\d{5,12})'
        r'(?:\.shtml|\.html|\.aspx)',

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                page_html,
                re.I
            )

        except Exception:

            continue

        for value in found:

            try:

                number = int(
                    value
                )

                if (
                    1000
                    <= number
                    <= 999999999999
                ):

                    ids.add(
                        str(number)
                    )

            except Exception:

                pass

    return sorted(
        ids,
        key=lambda x: int(x)
    )


# ============================================================
# 링크 추출
# ============================================================

def find_all_links(
    page_url,
    page_html
):

    links = []

    try:

        soup = BeautifulSoup(
            page_html,
            "html.parser"
        )

    except Exception:

        return links

    for tag in soup.find_all(
        "a"
    ):

        href = (
            tag.get("href")
            or ""
        ).strip()

        if not href:
            continue

        full = normalize_url(
            page_url,
            href
        )

        if (
            full
            and full not in links
        ):

            links.append(
                full
            )

    return links


# ============================================================
# 경기 관련 링크만
# ============================================================

def find_match_links(
    page_url,
    page_html
):

    all_links = find_all_links(
        page_url,
        page_html
    )

    result = []

    keywords = [

        "match",

        "fixture",

        "odds",

        "result",

        "game",

        "detail",

        "schedule",

    ]

    for url in all_links:

        low = url.lower()

        if any(
            key in low
            for key in keywords
        ):

            if url not in result:

                result.append(
                    url
                )

    return result


# ============================================================
# 팀 이름 후보
# ============================================================

def extract_team_pairs(
    page_html
):

    result = []

    patterns = [

        r'"homeTeam"\s*:\s*"([^"]+)"'
        r'.{0,1000}?'
        r'"awayTeam"\s*:\s*"([^"]+)"',

        r'"home_team"\s*:\s*"([^"]+)"'
        r'.{0,1000}?'
        r'"away_team"\s*:\s*"([^"]+)"',

        r'"homeName"\s*:\s*"([^"]+)"'
        r'.{0,1000}?'
        r'"awayName"\s*:\s*"([^"]+)"',

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                page_html,
                re.I | re.S
            )

        except Exception:

            continue

        for item in found:

            if len(item) != 2:
                continue

            home = clean_text(
                item[0]
            )

            away = clean_text(
                item[1]
            )

            if (
                home
                and away
            ):

                pair = (
                    home,
                    away
                )

                if pair not in result:

                    result.append(
                        pair
                    )

    return result


# ============================================================
# 스코어
# ============================================================

def extract_scores(
    page_html
):

    result = []

    patterns = [

        r'"homeScore"\s*:\s*["\']?(\d+)',
        r'"awayScore"\s*:\s*["\']?(\d+)',

    ]

    homes = []
    aways = []

    try:

        homes = re.findall(
            patterns[0],
            page_html,
            re.I
        )

        aways = re.findall(
            patterns[1],
            page_html,
            re.I
        )

    except Exception:

        pass

    if homes and aways:

        count = min(
            len(homes),
            len(aways)
        )

        for i in range(
            count
        ):

            result.append(
                (
                    int(
                        homes[i]
                    ),
                    int(
                        aways[i]
                    )
                )
            )

    # 일반 1-0 형태
    try:

        found = re.findall(
            r'\b(\d{1,2})\s*[-:]\s*(\d{1,2})\b',
            page_html
        )

        for item in found:

            home = int(
                item[0]
            )

            away = int(
                item[1]
            )

            if (
                home <= 30
                and away <= 30
            ):

                pair = (
                    home,
                    away
                )

                if pair not in result:

                    result.append(
                        pair
                    )

    except Exception:

        pass

    return result


# ============================================================
# 1X2 배당
# ============================================================

def extract_1x2_odds(
    page_html
):

    result = []

    patterns = [

        r'"home"\s*:\s*'
        r'([0-9]+\.[0-9]+)'
        r'.{0,500}?'
        r'"draw"\s*:\s*'
        r'([0-9]+\.[0-9]+)'
        r'.{0,500}?'
        r'"away"\s*:\s*'
        r'([0-9]+\.[0-9]+)',

        r'"homeOdds"\s*:\s*'
        r'([0-9]+\.[0-9]+)'
        r'.{0,500}?'
        r'"drawOdds"\s*:\s*'
        r'([0-9]+\.[0-9]+)'
        r'.{0,500}?'
        r'"awayOdds"\s*:\s*'
        r'([0-9]+\.[0-9]+)',

        r'"odds1"\s*:\s*'
        r'([0-9]+\.[0-9]+)'
        r'.{0,500}?'
        r'"oddsX"\s*:\s*'
        r'([0-9]+\.[0-9]+)'
        r'.{0,500}?'
        r'"odds2"\s*:\s*'
        r'([0-9]+\.[0-9]+)',

        r'\b'
        r'([1-9]\d?\.\d{1,3})'
        r'\s+'
        r'([1-9]\d?\.\d{1,3})'
        r'\s+'
        r'([1-9]\d?\.\d{1,3})'
        r'\b',

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                page_html,
                re.I | re.S
            )

        except Exception:

            continue

        for item in found:

            if len(item) != 3:
                continue

            home = safe_float(
                item[0]
            )

            draw = safe_float(
                item[1]
            )

            away = safe_float(
                item[2]
            )

            if (
                home
                and draw
                and away
            ):

                value = (
                    home,
                    draw,
                    away
                )

                if value not in result:

                    result.append(
                        value
                    )

    return result


# ============================================================
# API 응답 분석
# ============================================================

def inspect_api(
    url,
    referer="",
    log_callback=None
):

    result = {

        "url":
            url,

        "status":
            0,

        "bytes":
            0,

        "content_type":
            "",

        "match_ids":
            [],

        "odds":
            [],

        "teams":
            [],

        "preview":
            "",

    }

    response = _get(
        url,
        timeout=8,
        referer=referer
    )

    if response is None:

        _log(
            log_callback,
            f"API 접속 실패: {url}"
        )

        return result

    result[
        "status"
    ] = response.status_code

    result[
        "bytes"
    ] = len(
        response.content
    )

    result[
        "content_type"
    ] = response.headers.get(
        "Content-Type",
        ""
    )

    text = response.text

    result[
        "match_ids"
    ] = find_match_ids(
        text
    )

    result[
        "odds"
    ] = extract_1x2_odds(
        text
    )

    result[
        "teams"
    ] = extract_team_pairs(
        text
    )

    # 앞부분 일부만 로그
    clean_preview = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    result[
        "preview"
    ] = clean_preview[:1000]

    _log(
        log_callback,
        "------------------------------------------"
    )

    _log(
        log_callback,
        f"API URL: {url}"
    )

    _log(
        log_callback,
        f"HTTP: {response.status_code}"
    )

    _log(
        log_callback,
        f"크기: {len(response.content):,} bytes"
    )

    _log(
        log_callback,
        f"Content-Type: "
        f"{result['content_type']}"
    )

    _log(
        log_callback,
        f"경기 ID: "
        f"{len(result['match_ids'])}"
    )

    _log(
        log_callback,
        f"팀 후보: "
        f"{len(result['teams'])}"
    )

    _log(
        log_callback,
        f"배당 후보: "
        f"{len(result['odds'])}"
    )

    _log(
        log_callback,
        "응답 미리보기:"
    )

    _log(
        log_callback,
        result["preview"]
    )

    return result


# ============================================================
# 페이지 진단
# ============================================================

def diagnose(
    date_string,
    cid="",
    log_callback=None
):

    date_string = normalize_date(
        date_string
    )

    result = {

        "date":
            date_string,

        "http":
            0,

        "html_bytes":
            0,

        "js_bytes":
            0,

        "iframes":
            0,

        "scripts":
            0,

        "apis":
            0,

        "match_candidates":
            0,

        "odds_candidates":
            0,

        "api_urls":
            [],

        "iframe_urls":
            [],

        "script_urls":
            [],

        "match_urls":
            [],

        "match_ids":
            [],

        "api_details":
            [],

        "page_url":
            "",

    }

    _log(
        log_callback,
        ""
    )

    _log(
        log_callback,
        "=========================================="
    )

    _log(
        log_callback,
        "🔎 7M 구조 상세 진단"
    )

    _log(
        log_callback,
        f"진단 날짜: {date_string}"
    )

    _log(
        log_callback,
        "=========================================="
    )

    # --------------------------------------------------------
    # 날짜 페이지
    # --------------------------------------------------------

    page_url = ""
    page_html = ""

    for url in date_url_candidates(
        date_string
    ):

        _log(
            log_callback,
            f"페이지 확인: {url}"
        )

        response = _get(
            url
        )

        if response is None:
            continue

        _log(
            log_callback,
            f"HTTP {response.status_code} / "
            f"{len(response.content):,} bytes"
        )

        if (
            response.status_code == 200
            and len(response.text) > 500
        ):

            page_url = response.url
            page_html = response.text

            break

    if not page_html:

        _log(
            log_callback,
            "❌ 7M 페이지를 찾지 못했습니다."
        )

        return result

    result[
        "http"
    ] = 200

    result[
        "html_bytes"
    ] = len(
        page_html
    )

    result[
        "page_url"
    ] = page_url

    _log(
        log_callback,
        ""
    )

    _log(
        log_callback,
        f"✅ 실제 페이지: {page_url}"
    )

    _log(
        log_callback,
        f"HTML: {len(page_html):,} bytes"
    )

    # --------------------------------------------------------
    # script
    # --------------------------------------------------------

    script_urls = find_script_urls(
        page_url,
        page_html
    )

    result[
        "script_urls"
    ] = script_urls

    result[
        "scripts"
    ] = len(
        script_urls
    )

    _log(
        log_callback,
        ""
    )

    _log(
        log_callback,
        f"📜 script: {len(script_urls)}"
    )

    for index, url in enumerate(
        script_urls[:30],
        1
    ):

        _log(
            log_callback,
            f"SCRIPT {index}: {url}"
        )

    # --------------------------------------------------------
    # iframe
    # --------------------------------------------------------

    iframe_urls = find_iframe_urls(
        page_url,
        page_html
    )

    result[
        "iframe_urls"
    ] = iframe_urls

    result[
        "iframes"
    ] = len(
        iframe_urls
    )

    _log(
        log_callback,
        ""
    )

    _log(
        log_callback,
        f"🖼 iframe: {len(iframe_urls)}"
    )

    for index, url in enumerate(
        iframe_urls,
        1
    ):

        _log(
            log_callback,
            f"IFRAME {index}: {url}"
        )

    # --------------------------------------------------------
    # HTML 자체 API
    # --------------------------------------------------------

    api_urls = find_api_urls(
        page_url,
        page_html
    )

    # --------------------------------------------------------
    # JS 실제 내용 분석
    # --------------------------------------------------------

    js_total = 0

    for script_url in script_urls[:20]:

        response = _get(
            script_url,
            timeout=6,
            referer=page_url
        )

        if response is None:
            continue

        if response.status_code != 200:
            continue

        js_text = response.text

        js_total += len(
            js_text
        )

        found_api = find_api_urls(
            script_url,
            js_text
        )

        for api_url in found_api:

            if api_url not in api_urls:

                api_urls.append(
                    api_url
                )

    result[
        "js_bytes"
    ] = js_total

    # --------------------------------------------------------
    # iframe 내용 분석
    # --------------------------------------------------------

    for iframe_url in iframe_urls[:10]:

        iframe_response = _get(
            iframe_url,
            timeout=8,
            referer=page_url
        )

        if iframe_response is None:
            continue

        if iframe_response.status_code != 200:
            continue

        iframe_text = (
            iframe_response.text
        )

        iframe_api = find_api_urls(
            iframe_url,
            iframe_text
        )

        for api_url in iframe_api:

            if api_url not in api_urls:

                api_urls.append(
                    api_url
                )

    # --------------------------------------------------------
    # 경기 링크
    # --------------------------------------------------------

    match_urls = find_match_links(
        page_url,
        page_html
    )

    result[
        "match_urls"
    ] = match_urls

    # --------------------------------------------------------
    # ID
    # --------------------------------------------------------

    match_ids = find_match_ids(
        page_html
    )

    # 링크에서도 ID 추출
    for url in match_urls:

        ids = find_match_ids(
            url
        )

        for match_id in ids:

            if match_id not in match_ids:

                match_ids.append(
                    match_id
                )

    result[
        "match_ids"
    ] = sorted(
        set(match_ids),
        key=lambda x: int(x)
    )

    result[
        "match_candidates"
    ] = len(
        result["match_ids"]
    )

    # --------------------------------------------------------
    # 페이지 배당
    # --------------------------------------------------------

    odds = extract_1x2_odds(
        page_html
    )

    result[
        "odds_candidates"
    ] = len(
        odds
    )

    # --------------------------------------------------------
    # API 표시
    # --------------------------------------------------------

    result[
        "api_urls"
    ] = list(
        dict.fromkeys(
            api_urls
        )
    )

    result[
        "apis"
    ] = len(
        result["api_urls"]
    )

    _log(
        log_callback,
        ""
    )

    _log(
        log_callback,
        "=========================================="
    )

    _log(
        log_callback,
        f"📡 API 후보: {len(api_urls)}"
    )

    if api_urls:

        for index, url in enumerate(
            api_urls[:50],
            1
        ):

            _log(
                log_callback,
                f"API {index}: {url}"
            )

    else:

        _log(
            log_callback,
            "API 후보가 없습니다."
        )

    # --------------------------------------------------------
    # 경기 링크 표시
    # --------------------------------------------------------

    _log(
        log_callback,
        ""
    )

    _log(
        log_callback,
        f"🔗 경기 상세 링크: "
        f"{len(match_urls)}"
    )

    for index, url in enumerate(
        match_urls[:30],
        1
    ):

        _log(
            log_callback,
            f"MATCH {index}: {url}"
        )

    # --------------------------------------------------------
    # ID 표시
    # --------------------------------------------------------

    _log(
        log_callback,
        ""
    )

    _log(
        log_callback,
        f"🆔 경기 ID 후보: "
        f"{len(result['match_ids'])}"
    )

    if result["match_ids"]:

        _log(
            log_callback,
            ", ".join(
                result["match_ids"][:50]
            )
        )

    # --------------------------------------------------------
    # API 실제 요청
    # --------------------------------------------------------

    api_details = []

    for api_url in api_urls[:10]:

        detail = inspect_api(
            api_url,
            referer=page_url,
            log_callback=log_callback
        )

        api_details.append(
            detail
        )

        # API에서 경기 ID가 발견되면 추가
        for match_id in detail.get(
            "match_ids",
            []
        ):

            if match_id not in match_ids:

                match_ids.append(
                    match_id
                )

    result[
        "api_details"
    ] = api_details

    result[
        "match_ids"
    ] = sorted(
        set(match_ids),
        key=lambda x: int(x)
    )

    result[
        "match_candidates"
    ] = len(
        result["match_ids"]
    )

    _log(
        log_callback,
        ""
    )

    _log(
        log_callback,
        "=========================================="
    )

    _log(
        log_callback,
        "진단 최종 결과"
    )

    _log(
        log_callback,
        f"HTTP: {result['http']}"
    )

    _log(
        log_callback,
        f"HTML: {result['html_bytes']:,}"
    )

    _log(
        log_callback,
        f"JS: {result['js_bytes']:,}"
    )

    _log(
        log_callback,
        f"iframe: {result['iframes']}"
    )

    _log(
        log_callback,
        f"script: {result['scripts']}"
    )

    _log(
        log_callback,
        f"API 후보: {result['apis']}"
    )

    _log(
        log_callback,
        f"경기 후보: {result['match_candidates']}"
    )

    _log(
        log_callback,
        f"배당 후보: {result['odds_candidates']}"
    )

    _log(
        log_callback,
        "=========================================="
    )

    return result


# ============================================================
# 날짜별 수집
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

    _log(
        log_callback,
        ""
    )

    _log(
        log_callback,
        f"📅 {date_string} 7M 수집 시작"
    )

    diagnosis = diagnose(
        date_string=date_string,
        cid=cid,
        log_callback=log_callback
    )

    matches = []

    # --------------------------------------------------------
    # ID가 발견되었으면 상세 페이지 탐색
    # --------------------------------------------------------

    match_ids = diagnosis.get(
        "match_ids",
        []
    )

    _log(
        log_callback,
        f"수집 대상 경기 ID: "
        f"{len(match_ids)}"
    )

    for index, match_id in enumerate(
        match_ids[:500],
        1
    ):

        _log(
            log_callback,
            f"[{index}/{len(match_ids)}] "
            f"경기 {match_id}"
        )

        # 가능한 상세 주소
        detail_urls = [

            f"https://data.7msport.com/"
            f"odds.shtml?id={match_id}",

            f"https://data.7msport.com/"
            f"match.shtml?id={match_id}",

            f"https://data.7msport.com/"
            f"match_data.shtml?id={match_id}",

            f"https://data.7msport.com/"
            f"result.shtml?id={match_id}",

        ]

        found = None

        for detail_url in detail_urls:

            response = _get(
                detail_url,
                timeout=8
            )

            if response is None:
                continue

            if response.status_code != 200:
                continue

            if len(
                response.text
            ) < 300:

                continue

            found = (
                detail_url,
                response.text
            )

            break

        if found is None:
            continue

        detail_url, detail_html = found

        teams = extract_team_pairs(
            detail_html
        )

        scores = extract_scores(
            detail_html
        )

        odds = extract_1x2_odds(
            detail_html
        )

        item = {

            "match_id":
                str(match_id),

            "match_date":
                date_string,

            "home_team":
                "",

            "away_team":
                "",

            "home_score":
                None,

            "away_score":
                None,

            "result":
                None,

            "home_odds":
                None,

            "draw_odds":
                None,

            "away_odds":
                None,

            "bookmaker":
                "7M",

            "cid":
                cid,

            "url":
                detail_url,

        }

        if teams:

            item[
                "home_team"
            ] = teams[0][0]

            item[
                "away_team"
            ] = teams[0][1]

        if scores:

            item[
                "home_score"
            ] = scores[0][0]

            item[
                "away_score"
            ] = scores[0][1]

            item[
                "result"
            ] = calculate_result(
                scores[0][0],
                scores[0][1]
            )

        if odds:

            last_odds = odds[-1]

            item[
                "home_odds"
            ] = last_odds[0]

            item[
                "draw_odds"
            ] = last_odds[1]

            item[
                "away_odds"
            ] = last_odds[2]

        if (
            item["home_team"]
            or item["away_team"]
            or item["home_odds"]
        ):

            matches.append(
                item
            )

            _log(
                log_callback,
                f"  ✅ "
                f"{item['home_team']} "
                f"vs "
                f"{item['away_team']} | "
                f"{item['home_odds']} / "
                f"{item['draw_odds']} / "
                f"{item['away_odds']} | "
                f"{item['result']}"
            )

        time.sleep(
            max(
                0,
                float(
                    retry_delay
                )
            )
        )

    # --------------------------------------------------------
    # ID가 하나도 없으면 페이지 경기행 시도
    # --------------------------------------------------------

    if not match_ids:

        _log(
            log_callback,
            "⚠️ ID가 없어 페이지 구조 기반 탐색을 실행합니다."
        )

        page_url = diagnosis.get(
            "page_url",
            ""
        )

        if page_url:

            response = _get(
                page_url
            )

            if response is not None:

                html_text = (
                    response.text
                )

                soup = BeautifulSoup(
                    html_text,
                    "html.parser"
                )

                rows = soup.find_all(
                    "tr"
                )

                for row in rows:

                    text = row.get_text(
                        " ",
                        strip=True
                    )

                    if len(text) < 5:
                        continue

                    # 점수가 있는 경우
                    score = re.search(
                        r"\b(\d{1,2})\s*[-:]\s*(\d{1,2})\b",
                        text
                    )

                    if not score:
                        continue

                    home_score = int(
                        score.group(1)
                    )

                    away_score = int(
                        score.group(2)
                    )

                    item = {

                        "match_id":
                            "",

                        "match_date":
                            date_string,

                        "home_team":
                            "",

                        "away_team":
                            "",

                        "home_score":
                            home_score,

                        "away_score":
                            away_score,

                        "result":
                            calculate_result(
                                home_score,
                                away_score
                            ),

                        "home_odds":
                            None,

                        "draw_odds":
                            None,

                        "away_odds":
                            None,

                        "bookmaker":
                            "7M",

                        "cid":
                            cid,

                        "url":
                            page_url,

                    }

                    # 링크의 텍스트
                    anchors = row.find_all(
                        "a"
                    )

                    names = []

                    for a in anchors:

                        name = clean_text(
                            a.get_text(
                                " ",
                                strip=True
                            )
                        )

                        if (
                            name
                            and len(name) < 100
                        ):

                            names.append(
                                name
                            )

                    if len(names) >= 2:

                        item[
                            "home_team"
                        ] = names[0]

                        item[
                            "away_team"
                        ] = names[1]

                    if (
                        item["home_team"]
                        and item["away_team"]
                    ):

                        matches.append(
                            item
                        )

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

    unique = {}

    for item in matches:

        key = (

            item.get(
                "match_id"
            ),

            item.get(
                "match_date"
            ),

            item.get(
                "home_team"
            ),

            item.get(
                "away_team"
            ),

        )

        unique[key] = item

    matches = list(
        unique.values()
    )

    _log(
        log_callback,
        ""
    )

    _log(
        log_callback,
        f"📊 {date_string} 최종 경기: "
        f"{len(matches)}"
    )

    return matches


# ============================================================
# 전체 기간 수집
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

    all_matches = []

    current = start

    while current <= end:

        date_string = current.strftime(
            "%Y-%m-%d"
        )

        try:

            daily = collect_date(

                date_string,

                cid=cid,

                retry_count=retry_count,

                retry_delay=retry_delay,

                log_callback=log_callback
            )

            all_matches.extend(
                daily
            )

        except Exception as e:

            _log(
                log_callback,
                f"❌ {date_string} 오류: {e}"
            )

        current += timedelta(
            days=1
        )

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

    unique = {}

    for item in all_matches:

        key = (

            item.get(
                "match_id"
            ),

            item.get(
                "match_date"
            ),

            item.get(
                "home_team"
            ),

            item.get(
                "away_team"
            ),

        )

        unique[key] = item

    all_matches = list(
        unique.values()
    )

    odds_count = 0
    result_count = 0

    for item in all_matches:

        if (
            item.get(
                "home_odds"
            ) is not None
            and
            item.get(
                "draw_odds"
            ) is not None
            and
            item.get(
                "away_odds"
            ) is not None
        ):

            odds_count += 1

        if item.get(
            "result"
        ):

            result_count += 1

    _log(
        log_callback,
        ""
    )

    _log(
        log_callback,
        "=========================================="
    )

    _log(
        log_callback,
        "🎯 7M 전체 수집 완료"
    )

    _log(
        log_callback,
        f"전체 경기: {len(all_matches)}"
    )

    _log(
        log_callback,
        f"최종배당: {odds_count}"
    )

    _log(
        log_callback,
        f"실제결과: {result_count}"
    )

    _log(
        log_callback,
        "=========================================="
    )

    return all_matches


# ============================================================
# 단독 테스트
# ============================================================

if __name__ == "__main__":

    test_date = (
        datetime.now().strftime(
            "%Y-%m-%d"
        )
    )

    print(
        "7M 상세 진단"
    )

    result = diagnose(
        test_date,
        log_callback=print
    )

    print()
    print(
        "페이지:",
        result.get(
            "page_url"
        )
    )

    print()
    print(
        "API URL:"
    )

    for url in result.get(
        "api_urls",
        []
    ):

        print(
            url
        )

    print()
    print(
        "iframe URL:"
    )

    for url in result.get(
        "iframe_urls",
        []
    ):

        print(
            url
        )

    print()
    print(
        "경기 ID:"
    )

    for match_id in result.get(
        "match_ids",
        []
    )[:100]:

        print(
            match_id
    )
