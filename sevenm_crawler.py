# ============================================================
# sevenm_crawler.py
# ⚽ 7M 축구 최종배당 수집기
#
# 기능
# - 7M 접속
# - 날짜별 페이지 탐색
# - iframe 탐색
# - script 탐색
# - API 후보 탐색
# - 경기 ID 탐색
# - 경기 상세 탐색
# - 홈 / 무 / 원정 1X2 배당 탐색
# - 실제 경기 스코어 탐색
# - 승 / 무 / 패 자동 계산
# - CID 입력 지원
# - 빠른 연결 진단
# ============================================================

import re
import html
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# 기본 설정
# ============================================================

BASE_URLS = [
    "https://kr.7msport.com",
    "https://www.7msport.com",
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
    "Connection": "keep-alive",
}

TIMEOUT = 8


# ============================================================
# 세션
# ============================================================

session = requests.Session()

session.headers.update(
    HEADERS
)


# ============================================================
# 기본 유틸
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    value = html.unescape(
        str(value)
    )

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


def safe_float(value):

    if value is None:
        return None

    try:

        value = str(
            value
        ).strip()

        value = value.replace(
            ",",
            ""
        )

        match = re.search(
            r"\d+(?:\.\d+)?",
            value
        )

        if not match:
            return None

        number = float(
            match.group(0)
        )

        if number <= 1:
            return None

        if number > 1000:
            return None

        return number

    except Exception:

        return None


