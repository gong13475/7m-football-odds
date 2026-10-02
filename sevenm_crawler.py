# ============================================================
# 7M 축구 최종배당 수집기
# - 7M 전용
# - iframe 자동 탐색
# - script 자동 탐색
# - 경기 ID 자동 탐색
# - 날짜별 경기 탐색
# - 1X2 최종배당 후보 탐색
# - 실제 결과 탐색
# - CID 선택 지원
# ============================================================

import re
import json
import time
import html
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# 기본 설정
# ============================================================

BASE_URLS = [
    "https://www.7msport.com",
    "https://live.7msport.com",
    "https://kr.7msport.com",
    "https://kr2.7msport.com",
    "https://live.7msport.info",
]

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 16; K) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/153.0.0.0 Mobile Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,"
        "*/*;q=0.8"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

TIMEOUT = 20


# ============================================================
# 세션
# ============================================================

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# 유틸
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = html.unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def safe_float(value):
    if value is None:
        return None

    try:
        value = str(value).strip()
        value = value.replace(",", "")
        value = value.replace("－", "-")

        m = re.search(r"-?\d+(?:\.\d+)?", value)

        if not m:
            return None

        number = float(m.group(0))

        if number <= 1.0:
            return None

        if number > 1000:
            return None

        return number

    except Exception:
        return None


def normalize_result(home_score, away_score):

    try:
        h = int(home_score)
        a = int(away_score)
    except Exception:
        return None

    if h > a:
        return "승"

    if h == a:
        return "무"

    return "패"


