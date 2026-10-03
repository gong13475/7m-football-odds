# ============================================================
# sevenm_crawler.py
# ============================================================
# 7M 축구 최종배당 수집 · 분석기
#
# 기능
# 1. 7M 메인 페이지 탐색
# 2. iframe 자동 탐색
# 3. JS 자동 수집
# 4. API 후보 자동 탐색
# 5. API 후보 실제 응답 검사
# 6. 경기 ID 자동 탐색
# 7. 경기 상세 페이지 탐색
# 8. 팀명 / 결과 / 1X2 배당 탐색
# 9. 최종배당 우선 저장
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

BASE_URL = "https://data.7msport.com"

LIVE_URL = "https://live.7msport.com"

KR_URL = "https://kr.7msport.com"

KR2_URL = "https://kr2.7msport.com"

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
        "image/apng,*/*;q=0.8"
    ),
    "Accept-Language": (
        "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
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

def log(callback, message):

    if callback is None:
        return

    try:
        callback(str(message))
    except Exception:
        pass


# ============================================================
# HTTP
# ============================================================

def get(url, referer=None, timeout=TIMEOUT):

    try:

        headers = {}

        if referer:
            headers["Referer"] = referer

        response = session.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True
        )

        response.encoding = (
            response.apparent_encoding
            or response.encoding
            or "utf-8"
        )

        return response

    except Exception:

        return None


# ============================================================
# 텍스트
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
# URL
# ============================================================

def make_url(base, value):

    if not value:
        return ""

    value = str(value).strip()

    value = value.replace(
        "\\/",
        "/"
    )

    if value.startswith("//"):

        scheme = urlparse(base).scheme

        return scheme + ":" + value

    return urljoin(
        base,
        value
    )


# ============================================================
# 날짜
# ============================================================

def normalize_date(value):

    if isinstance(
        value,
        datetime
    ):

        return value.strftime(
            "%Y-%m-%d"
        )

    value = str(value).strip()

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
# 숫자
# ============================================================

def number(value):

    try:

        value = str(value).strip()

        value = value.replace(
            ",",
            ""
        )

        m = re.search(
            r"\d+(?:\.\d+)?",
            value
        )

        if not m:
            return None

        n = float(
            m.group(0)
        )

        if n <= 1:
            return None

        if n > 100:
            return None

        return n

    except Exception:

        return None


# ============================================================
# 결과
# ============================================================

def result_from_score(
    home,
    away
):

    try:

        home = int(home)
        away = int(away)

    except Exception:

        return None

    if home > away:
        return "승"

    if home == away:
        return "무"

    return "패"


# ============================================================
# iframe
# ============================================================

def extract_iframes(
    page_url,
    html
):

    result = []

    try:

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        for iframe in soup.find_all(
            "iframe"
        ):

            for key in (
                "src",
                "data-src",
                "data-url",
            ):

                value = iframe.get(
                    key
                )

                if not value:
                    continue

                url = make_url(
                    page_url,
                    value
                )

                if (
                    url
                    and url not in result
                ):

                    result.append(
                        url
                    )

    except Exception:
        pass

    return result


# ============================================================
# script
# ============================================================

def extract_scripts(
    page_url,
    html
):

    result = []

    try:

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        for script in soup.find_all(
            "script"
        ):

            src = (
                script.get("src")
                or script.get("data-src")
                or ""
            )

            if not src:
                continue

            url = make_url(
                page_url,
                src
            )

            if (
                url
                and url not in result
            ):

                result.append(
                    url
                )

    except Exception:
        pass

    return result


# ============================================================
# 모든 링크
# ============================================================

def extract_links(
    page_url,
    html
):

    result = []

    try:

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        for tag in soup.find_all(
            "a"
        ):

            href = (
                tag.get("href")
                or ""
            ).strip()

            if not href:
                continue

            url = make_url(
                page_url,
                href
            )

            if (
                url
                and url not in result
            ):

                result.append(
                    url
                )

    except Exception:
        pass

    return result


# ============================================================
# API 후보
# ============================================================