def normalize_result(
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
# HTTP
# ============================================================

def get(
    url,
    timeout=TIMEOUT
):

    try:

        response = session.get(
            url,
            timeout=timeout,
            allow_redirects=True
        )

        response.encoding = (
            response.apparent_encoding
            or "utf-8"
        )

        return response

    except Exception:

        return None


# ============================================================
# 날짜 URL
# ============================================================

def build_date_urls(
    date_string
):

    urls = []

    for base in BASE_URLS:

        urls.extend([

            f"{base}/default_odds_kr.aspx",

            f"{base}/default_kr.aspx",

            f"{base}/default_en.aspx",

            f"{base}/default_odds_en.aspx",

        ])

    # 날짜 파라미터 후보
    for base in BASE_URLS:

        urls.extend([

            f"{base}/default_odds_kr.aspx"
            f"?date={date_string}",

            f"{base}/default_kr.aspx"
            f"?date={date_string}",

            f"{base}/default_odds_en.aspx"
            f"?date={date_string}",

            f"{base}/default_en.aspx"
            f"?date={date_string}",

        ])

    return list(
        dict.fromkeys(
            urls
        )
    )


# ============================================================
# iframe 찾기
# ============================================================

def find_iframes(
    page_url,
    page_html
):

    result = []

    try:

        soup = BeautifulSoup(
            page_html,
            "html.parser"
        )

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

            full_url = urljoin(
                page_url,
                src
            )

            if full_url not in result:

                result.append(
                    full_url
                )

    except Exception:

        pass

    return result


# ============================================================
# script 찾기
# ============================================================

def find_scripts(
    page_url,
    page_html
):

    result = []

    try:

        soup = BeautifulSoup(
            page_html,
            "html.parser"
        )

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

            full_url = urljoin(
                page_url,
                src
            )

            if full_url not in result:

                result.append(
                    full_url
                )

    except Exception:

        pass

    return result


# ============================================================
# API 후보
# ============================================================

def find_api_candidates(
    text,
    base_url
):

    result = []

    patterns = [

        r'["\']([^"\']*(?:ajax|api|odds|match|score|fixture)[^"\']*)["\']',

        r'["\']([^"\']+\.ashx[^"\']*)["\']',

        r'["\']([^"\']+\.json[^"\']*)["\']',

        r'["\']([^"\']+\.aspx[^"\']*)["\']',

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I
            )

            for value in found:

                value = html.unescape(
                    str(value)
                ).strip()

                if not value:
                    continue

                if len(value) > 500:
                    continue

                full_url = urljoin(
                    base_url,
                    value
                )

                low = full_url.lower()

                keywords = [
                    "ajax",
                    "api",
                    "odds",
                    "match",
                    "score",
                    "fixture",
                    "ashx",
                    "json",
                ]

                if any(
                    x in low
                    for x in keywords
                ):

                    if full_url not in result:

                        result.append(
                            full_url
                        )

        except Exception:

            continue

    return result


# ============================================================
# 경기 ID 찾기
# ============================================================

def find_match_ids(
    text
):

    ids = set()

    patterns = [

        r'(?:matchid|match_id)'
        r'\s*[=:]\s*["\']?'
        r'(\d{4,12})',

        r'(?:gameid|game_id)'
        r'\s*[=:]\s*["\']?'
        r'(\d{4,12})',

        r'(?:eventid|event_id)'
        r'\s*[=:]\s*["\']?'
        r'(\d{4,12})',

        r'(?:scheduleid|schedule_id)'
        r'\s*[=:]\s*["\']?'
        r'(\d{4,12})',

        r'[?&]id=(\d{4,12})',

        r'(?:fid|sid|mid)'
        r'\s*[=:]\s*["\']?'
        r'(\d{4,12})',

        r'data-(?:id|match-id|game-id)'
        r'=["\'](\d{4,12})',

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I
            )

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

                    continue

        except Exception:

            continue

    return sorted(
        ids,
        key=lambda x: int(x)
    )


# ============================================================
# 팀 이름
# ============================================================

def extract_team_pairs(
    text
):

    result = []

    patterns = [

        r'(?:homeTeam|home_team)'
        r'\s*[=:]\s*'
        r'["\']([^"\']{1,100})["\']'
        r'.{0,1000}?'
        r'(?:awayTeam|away_team)'
        r'\s*[=:]\s*'
        r'["\']([^"\']{1,100})["\']',

        r'(?:homeName|home_name)'
        r'\s*[=:]\s*'
        r'["\']([^"\']{1,100})["\']'
        r'.{0,1000}?'
        r'(?:awayName|away_name)'
        r'\s*[=:]\s*'
        r'["\']([^"\']{1,100})["\']',

        r'([A-Za-z가-힣0-9][^<>\r\n]{1,80})'
        r'\s+VS\s+'
        r'([A-Za-z가-힣0-9][^<>\r\n]{1,80})',

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I | re.S
            )

            for item in found:

                if not isinstance(
                    item,
                    tuple
                ):
                    continue

                if len(item) != 2:
                    continue

                home = clean_text(
                    item[0]
                )

                away = clean_text(
                    item[1]
                )

                if (
                    not home
                    or not away
                ):
                    continue

                if (
                    len(home) > 100
                    or len(away) > 100
                ):
                    continue

                pair = (
                    home,
                    away
                )

                if pair not in result:

                    result.append(
                        pair
                    )

        except Exception:

            continue

    return result


# ============================================================
# 스코어
# ============================================================

def extract_scores(
    text
):

    result = []

    patterns = [

        r'(?:homeScore|home_score|homescore)'
        r'\s*[=:]\s*["\']?(\d+)["\']?'
        r'.{0,500}?'
        r'(?:awayScore|away_score|awayscore)'
        r'\s*[=:]\s*["\']?(\d+)["\']?',

        r'(\d+)\s*-\s*(\d+)',

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I | re.S
            )

            for item in found:

                if not isinstance(
                    item,
                    tuple
                ):
                    continue

                if len(item) != 2:
                    continue

                home = int(
                    item[0]
                )

                away = int(
                    item[1]
                )

                if (
                    home > 30
                    or away > 30
                ):
                    continue

                result.append(
                    (
                        home,
                        away
                    )
                )

        except Exception:

            continue

    return result


# ============================================================
# 1X2 최종배당
# ============================================================

def extract_1x2_odds(
    text
):

    result = []

    patterns = [

        # home / draw / away
        r'"home"\s*:\s*'
        r'([0-9]+(?:\.[0-9]+)?)'
        r'.{0,500}?'
        r'"draw"\s*:\s*'
        r'([0-9]+(?:\.[0-9]+)?)'
        r'.{0,500}?'
        r'"away"\s*:\s*'
        r'([0-9]+(?:\.[0-9]+)?)',

        # homeOdds / drawOdds / awayOdds
        r'"homeOdds"\s*:\s*'
        r'([0-9]+(?:\.[0-9]+)?)'
        r'.{0,500}?'
        r'"drawOdds"\s*:\s*'
        r'([0-9]+(?:\.[0-9]+)?)'
        r'.{0,500}?'
        r'"awayOdds"\s*:\s*'
        r'([0-9]+(?:\.[0-9]+)?)',

        # odds1 / oddsX / odds2
        r'"odds1"\s*:\s*'
        r'([0-9]+(?:\.[0-9]+)?)'
        r'.{0,500}?'
        r'"oddsX"\s*:\s*'
        r'([0-9]+(?:\.[0-9]+)?)'
        r'.{0,500}?'
        r'"odds2"\s*:\s*'
        r'([0-9]+(?:\.[0-9]+)?)',

        # 3개 숫자 배열
        r'\[\s*'
        r'([0-9]+\.[0-9]+)'
        r'\s*,\s*'
        r'([0-9]+\.[0-9]+)'
        r'\s*,\s*'
        r'([0-9]+\.[0-9]+)'
        r'\s*\]',

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I | re.S
            )

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

        except Exception:

            continue

    return result


# ============================================================
# 페이지 분석
# ============================================================

def inspect_page(
    url,
    log_callback=None,
    deep=False
):

    def log(message):

        if log_callback:

            log_callback(
                message
            )

    response = get(
        url
    )

    if response is None:

        log(
            f"접속 실패: {url}"
        )

        return {
            "url": url,
            "status": 0,
            "html": "",
            "iframes": [],
            "scripts": [],
            "apis": [],
            "match_ids": [],
            "teams": [],
            "odds": [],
        }

    text = response.text

    log(
        f"HTTP {response.status_code} | "
        f"{len(text):,} bytes"
    )

    result = {

        "url": url,

        "status":
            response.status_code,

        "html":
            text,

        "iframes":
            [],

        "scripts":
            [],

        "apis":
            [],

        "match_ids":
            find_match_ids(
                text
            ),

        "teams":
            extract_team_pairs(
                text
            ),

        "odds":
            extract_1x2_odds(
                text
            ),
    }

    if response.status_code != 200:

        return result

    # iframe
    result["iframes"] = (
        find_iframes(
            url,
            text
        )
    )

    # script
    result["scripts"] = (
        find_scripts(
            url,
            text
        )
    )

    # API
    result["apis"] = (
        find_api_candidates(
            text,
            url
        )
    )

    # 깊은 분석은 필요한 경우만
    if deep:

        # iframe 최대 5개
        for iframe_url in result[
            "iframes"
        ][:5]:

            iframe_response = get(
                iframe_url,
                timeout=5
            )

            if iframe_response is None:
                continue

            iframe_text = (
                iframe_response.text
            )

            result[
                "match_ids"
            ].extend(
                find_match_ids(
                    iframe_text
                )
            )

            result[
                "teams"
            ].extend(
                extract_team_pairs(
                    iframe_text
                )
            )

            result[
                "odds"
            ].extend(
                extract_1x2_odds(
                    iframe_text
                )
            )

            result[
                "apis"
            ].extend(
                find_api_candidates(
                    iframe_text,
                    iframe_url
                )
            )

    # 중복 제거
    result[
        "match_ids"
    ] = sorted(
        set(
            result["match_ids"]
        ),
        key=lambda x: int(x)
    )

    result[
        "apis"
    ] = list(
        dict.fromkeys(
            result["apis"]
        )
    )

    return result


# ============================================================
# 빠른 연결 진단
# ============================================================

def diagnose(
    date_string,
    cid="",
    log_callback=None
):

    def log(message):

        if log_callback:

            log_callback(
                message
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

        "pages":
            0,
    }

    log("=" * 50)

    log(
        "7M 빠른 연결 진단 시작"
    )

    log(
        f"진단 날짜: {date_string}"
    )

    log("=" * 50)

    # --------------------------------------------------------
    # 기본 주소만 빠르게 검사
    # --------------------------------------------------------

    test_urls = [

        "https://kr.7msport.com/default_odds_kr.aspx",

        "https://kr.7msport.com/default_kr.aspx",

        "https://www.7msport.com/default_en.aspx",

    ]

    response = None

    page_url = ""

    for url in test_urls:

        log(
            f"접속 확인: {url}"
        )

        try:

            r = session.get(
                url,
                timeout=8,
                allow_redirects=True
            )

            if r.status_code == 200:

                response = r

                page_url = r.url

                log(
                    f"HTTP 200 성공: {r.url}"
                )

                break

            log(
                f"HTTP {r.status_code}"
            )

        except Exception as e:

            log(
                "접속 실패: "
                + str(e)[:100]
            )

    if response is None:

        log(
            "7M 접속에 실패했습니다."
        )

        return result

    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------

    text = response.text

    result[
        "http"
    ] = response.status_code

    result[
        "html_bytes"
    ] = len(text)

    result[
        "pages"
    ] = 1

    log(
        f"HTML: {len(text):,} bytes"
    )

    # --------------------------------------------------------
    # BeautifulSoup
    # --------------------------------------------------------

    try:

        soup = BeautifulSoup(
            text,
            "html.parser"
        )

    except Exception as e:

        log(
            f"HTML 분석 실패: {e}"
        )

        return result

    # --------------------------------------------------------
    # iframe
    # --------------------------------------------------------

    try:

        iframe_tags = (
            soup.find_all(
                "iframe"
            )
        )

        result[
            "iframes"
        ] = len(
            iframe_tags
        )

        log(
            f"iframe: "
            f"{len(iframe_tags)}"
        )

    except Exception:

        pass

    # --------------------------------------------------------
    # script
    # --------------------------------------------------------

    try:

        script_tags = (
            soup.find_all(
                "script"
            )
        )

        result[
            "scripts"
        ] = len(
            script_tags
        )

        log(
            f"script: "
            f"{len(script_tags)}"
        )

        # 처음 5개만 확인
        js_total = 0

        for tag in script_tags[:5]:

            src = (
                tag.get(
                    "src"
                )
                or ""
            ).strip()

            if not src:
                continue

            js_url = urljoin(
                page_url,
                src
            )

            try:

                js_response = (
                    session.get(
                        js_url,
                        timeout=4
                    )
                )

                if (
                    js_response.status_code
                    == 200
                ):

                    js_total += len(
                        js_response.text
                    )

            except Exception:

                continue

        result[
            "js_bytes"
        ] = js_total

        log(
            f"JS 확인: "
            f"{js_total:,} bytes"
        )

    except Exception as e:

        log(
            f"JS 분석 실패: {e}"
        )

    # --------------------------------------------------------
    # 경기 ID
    # --------------------------------------------------------

    try:

        ids = find_match_ids(
            text
        )

        result[
            "match_candidates"
        ] = len(ids)

        log(
            f"경기 ID 후보: "
            f"{len(ids)}"
        )

    except Exception as e:

        log(
            f"경기 ID 분석 실패: {e}"
        )

    # --------------------------------------------------------
    # 배당
    # --------------------------------------------------------

    try:

        odds = extract_1x2_odds(
            text
        )

        result[
            "odds_candidates"
        ] = len(
            odds
        )

        log(
            f"1X2 배당 후보: "
            f"{len(odds)}"
        )

    except Exception as e:

        log(
            f"배당 분석 실패: {e}"
        )

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    try:

        apis = find_api_candidates(
            text,
            page_url
        )

        result[
            "apis"
        ] = len(
            apis
        )

        log(
            f"API 후보: "
            f"{len(apis)}"
        )

    except Exception as e:

        log(
            f"API 분석 실패: {e}"
        )

    log("=" * 50)

    log(
        "7M 빠른 연결 진단 완료"
    )

    log("=" * 50)

    return result


# ============================================================
# 날짜별 경기 ID 수집
# ============================================================

def collect_date(
    date_string,
    cid="",
    retry_count=3,
    retry_delay=1.0,
    log_callback=None
):

    def log(message):

        if log_callback:

            log_callback(
                message
            )

    result = {

        "date":
            date_string,

        "ids":
            [],

        "odds":
            [],

        "pages":
            [],

        "apis":
            [],
    }

    log("=" * 50)

    log(
        f"7M 경기 탐색: {date_string}"
    )

    log("=" * 50)

    urls = build_date_urls(
        date_string
    )

    all_ids = set()
    all_odds = []
    all_apis = []

    # 너무 많은 주소를 돌지 않음
    for url in urls[:6]:

        found_page = None

        for attempt in range(
            retry_count + 1
        ):

            data = inspect_page(
                url,
                log_callback=log,
                deep=False
            )

            result[
                "pages"
            ].append(
                data
            )

            if data.get(
                "match_ids"
            ):

                found_page = data

                break

            if attempt < retry_count:

                log(
                    f"경기 후보 없음 "
                    f"재시도 "
                    f"{attempt + 1}/"
                    f"{retry_count}"
                )

                time.sleep(
                    retry_delay
                )

        if found_page is None:
            continue

        for match_id in (
            found_page.get(
                "match_ids",
                []
            )
        ):

            all_ids.add(
                match_id
            )

        all_odds.extend(
            found_page.get(
                "odds",
                []
            )
        )

        all_apis.extend(
            found_page.get(
                "apis",
                []
            )
        )

        if all_ids:

            break

    result[
        "ids"
    ] = sorted(
        all_ids,
        key=lambda x: int(x)
    )

    result[
        "odds"
    ] = all_odds

    result[
        "apis"
    ] = list(
        dict.fromkeys(
            all_apis
        )
    )

    log(
        f"발견 경기 ID: "
        f"{len(result['ids'])}"
    )

    log(
        f"발견 API: "
        f"{len(result['apis'])}"
    )

    return result


# ============================================================
# 경기 상세 URL
# ============================================================

def build_match_urls(
    match_id
):

    urls = []

    for base in BASE_URLS:

        urls.extend([

            f"{base}/match/{match_id}",

            f"{base}/match/{match_id}.html",

            f"{base}/match/{match_id}.aspx",

            f"{base}/soccer/{match_id}",

            f"{base}/soccer/{match_id}.html",

            f"{base}/soccer/{match_id}.aspx",

            f"{base}/matchdata.aspx"
            f"?id={match_id}",

            f"{base}/match_detail.aspx"
            f"?id={match_id}",

            f"{base}/odds.aspx"
            f"?id={match_id}",

            f"{base}/odds_detail.aspx"
            f"?id={match_id}",

        ])

    return list(
        dict.fromkeys(
            urls
        )
    )


# ============================================================
# 경기 상세 수집
# ============================================================

def collect_match(
    match_id,
    cid="",
    retry_count=3,
    retry_delay=1.0,
    log_callback=None
):

    def log(message):

        if log_callback:

            log_callback(
                message
            )

    result = {

        "match_id":
            str(match_id),

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

        "cid":
            cid,

        "url":
            "",
    }

    urls = build_match_urls(
        match_id
    )

    for url in urls:

        response = get(
            url
        )

        if response is None:
            continue

        if response.status_code != 200:
            continue

        text = response.text

        teams = extract_team_pairs(
            text
        )

        scores = extract_scores(
            text
        )

        odds = extract_1x2_odds(
            text
        )

        if teams:

            result[
                "home_team"
            ] = teams[0][0]

            result[
                "away_team"
            ] = teams[0][1]

        if scores:

            result[
                "home_score"
            ] = scores[0][0]

            result[
                "away_score"
            ] = scores[0][1]

            result[
                "result"
            ] = normalize_result(

                scores[0][0],

                scores[0][1]
            )

        if odds:

            # 페이지에서 확인되는
            # 마지막 1X2 값을 최종 후보로 사용
            selected = odds[-1]

            result[
                "home_odds"
            ] = selected[0]

            result[
                "draw_odds"
            ] = selected[1]

            result[
                "away_odds"
            ] = selected[2]

        if (
            result["home_team"]
            or result["away_team"]
            or result["home_odds"]
        ):

            result[
                "url"
            ] = url

            log(
                f"[{match_id}] "
                f"{result['home_team']} "
                f"vs "
                f"{result['away_team']} | "
                f"{result['home_odds']} / "
                f"{result['draw_odds']} / "
                f"{result['away_odds']} | "
                f"{result['result']}"
            )

            return result

    return result


# ============================================================
# 전체 수집
# ============================================================

def collect(
    start_date,
    end_date,
    cid="",
    retry_count=3,
    retry_delay=1.0,
    log_callback=None
):

    def log(message):

        if log_callback:

            log_callback(
                message
            )

    start = datetime.strptime(
        start_date,
        "%Y-%m-%d"
    )

    end = datetime.strptime(
        end_date,
        "%Y-%m-%d"
    )

    final_matches = []

    current = start

    while current <= end:

        date_string = (
            current.strftime(
                "%Y-%m-%d"
            )
        )

        daily = collect_date(
            date_string=date_string,
            cid=cid,
            retry_count=retry_count,
            retry_delay=retry_delay,
            log_callback=log
        )

        ids = daily.get(
            "ids",
            []
        )

        log(
            f"{date_string}: "
            f"경기 ID {len(ids)}개"
        )

        # 한 날짜에 너무 많은 ID가 잡히는
        # 비정상적인 경우 무한 수집 방지
        ids = ids[:300]

        for match_id in ids:

            match = collect_match(
                match_id=match_id,
                cid=cid,
                retry_count=retry_count,
                retry_delay=retry_delay,
                log_callback=log
            )

            if (
                match.get(
                    "home_team"
                )
                or match.get(
                    "away_team"
                )
                or match.get(
                    "home_odds"
                )
            ):

                match[
                    "match_date"
                ] = date_string

                final_matches.append(
                    match
                )

        current += timedelta(
            days=1
        )

    # 중복 제거
    unique = {}

    for item in final_matches:

        key = item.get(
            "match_id"
        )

        if not key:

            key = (
                item.get(
                    "match_date"
                ),
                item.get(
                    "home_team"
                ),
                item.get(
                    "away_team"
                )
            )

        unique[key] = item

    final_matches = list(
        unique.values()
    )

    log("=" * 50)

    log(
        f"최종 수집 경기: "
        f"{len(final_matches)}"
    )

    odds_count = sum(

        1

        for item in final_matches

        if (
            item.get(
                "home_odds"
            )
            is not None
            and
            item.get(
                "draw_odds"
            )
            is not None
            and
            item.get(
                "away_odds"
            )
            is not None
        )
    )

    result_count = sum(

        1

        for item in final_matches

        if item.get(
            "result"
        )
    )

    log(
        f"1X2 배당: "
        f"{odds_count}"
    )

    log(
        f"실제 결과: "
        f"{result_count}"
    )

    log("=" * 50)

    return final_matches


# ============================================================
# 파일 단독 실행 테스트
# ============================================================

if __name__ == "__main__":

    print(
        "7M 연결 진단 시작"
    )

    data = diagnose(
        datetime.now().strftime(
            "%Y-%m-%d"
        ),
        log_callback=print
    )

    print()
    print(
        "진단 결과"
    )
    print(
        data
            )