def get(url, params=None):

    try:
        response = session.get(
            url,
            params=params,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        response.encoding = response.apparent_encoding or "utf-8"

        return response

    except Exception:
        return None


# ============================================================
# URL 후보
# ============================================================

def build_date_urls(date_string):

    urls = []

    date_obj = datetime.strptime(
        date_string,
        "%Y-%m-%d"
    )

    y = date_obj.strftime("%Y")
    m = date_obj.strftime("%m")
    d = date_obj.strftime("%d")

    # 기본 페이지
    for base in BASE_URLS:

        urls.extend([
            f"{base}/default_en.aspx",
            f"{base}/default_kr.aspx",
            f"{base}/default_odds_en.aspx",
            f"{base}/default_odds_kr.aspx",
            f"{base}/soccer.aspx",
            f"{base}/football.aspx",
        ])

        # 날짜 관련 후보
        urls.extend([
            f"{base}/default_en.aspx?date={date_string}",
            f"{base}/default_kr.aspx?date={date_string}",
            f"{base}/default_odds_en.aspx?date={date_string}",
            f"{base}/default_odds_kr.aspx?date={date_string}",
            f"{base}/default_en.aspx?date={y}-{m}-{d}",
            f"{base}/default_kr.aspx?date={y}-{m}-{d}",
        ])

    # 중복 제거
    result = []

    for u in urls:
        if u not in result:
            result.append(u)

    return result


# ============================================================
# HTML에서 iframe 찾기
# ============================================================

def find_iframes(page_url, page_html):

    result = []

    soup = BeautifulSoup(
        page_html,
        "html.parser"
    )

    for tag in soup.find_all("iframe"):

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
            result.append(full_url)

    # HTML 안에 직접 iframe URL이 들어있는 경우
    patterns = [
        r'<iframe[^>]+src=["\']([^"\']+)',
        r'iframe[^"\']{0,100}["\']([^"\']+)',
        r'frameUrl["\']?\s*[:=]\s*["\']([^"\']+)',
        r'iframeUrl["\']?\s*[:=]\s*["\']([^"\']+)',
    ]

    for pattern in patterns:

        try:
            matches = re.findall(
                pattern,
                page_html,
                re.I
            )

            for src in matches:

                full_url = urljoin(
                    page_url,
                    src
                )

                if full_url not in result:
                    result.append(full_url)

        except Exception:
            pass

    return result


# ============================================================
# Script URL 찾기
# ============================================================

def find_scripts(page_url, page_html):

    result = []

    soup = BeautifulSoup(
        page_html,
        "html.parser"
    )

    for tag in soup.find_all("script"):

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
            result.append(full_url)

    # HTML 내부 script 문자열
    patterns = [
        r'<script[^>]+src=["\']([^"\']+)',
        r'["\']([^"\']+\.js(?:\?[^"\']*)?)["\']',
    ]

    for pattern in patterns:

        try:

            matches = re.findall(
                pattern,
                page_html,
                re.I
            )

            for src in matches:

                if ".js" not in src.lower():
                    continue

                full_url = urljoin(
                    page_url,
                    src
                )

                if full_url not in result:
                    result.append(full_url)

        except Exception:
            pass

    return result


# ============================================================
# JS / HTML에서 API URL 찾기
# ============================================================

def find_api_candidates(text, base_url):

    candidates = []

    patterns = [

        # https URL
        r'https?://[^"\']+',

        # 상대 ajax
        r'["\']([^"\']*(?:ajax|api|odds|match|score|fixture)[^"\']*)["\']',

        # .ashx
        r'["\']([^"\']+\.ashx[^"\']*)["\']',

        # .aspx
        r'["\']([^"\']+\.aspx[^"\']*)["\']',

        # json
        r'["\']([^"\']+\.json[^"\']*)["\']',
    ]

    for pattern in patterns:

        try:

            matches = re.findall(
                pattern,
                text,
                re.I
            )

            for value in matches:

                if isinstance(value, tuple):
                    value = value[0]

                value = html.unescape(
                    str(value)
                ).strip()

                if not value:
                    continue

                if len(value) > 500:
                    continue

                full = urljoin(
                    base_url,
                    value
                )

                low = full.lower()

                if any(
                    x in low
                    for x in [
                        "ajax",
                        "api",
                        "odds",
                        "match",
                        "score",
                        "fixture",
                        "soccer",
                        ".ashx",
                        ".json",
                    ]
                ):
                    if full not in candidates:
                        candidates.append(full)

        except Exception:
            pass

    return candidates


# ============================================================
# 경기 ID 찾기
# ============================================================

def find_match_ids(text):

    ids = set()

    patterns = [

        # match id
        r'(?:matchid|match_id|gameid|game_id|eventid|event_id|scheduleid|schedule_id)'
        r'\s*[=:]\s*["\']?(\d{4,12})',

        # id=123456
        r'(?:[?&]id=)(\d{4,12})',

        # match/123456
        r'(?:match|game|event|soccer)[/_-](\d{4,12})',

        # fid=123456
        r'(?:fid|sid|mid)\s*[=:]\s*["\']?(\d{4,12})',

        # data-id
        r'data-(?:id|match-id|game-id)=["\'](\d{4,12})',
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
                    number = int(value)

                    if 1000 <= number <= 999999999999:
                        ids.add(str(number))

                except Exception:
                    pass

        except Exception:
            pass

    return sorted(
        ids,
        key=lambda x: int(x)
    )


# ============================================================
# 팀 이름 후보
# ============================================================

def extract_team_pairs(text):

    pairs = []

    patterns = [

        # Home VS Away
        r'([A-Za-z가-힣0-9][^<>\r\n]{1,80})\s+VS\s+'
        r'([A-Za-z가-힣0-9][^<>\r\n]{1,80})',

        # homeTeam / awayTeam
        r'(?:homeTeam|home_team|home)\s*[=:]\s*["\']([^"\']{1,100})["\']'
        r'.{0,1000}?'
        r'(?:awayTeam|away_team|away)\s*[=:]\s*["\']([^"\']{1,100})["\']',

        # team names
        r'(?:homeName|home_name)\s*[=:]\s*["\']([^"\']{1,100})["\']'
        r'.{0,1000}?'
        r'(?:awayName|away_name)\s*[=:]\s*["\']([^"\']{1,100})["\']',
    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I | re.S
            )

            for item in found:

                if not isinstance(item, tuple):
                    continue

                if len(item) != 2:
                    continue

                home = clean_text(item[0])
                away = clean_text(item[1])

                if not home or not away:
                    continue

                if len(home) > 100 or len(away) > 100:
                    continue

                pair = (
                    home,
                    away
                )

                if pair not in pairs:
                    pairs.append(pair)

        except Exception:
            pass

    return pairs


# ============================================================
# 스코어 찾기
# ============================================================

def extract_scores(text):

    results = []

    patterns = [

        r'(?:homeScore|home_score|homescore)'
        r'\s*[=:]\s*["\']?(\d+)["\']?'
        r'.{0,300}?'
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

                if not isinstance(item, tuple):
                    continue

                if len(item) != 2:
                    continue

                h = int(item[0])
                a = int(item[1])

                if h > 30 or a > 30:
                    continue

                results.append(
                    (
                        h,
                        a
                    )
                )

        except Exception:
            pass

    return results


# ============================================================
# 1X2 배당 찾기
# ============================================================

def extract_1x2_odds(text):

    odds = []

    # JSON 형태
    json_patterns = [

        r'"home"\s*:\s*([0-9]+(?:\.[0-9]+)?)'
        r'.{0,500}?'
        r'"draw"\s*:\s*([0-9]+(?:\.[0-9]+)?)'
        r'.{0,500}?'
        r'"away"\s*:\s*([0-9]+(?:\.[0-9]+)?)',

        r'"homeOdds"\s*:\s*([0-9]+(?:\.[0-9]+)?)'
        r'.{0,500}?'
        r'"drawOdds"\s*:\s*([0-9]+(?:\.[0-9]+)?)'
        r'.{0,500}?'
        r'"awayOdds"\s*:\s*([0-9]+(?:\.[0-9]+)?)',

        r'"odds1"\s*:\s*([0-9]+(?:\.[0-9]+)?)'
        r'.{0,500}?'
        r'"oddsX"\s*:\s*([0-9]+(?:\.[0-9]+)?)'
        r'.{0,500}?'
        r'"odds2"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
    ]

    for pattern in json_patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I | re.S
            )

            for item in found:

                if len(item) != 3:
                    continue

                h = safe_float(item[0])
                d = safe_float(item[1])
                a = safe_float(item[2])

                if h and d and a:

                    odds.append(
                        (
                            h,
                            d,
                            a
                        )
                    )

        except Exception:
            pass

    # 일반 숫자 배열
    array_patterns = [
        r'\[\s*([0-9]+\.[0-9]+)\s*,\s*'
        r'([0-9]+\.[0-9]+)\s*,\s*'
        r'([0-9]+\.[0-9]+)\s*\]',

        r'\(\s*([0-9]+\.[0-9]+)\s*,\s*'
        r'([0-9]+\.[0-9]+)\s*,\s*'
        r'([0-9]+\.[0-9]+)\s*\)',
    ]

    for pattern in array_patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I
            )

            for item in found:

                h = safe_float(item[0])
                d = safe_float(item[1])
                a = safe_float(item[2])

                if h and d and a:
                    odds.append(
                        (
                            h,
                            d,
                            a
                        )
                    )

        except Exception:
            pass

    # 중복 제거
    unique = []

    for item in odds:

        if item not in unique:
            unique.append(item)

    return unique


# ============================================================
# 페이지 분석
# ============================================================

def inspect_page(
    url,
    log_callback=None
):

    def log(message):

        if log_callback:
            log_callback(message)

    response = get(url)

    if response is None:
        log(f"접속 실패: {url}")
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

    page_html = response.text

    log(
        f"HTTP {response.status_code} | "
        f"{len(page_html):,} bytes | "
        f"{url}"
    )

    if response.status_code != 200:
        return {
            "url": url,
            "status": response.status_code,
            "html": page_html,
            "iframes": [],
            "scripts": [],
            "apis": [],
            "match_ids": [],
            "teams": [],
            "odds": [],
        }

    iframes = find_iframes(
        url,
        page_html
    )

    scripts = find_scripts(
        url,
        page_html
    )

    apis = find_api_candidates(
        page_html,
        url
    )

    match_ids = find_match_ids(
        page_html
    )

    teams = extract_team_pairs(
        page_html
    )

    odds = extract_1x2_odds(
        page_html
    )

    log(
        f"iframe={len(iframes)} "
        f"script={len(scripts)} "
        f"API={len(apis)} "
        f"경기ID={len(match_ids)} "
        f"팀={len(teams)} "
        f"1X2={len(odds)}"
    )

    # iframe 분석
    for iframe_url in iframes[:15]:

        iframe_response = get(
            iframe_url
        )

        if iframe_response is None:
            continue

        iframe_html = iframe_response.text

        log(
            f"iframe HTTP "
            f"{iframe_response.status_code} | "
            f"{len(iframe_html):,} bytes | "
            f"{iframe_url}"
        )

        iframe_ids = find_match_ids(
            iframe_html
        )

        iframe_teams = extract_team_pairs(
            iframe_html
        )

        iframe_odds = extract_1x2_odds(
            iframe_html
        )

        iframe_apis = find_api_candidates(
            iframe_html,
            iframe_url
        )

        match_ids.extend(
            iframe_ids
        )

        teams.extend(
            iframe_teams
        )

        odds.extend(
            iframe_odds
        )

        apis.extend(
            iframe_apis
        )

        # iframe 내부 script
        iframe_scripts = find_scripts(
            iframe_url,
            iframe_html
        )

        scripts.extend(
            iframe_scripts
        )

    # JS 분석
    js_counter = 0

    for script_url in scripts[:40]:

        js_response = get(
            script_url
        )

        if js_response is None:
            continue

        js_text = js_response.text

        js_counter += 1

        new_ids = find_match_ids(
            js_text
        )

        new_apis = find_api_candidates(
            js_text,
            script_url
        )

        new_odds = extract_1x2_odds(
            js_text
        )

        match_ids.extend(
            new_ids
        )

        apis.extend(
            new_apis
        )

        odds.extend(
            new_odds
        )

    # 중복 제거
    match_ids = sorted(
        set(match_ids),
        key=lambda x: int(x)
    )

    apis = list(
        dict.fromkeys(apis)
    )

    scripts = list(
        dict.fromkeys(scripts)
    )

    iframes = list(
        dict.fromkeys(iframes)
    )

    return {
        "url": url,
        "status": response.status_code,
        "html": page_html,
        "iframes": iframes,
        "scripts": scripts,
        "apis": apis,
        "match_ids": match_ids,
        "teams": teams,
        "odds": odds,
        "js_loaded": js_counter,
    }


# ============================================================
# 날짜 수집
# ============================================================

def collect_date(
    date_string,
    cid="",
    retry_count=3,
    retry_delay=1.0,
    log_callback=None,
):

    def log(message):

        if log_callback:
            log_callback(message)

    result = {
        "date": date_string,
        "matches": [],
        "ids": [],
        "odds": [],
        "pages": [],
        "apis": [],
    }

    log("=" * 60)
    log(f"7M 수집 시작: {date_string}")
    log("=" * 60)

    urls = build_date_urls(
        date_string
    )

    all_ids = set()
    all_odds = []
    all_pages = []
    all_apis = []

    for url in urls:

        found = False

        for attempt in range(
            retry_count + 1
        ):

            data = inspect_page(
                url,
                log_callback=log
            )

            all_pages.append(
                data
            )

            if data["match_ids"]:

                for match_id in data["match_ids"]:
                    all_ids.add(match_id)

                found = True
                break

            if attempt < retry_count:

                log(
                    f"경기 후보 없음 "
                    f"재시도 {attempt + 1}/"
                    f"{retry_count}"
                )

                time.sleep(
                    retry_delay
                )

        all_apis.extend(
            data.get("apis", [])
        )

        all_odds.extend(
            data.get("odds", [])
        )

        if found:
            log(
                f"경기 ID 발견: "
                f"{len(data['match_ids'])}"
            )

    result["ids"] = sorted(
        all_ids,
        key=lambda x: int(x)
    )

    result["odds"] = all_odds

    result["pages"] = all_pages

    result["apis"] = list(
        dict.fromkeys(all_apis)
    )

    log("")
    log(
        f"최종 발견 경기 ID: "
        f"{len(result['ids'])}"
    )

    log(
        f"발견 API 후보: "
        f"{len(result['apis'])}"
    )

    log(
        f"1X2 배당 후보: "
        f"{len(result['odds'])}"
    )

    return result


# ============================================================
# 경기 상세 후보 URL
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
            f"{base}/matchdata.aspx?id={match_id}",
            f"{base}/match_detail.aspx?id={match_id}",
            f"{base}/odds.aspx?id={match_id}",
            f"{base}/odds_detail.aspx?id={match_id}",
        ])

    return list(
        dict.fromkeys(urls)
    )