def extract_api_candidates(
    page_url,
    html
):

    result = []

    patterns = [

        # url: "..."
        r'(?:url|api|endpoint|apiUrl|ajaxUrl)'
        r'\s*[:=]\s*["\']([^"\']+)["\']',

        # $.get("...")
        r'(?:get|post|ajax)'
        r'\s*\(\s*["\']([^"\']+)["\']',

        # .json
        r'["\']([^"\']+\.json'
        r'(?:\?[^"\']*)?)["\']',

        # .ashx
        r'["\']([^"\']+\.ashx'
        r'(?:\?[^"\']*)?)["\']',

        # ajax
        r'["\']([^"\']*ajax[^"\']*)["\']',

        # api
        r'["\']([^"\']*api[^"\']*)["\']',

        # odds
        r'["\']([^"\']*odds[^"\']*)["\']',

        # match
        r'["\']([^"\']*match[^"\']*)["\']',

        # fixture
        r'["\']([^"\']*fixture[^"\']*)["\']',

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                html,
                re.I
            )

        except Exception:

            continue

        for value in found:

            value = str(
                value
            ).strip()

            if not value:
                continue

            if len(value) > 1200:
                continue

            url = make_url(
                page_url,
                value
            )

            if not url:
                continue

            low = url.lower()

            keywords = (
                "ajax",
                "api",
                "json",
                "ashx",
                "odds",
                "match",
                "fixture",
                "schedule",
                "score",
                "event",
                "game",
            )

            if not any(
                x in low
                for x in keywords
            ):
                continue

            if url not in result:

                result.append(
                    url
                )

    return result


# ============================================================
# 경기 ID
# ============================================================

def extract_match_ids(
    text
):

    result = set()

    patterns = [

        r'[?&](?:id|sid|mid|fid|gid|matchid)'
        r'=(\d{4,12})',

        r'(?:matchid|match_id)'
        r'\s*[:=]\s*["\']?'
        r'(\d{4,12})',

        r'(?:gameid|game_id)'
        r'\s*[:=]\s*["\']?'
        r'(\d{4,12})',

        r'(?:eventid|event_id)'
        r'\s*[:=]\s*["\']?'
        r'(\d{4,12})',

        r'(?:scheduleid|schedule_id)'
        r'\s*[:=]\s*["\']?'
        r'(\d{4,12})',

        r'data-(?:id|match-id|game-id)'
        r'\s*=\s*["\'](\d{4,12})',

        r'/(\d{5,12})'
        r'(?:\.shtml|\.html|\.aspx)',

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I
            )

        except Exception:
            continue

        for item in found:

            try:

                n = int(item)

                if (
                    1000
                    <= n
                    <= 999999999999
                ):

                    result.add(
                        str(n)
                    )

            except Exception:
                pass

    return sorted(
        result,
        key=lambda x: int(x)
    )


# ============================================================
# 팀명
# ============================================================