# ============================================================
# 경기 상세 수집
# ============================================================

def collect_match(
    match_id,
    cid="",
    retry_count=3,
    retry_delay=1.0,
    log_callback=None,
):

    def log(message):

        if log_callback:
            log_callback(message)

    best = {
        "match_id": str(match_id),
        "home_team": "",
        "away_team": "",
        "home_score": None,
        "away_score": None,
        "result": None,
        "home_odds": None,
        "draw_odds": None,
        "away_odds": None,
        "cid": cid,
        "url": "",
    }

    urls = build_match_urls(
        match_id
    )

    for url in urls:

        for attempt in range(
            retry_count + 1
        ):

            response = get(url)

            if response is None:
                continue

            if response.status_code != 200:

                if attempt < retry_count:
                    time.sleep(
                        retry_delay
                    )

                continue

            text = response.text

            pairs = extract_team_pairs(
                text
            )

            scores = extract_scores(
                text
            )

            odds = extract_1x2_odds(
                text
            )

            if pairs:

                if not best["home_team"]:
                    best["home_team"] = pairs[0][0]

                if not best["away_team"]:
                    best["away_team"] = pairs[0][1]

            if scores:

                if best["home_score"] is None:
                    best["home_score"] = scores[0][0]

                if best["away_score"] is None:
                    best["away_score"] = scores[0][1]

                best["result"] = normalize_result(
                    best["home_score"],
                    best["away_score"]
                )

            if odds:

                selected = odds[-1]

                best["home_odds"] = selected[0]
                best["draw_odds"] = selected[1]
                best["away_odds"] = selected[2]

            if (
                best["home_team"]
                and best["away_team"]
            ):

                best["url"] = url

                log(
                    f"[{match_id}] "
                    f"{best['home_team']} vs "
                    f"{best['away_team']} | "
                    f"배당 "
                    f"{best['home_odds']} / "
                    f"{best['draw_odds']} / "
                    f"{best['away_odds']} | "
                    f"결과 {best['result']}"
                )

                return best

            break

    return best


# ============================================================
# 전체 실행
# ============================================================

def collect(
    start_date,
    end_date,
    cid="",
    retry_count=3,
    retry_delay=1.0,
    log_callback=None,
):

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

        date_string = current.strftime(
            "%Y-%m-%d"
        )

        daily = collect_date(
            date_string=date_string,
            cid=cid,
            retry_count=retry_count,
            retry_delay=retry_delay,
            log_callback=log_callback,
        )

        ids = daily.get(
            "ids",
            []
        )

        log_message = (
            f"{date_string} "
            f"경기 {len(ids)}개 발견"
        )

        if log_callback:
            log_callback(
                log_message
            )

        for match_id in ids:

            match = collect_match(
                match_id=match_id,
                cid=cid,
                retry_count=retry_count,
                retry_delay=retry_delay,
                log_callback=log_callback,
            )

            if (
                match["home_team"]
                or match["away_team"]
                or match["home_odds"]
            ):

                match["match_date"] = date_string

                final_matches.append(
                    match
                )

        current += timedelta(
            days=1
        )

    # 경기 중복 제거
    unique = {}

    for item in final_matches:

        key = (
            item.get("match_id")
            or (
                item.get("match_date"),
                item.get("home_team"),
                item.get("away_team"),
            )
        )

        unique[key] = item

    final_matches = list(
        unique.values()
    )

    if log_callback:

        log_callback("")
        log_callback("=" * 60)
        log_callback(
            f"최종 수집 경기: "
            f"{len(final_matches)}"
        )

        odds_count = sum(
            1
            for x in final_matches
            if (
                x.get("home_odds")
                and x.get("draw_odds")
                and x.get("away_odds")
            )
        )

        log_callback(
            f"최종 1X2 배당: "
            f"{odds_count}"
        )

        result_count = sum(
            1
            for x in final_matches
            if x.get("result")
        )

        log_callback(
            f"실제 결과: "
            f"{result_count}"
        )

        log_callback("=" * 60)

    return final_matches