def extract_teams(
    text
):

    result = []

    patterns = [

        (
            r'"homeTeam"\s*:\s*"([^"]+)"'
            r'.{0,1500}?'
            r'"awayTeam"\s*:\s*"([^"]+)"'
        ),

        (
            r'"home_team"\s*:\s*"([^"]+)"'
            r'.{0,1500}?'
            r'"away_team"\s*:\s*"([^"]+)"'
        ),

        (
            r'"homeName"\s*:\s*"([^"]+)"'
            r'.{0,1500}?'
            r'"awayName"\s*:\s*"([^"]+)"'
        ),

        (
            r'"HomeTeam"\s*:\s*"([^"]+)"'
            r'.{0,1500}?'
            r'"AwayTeam"\s*:\s*"([^"]+)"'
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
            continue

        for pair in found:

            if len(pair) != 2:
                continue

            home = clean_text(
                pair[0]
            )

            away = clean_text(
                pair[1]
            )

            if (
                home
                and away
            ):

                value = (
                    home,
                    away
                )

                if value not in result:

                    result.append(
                        value
                    )

    return result


# ============================================================
# 스코어
# ============================================================

def extract_scores(
    text
):

    result = []

    patterns = [

        (
            r'"homeScore"\s*:\s*'
            r'["\']?(\d{1,3})'
        ),

        (
            r'"awayScore"\s*:\s*'
            r'["\']?(\d{1,3})'
        ),

    ]

    homes = []
    aways = []

    try:

        homes = re.findall(
            patterns[0],
            text,
            re.I
        )

        aways = re.findall(
            patterns[1],
            text,
            re.I
        )

    except Exception:
        pass

    count = min(
        len(homes),
        len(aways)
    )

    for i in range(
        count
    ):

        try:

            result.append(
                (
                    int(homes[i]),
                    int(aways[i])
                )
            )

        except Exception:
            pass

    # 일반 스코어
    try:

        found = re.findall(
            r'\b(\d{1,2})\s*[-:]\s*(\d{1,2})\b',
            text
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

                value = (
                    home,
                    away
                )

                if value not in result:

                    result.append(
                        value
                    )

    except Exception:
        pass

    return result


# ============================================================
# 1X2 배당
# ============================================================

def extract_odds(
    text
):

    result = []

    patterns = [

        (
            r'"home"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,800}?'
            r'"draw"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,800}?'
            r'"away"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
        ),

        (
            r'"homeOdds"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,800}?'
            r'"drawOdds"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,800}?'
            r'"awayOdds"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
        ),

        (
            r'"odds1"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,800}?'
            r'"oddsX"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,800}?'
            r'"odds2"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
        ),

        (
            r'"1"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,500}?'
            r'"X"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,500}?'
            r'"2"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
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
            continue

        for item in found:

            if len(item) != 3:
                continue

            h = number(
                item[0]
            )

            d = number(
                item[1]
            )

            a = number(
                item[2]
            )

            if (
                h
                and d
                and a
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
# API 검사
# ============================================================

def inspect_url(
    url,
    referer=None
):

    result = {

        "url": url,

        "status": 0,

        "bytes": 0,

        "content_type": "",

        "ids": [],

        "teams": [],

        "scores": [],

        "odds": [],

        "score": 0,

        "preview": "",

    }

    response = get(
        url,
        referer=referer,
        timeout=8
    )

    if response is None:
        return result

    text = response.text

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

    result[
        "ids"
    ] = extract_match_ids(
        text
    )

    result[
        "teams"
    ] = extract_teams(
        text
    )

    result[
        "scores"
    ] = extract_scores(
        text
    )

    result[
        "odds"
    ] = extract_odds(
        text
    )

    # --------------------------------------------------------
    # API 점수
    # --------------------------------------------------------

    score = 0

    if result["status"] == 200:
        score += 2

    if result["bytes"] > 500:
        score += 1

    if result["ids"]:
        score += min(
            5,
            len(result["ids"])
        )

    if result["teams"]:
        score += 5

    if result["scores"]:
        score += 3

    if result["odds"]:
        score += 6

    low = text.lower()

    for key in (
        "soccer",
        "football",
        "home",
        "away",
        "match",
        "fixture",
        "odds",
    ):

        if key in low:
            score += 1

    result[
        "score"
    ] = score

    preview = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    result[
        "preview"
    ] = preview[:600]

    return result


# ============================================================
# 실제 7M 시작 페이지
# ============================================================

def root_candidates():

    return [

        "https://data.7msport.com/",

        "https://live.7msport.com/",

        "https://www.7msport.com/",

        "https://kr.7msport.com/",

        "https://kr2.7msport.com/",

    ]


# ============================================================
# 날짜 관련 페이지
# ============================================================

def date_candidates(
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

    return [

        f"{LIVE_URL}/default_odds_en.aspx",

        f"{LIVE_URL}/default_odds_kr.aspx",

        f"{LIVE_URL}/default_en.aspx",

        f"{LIVE_URL}/default_kr.aspx",

        f"{KR_URL}/default_odds_en.aspx",

        f"{KR_URL}/default_odds_kr.aspx",

        f"{KR2_URL}/default_odds_en.aspx",

        f"{KR2_URL}/default_odds_kr.aspx",

        f"{BASE_URL}/",

        f"{BASE_URL}/matches_data/",

    ]


# ============================================================
# 페이지 자동 선택
# ============================================================

def find_start_page(
    date_string,
    callback=None
):

    best = None

    for url in date_candidates(
        date_string
    ):

        response = get(
            url,
            timeout=10
        )

        if response is None:
            continue

        if response.status_code != 200:
            continue

        if len(
            response.content
        ) < 1000:
            continue

        html = response.text

        ids = extract_match_ids(
            html
        )

        teams = extract_teams(
            html
        )

        iframes = extract_iframes(
            response.url,
            html
        )

        scripts = extract_scripts(
            response.url,
            html
        )

        score = (

            len(ids) * 3

            + len(teams) * 5

            + len(iframes) * 4

            + len(scripts)

        )

        if best is None or score > best["score"]:

            best = {

                "url":
                    response.url,

                "html":
                    html,

                "score":
                    score,

                "ids":
                    ids,

                "teams":
                    teams,

                "iframes":
                    iframes,

                "scripts":
                    scripts,

            }

    return best


# ============================================================
# 상세 페이지 후보
# ============================================================

def match_detail_candidates(
    match_id
):

    return [

        f"{BASE_URL}/match_data/{match_id}",

        f"{BASE_URL}/match/{match_id}",

        f"{BASE_URL}/match.shtml?id={match_id}",

        f"{BASE_URL}/odds.shtml?id={match_id}",

        f"{BASE_URL}/result.shtml?id={match_id}",

        f"{LIVE_URL}/match_data.aspx?id={match_id}",

        f"{LIVE_URL}/match.aspx?id={match_id}",

        f"{LIVE_URL}/match_data.shtml?id={match_id}",

    ]


# ============================================================
# 경기 상세 검색
# ============================================================

def get_match_detail(
    match_id,
    referer=None
):

    best = None

    for url in match_detail_candidates(
        match_id
    ):

        result = inspect_url(
            url,
            referer=referer
        )

        if result["status"] != 200:
            continue

        if (
            not result["teams"]
            and not result["scores"]
            and not result["odds"]
        ):
            continue

        if (
            best is None
            or result["score"]
            > best["score"]
        ):

            best = result

    return best


# ============================================================
# 7M 진단
# ============================================================

def diagnose(
    date_string,
    cid="",
    log_callback=None
):

    date_string = normalize_date(
        date_string
    )

    output = {

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

        "best_api":
            "",

    }

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
        "🔎 7M 자동 구조 진단"
    )

    log(
        log_callback,
        f"날짜: {date_string}"
    )

    log(
        log_callback,
        "=========================================="
    )

    # --------------------------------------------------------
    # 시작 페이지
    # --------------------------------------------------------

    page = find_start_page(
        date_string,
        callback=log_callback
    )

    if page is None:

        log(
            log_callback,
            "❌ 7M 페이지를 찾지 못했습니다."
        )

        return output

    page_url = page["url"]
    html = page["html"]

    output[
        "http"
    ] = 200

    output[
        "page_url"
    ] = page_url

    output[
        "html_bytes"
    ] = len(
        html.encode(
            errors="ignore"
        )
    )

    log(
        log_callback,
        f"페이지: {page_url}"
    )

    log(
        log_callback,
        f"HTTP: 200"
    )

    log(
        log_callback,
        f"HTML: {output['html_bytes']:,}"
    )

    # --------------------------------------------------------
    # iframe
    # --------------------------------------------------------

    iframe_urls = list(
        page["iframes"]
    )

    # iframe 내부도 탐색
    for iframe_url in iframe_urls[:10]:

        response = get(
            iframe_url,
            referer=page_url,
            timeout=10
        )

        if response is None:
            continue

        if response.status_code != 200:
            continue

        inner = response.text

        inner_iframes = extract_iframes(
            response.url,
            inner
        )

        for url in inner_iframes:

            if url not in iframe_urls:

                iframe_urls.append(
                    url
                )

    output[
        "iframe_urls"
    ] = iframe_urls

    output[
        "iframes"
    ] = len(
        iframe_urls
    )

    log(
        log_callback,
        f"iframe: {len(iframe_urls)}"
    )

    for i, url in enumerate(
        iframe_urls[:20],
        1
    ):

        log(
            log_callback,
            f"IFRAME {i}: {url}"
        )

    # --------------------------------------------------------
    # script
    # --------------------------------------------------------

    script_urls = list(
        page["scripts"]
    )

    # iframe JS도 추가
    for iframe_url in iframe_urls[:10]:

        response = get(
            iframe_url,
            referer=page_url,
            timeout=8
        )

        if response is None:
            continue

        inner_scripts = extract_scripts(
            response.url,
            response.text
        )

        for url in inner_scripts:

            if url not in script_urls:

                script_urls.append(
                    url
                )

    output[
        "script_urls"
    ] = script_urls

    output[
        "scripts"
    ] = len(
        script_urls
    )

    log(
        log_callback,
        f"script: {len(script_urls)}"
    )

    # --------------------------------------------------------
    # JS 읽기
    # --------------------------------------------------------

    all_js = ""

    for script_url in script_urls[:30]:

        response = get(
            script_url,
            referer=page_url,
            timeout=8
        )

        if response is None:
            continue

        if response.status_code != 200:
            continue

        all_js += "\n" + response.text

    output[
        "js_bytes"
    ] = len(
        all_js.encode(
            errors="ignore"
        )
    )

    log(
        log_callback,
        f"JS: {output['js_bytes']:,}"
    )

    # --------------------------------------------------------
    # API 후보
    # --------------------------------------------------------

    api_urls = []

    for source_url, source_text in [

        (
            page_url,
            html
        ),

        (
            page_url,
            all_js
        ),

    ]:

        found = extract_api_candidates(
            source_url,
            source_text
        )

        for url in found:

            if url not in api_urls:

                api_urls.append(
                    url
                )

    # iframe HTML
    for iframe_url in iframe_urls[:10]:

        response = get(
            iframe_url,
            referer=page_url,
            timeout=8
        )

        if response is None:
            continue

        found = extract_api_candidates(
            response.url,
            response.text
        )

        for url in found:

            if url not in api_urls:

                api_urls.append(
                    url
                )

    output[
        "api_urls"
    ] = api_urls

    output[
        "apis"
    ] = len(
        api_urls
    )

    log(
        log_callback,
        ""
    )

    log(
        log_callback,
        f"📡 API 후보: {len(api_urls)}"
    )

    # --------------------------------------------------------
    # API 자동 검사
    # --------------------------------------------------------

    api_results = []

    # 너무 많은 후보를 한 번에 요청하지 않음
    check_list = api_urls[:100]

    log(
        log_callback,
        f"API 자동검사: {len(check_list)}개"
    )

    for index, api_url in enumerate(
        check_list,
        1
    ):

        result = inspect_url(
            api_url,
            referer=page_url
        )

        if result["status"] != 200:
            continue

        # 의미 있는 API만 저장
        if (
            result["ids"]
            or result["teams"]
            or result["odds"]
            or result["scores"]
        ):

            api_results.append(
                result
            )

            log(
                log_callback,
                (
                    f"API 발견 "
                    f"{len(api_results)} | "
                    f"점수={result['score']} | "
                    f"ID={len(result['ids'])} | "
                    f"팀={len(result['teams'])} | "
                    f"배당={len(result['odds'])} | "
                    f"{api_url}"
                )
            )

    # --------------------------------------------------------
    # 높은 점수 API 순
    # --------------------------------------------------------

    api_results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    output[
        "api_details"
    ] = api_results

    if api_results:

        best = api_results[0]

        output[
            "best_api"
        ] = best["url"]

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
            "🏆 최적 경기 API"
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

    # --------------------------------------------------------
    # 경기 ID
    # --------------------------------------------------------

    match_ids = set(
        page["ids"]
    )

    for result in api_results:

        for match_id in result["ids"]:

            match_ids.add(
                match_id
            )

    # 경기 링크
    match_urls = []

    for url in extract_links(
        page_url,
        html
    ):

        low = url.lower()

        if any(
            key in low
            for key in (
                "match",
                "fixture",
                "odds",
                "result",
                "game",
                "detail",
            )
        ):

            if url not in match_urls:

                match_urls.append(
                    url
                )

            ids = extract_match_ids(
                url
            )

            for match_id in ids:

                match_ids.add(
                    match_id
                )

    output[
        "match_urls"
    ] = match_urls

    output[
        "match_ids"
    ] = sorted(
        match_ids,
        key=lambda x: int(x)
    )

    output[
        "match_candidates"
    ] = len(
        output["match_ids"]
    )

    # --------------------------------------------------------
    # 배당
    # --------------------------------------------------------

    odds_count = 0

    for result in api_results:

        odds_count += len(
            result["odds"]
        )

    output[
        "odds_candidates"
    ] = odds_count

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
        f"HTTP: {output['http']}"
    )

    log(
        log_callback,
        f"HTML: {output['html_bytes']:,}"
    )

    log(
        log_callback,
        f"JS: {output['js_bytes']:,}"
    )

    log(
        log_callback,
        f"iframe: {output['iframes']}"
    )

    log(
        log_callback,
        f"script: {output['scripts']}"
    )

    log(
        log_callback,
        f"API 후보: {output['apis']}"
    )

    log(
        log_callback,
        f"실제 데이터 API: {len(api_results)}"
    )

    log(
        log_callback,
        f"경기 ID: {output['match_candidates']}"
    )

    log(
        log_callback,
        f"배당 후보: {output['odds_candidates']}"
    )

    log(
        log_callback,
        "=========================================="
    )

    return output


# ============================================================
# 경기 1개 수집
# ============================================================

def collect_match(
    match_id,
    date_string,
    referer=None,
    retry_count=3,
    retry_delay=1.0,
    log_callback=None
):

    best = None

    for attempt in range(
        retry_count + 1
    ):

        detail = get_match_detail(
            match_id,
            referer=referer
        )

        if detail is not None:

            if (
                best is None
                or detail["score"]
                > best["score"]
            ):

                best = detail

            if (
                detail["teams"]
                or detail["odds"]
            ):

                break

        if attempt < retry_count:

            time.sleep(
                retry_delay
            )

    if best is None:
        return None

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
            "",

        "url":
            best["url"],

    }

    if best["teams"]:

        item[
            "home_team"
        ] = best["teams"][0][0]

        item[
            "away_team"
        ] = best["teams"][0][1]

    if best["scores"]:

        home = best[
            "scores"
        ][0][0]

        away = best[
            "scores"
        ][0][1]

        item[
            "home_score"
        ] = home

        item[
            "away_score"
        ] = away

        item[
            "result"
        ] = result_from_score(
            home,
            away
        )

    # --------------------------------------------------------
    # 최종 배당
    # --------------------------------------------------------

    if best["odds"]:

        odds = best[
            "odds"
        ][-1]

        item[
            "home_odds"
        ] = odds[0]

        item[
            "draw_odds"
        ] = odds[1]

        item[
            "away_odds"
        ] = odds[2]

    if (
        not item["home_team"]
        and not item["away_team"]
        and not item["home_odds"]
    ):

        return None

    return item


# ============================================================
# 날짜 수집
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

    log(
        log_callback,
        ""
    )

    log(
        log_callback,
        f"📅 {date_string} 수집 시작"
    )

    diagnosis = diagnose(
        date_string,
        cid=cid,
        log_callback=log_callback
    )

    match_ids = diagnosis.get(
        "match_ids",
        []
    )

    # 최대 500개
    match_ids = match_ids[:500]

    log(
        log_callback,
        f"🎯 수집 대상: {len(match_ids)}경기"
    )

    results = []

    for index, match_id in enumerate(
        match_ids,
        1
    ):

        log(
            log_callback,
            f"[{index}/{len(match_ids)}] "
            f"ID {match_id}"
        )

        item = collect_match(
            match_id=match_id,
            date_string=date_string,
            referer=diagnosis.get(
                "page_url"
            ),
            retry_count=retry_count,
            retry_delay=retry_delay,
            log_callback=log_callback
        )

        if item is None:

            log(
                log_callback,
                "  ❌ 데이터 없음"
            )

            continue

        results.append(
            item
        )

        log(
            log_callback,
            (
                f"  ✅ "
                f"{item['home_team']} "
                f"vs "
                f"{item['away_team']} | "
                f"{item['home_odds']} / "
                f"{item['draw_odds']} / "
                f"{item['away_odds']} | "
                f"{item['result'] or '-'}"
            )
        )

    # 중복
    unique = {}

    for item in results:

        key = (

            item["match_id"],

            item["home_team"],

            item["away_team"],

        )

        unique[key] = item

    results = list(
        unique.values()
    )

    log(
        log_callback,
        ""
    )

    log(
        log_callback,
        f"✅ {date_string} 수집 완료: "
        f"{len(results)}경기"
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

        try:

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

        except Exception as e:

            log(
                log_callback,
                f"❌ {date_string}: {e}"
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

    odds_count = 0
    result_count = 0

    for item in all_results:

        if all(
            item.get(key) is not None
            for key in (
                "home_odds",
                "draw_odds",
                "away_odds",
            )
        ):

            odds_count += 1

        if item.get(
            "result"
        ):

            result_count += 1

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
        "🏁 7M 수집 완료"
    )

    log(
        log_callback,
        f"DB 저장 대상 경기: {len(all_results)}"
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
# 테스트
# ============================================================

if __name__ == "__main__":

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    print(
        "7M 자동 진단 시작:",
        today
    )

    result = diagnose(
        today,
        log_callback=print
    )

    print()
    print(
        "최적 API:",
        result.get(
            "best_api"
        )
    )

    print(
        "경기 ID:",
        len(
            result.get(
                "match_ids",
                []
            )
        )
                )