# ============================================================
# 연결 진단
# ============================================================

def diagnose(
    date_string,
    cid="",
    log_callback=None,
):

    data = collect_date(
        date_string=date_string,
        cid=cid,
        retry_count=1,
        retry_delay=0.5,
        log_callback=log_callback,
    )

    diagnostic = {
        "date": date_string,
        "http": 0,
        "html_bytes": 0,
        "js_bytes": 0,
        "iframes": 0,
        "scripts": 0,
        "apis": len(
            data.get("apis", [])
        ),
        "match_candidates": len(
            data.get("ids", [])
        ),
        "odds_candidates": len(
            data.get("odds", [])
        ),
        "pages": len(
            data.get("pages", [])
        ),
    }

    pages = data.get(
        "pages",
        []
    )

    for page in pages:

        if page.get("status") == 200:

            diagnostic["http"] = 200

            diagnostic["html_bytes"] = max(
                diagnostic["html_bytes"],
                len(
                    page.get(
                        "html",
                        ""
                    )
                )
            )

            diagnostic["iframes"] += len(
                page.get(
                    "iframes",
                    []
                )
            )

            diagnostic["scripts"] += len(
                page.get(
                    "scripts",
                    []
                )
            )

            for script_url in page.get(
                "scripts",
                []
            ):

                js_response = get(
                    script_url
                )

                if js_response is not None:

                    diagnostic["js_bytes"] += len(
                        js_response.text
                    )

    return diagnostic
