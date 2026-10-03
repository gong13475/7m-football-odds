# ============================================================
# sevenm_crawler.py
# ⚽ 7M 축구 최종배당 수집기 - API 자동 탐색 강화판
#
# app.py 수정 불필요
#
# 기능
# - 7M 시작 페이지 탐색
# - iframe 탐색
# - JS 탐색
# - API 후보 탐색
# - API 실제 호출
# - JSON / JS / HTML 경기 ID 탐색
# - 경기 상세 URL 자동 탐색
# - 팀명 탐색
# - 스코어 탐색
# - 1X2 배당 탐색
# - 최종배당 후보 선택
# - 날짜별 수집
# - 기존 app.py 인터페이스 유지
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

def request_get(
    url,
    referer=None,
    params=None,
    timeout=TIMEOUT,
):

    try:

        headers = {}

        if referer:
            headers["Referer"] = referer

        response = session.get(
            url,
            headers=headers,
            params=params,
            timeout=timeout,
            allow_redirects=True,
        )

        if not response.encoding:
            response.encoding = (
                response.apparent_encoding
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

    value = html_lib.unescape(
        str(value)
    )

    value = value.replace(
        "\\/",
        "/"
    )

    value = value.replace(
        "\\u002F",
        "/"
    )

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
            .replace('"', "")
            .replace("'", "")
            .strip()
        )

        number = float(value)

        if 1.01 <= number <= 100:
            return number

    except Exception:
        pass

    return None


def valid_score(value):

    try:

        number = int(
            float(
                str(value).strip()
            )
        )

        if 0 <= number <= 99:
            return number

    except Exception:
        pass

    return None


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
# JSON 파싱
# ============================================================

def try_json(text):

    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    cleaned = text.strip()

    cleaned = (
        cleaned
        .replace(
            ")]}',",
            ""
        )
        .strip()
    )

    try:
        return json.loads(cleaned)
    except Exception:
        return None


# ============================================================
# HTML 링크
# ============================================================

def extract_links(
    page_url,
    source_html,
):

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
                (
                    "javascript:",
                    "mailto:",
                    "#",
                )
            ):
                continue

            absolute = urljoin(
                page_url,
                href,
            )

            if absolute not in result:
                result.append(
                    absolute
                )

    except Exception:
        pass

    return result


# ============================================================
# 경기 ID 추출
# ============================================================

def extract_match_id_from_url(url):

    if not url:
        return None

    decoded = unquote(
        str(url)
    )

    patterns = [

        r"[?&](?:id|mid|matchid|match_id)"
        r"=(\d{4,12})",

        r"[?&](?:gameid|game_id)"
        r"=(\d{4,12})",

        r"[?&](?:eventid|event_id)"
        r"=(\d{4,12})",

        r"[?&](?:fid|fixtureid)"
        r"=(\d{4,12})",

        r"/match(?:es)?/"
        r"(\d{4,12})",

        r"/game(?:s)?/"
        r"(\d{4,12})",

        r"/event(?:s)?/"
        r"(\d{4,12})",

        r"/fixture(?:s)?/"
        r"(\d{4,12})",

        r"/detail/"
        r"(\d{4,12})",

        r"/odds/"
        r"(\d{4,12})",

        r"(?:match|game|event|fixture)"
        r"[-_/](\d{4,12})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            decoded,
            re.I,
        )

        if match:

            try:

                value = int(
                    match.group(1)
                )

                if value >= 1000:
                    return str(value)

            except Exception:
                pass

    return None


# ============================================================
# HTML/JS 경기 ID
# ============================================================

def extract_match_ids(
    source_html
):

    ids = set()

    if not source_html:
        return ids

    patterns = [

        r'data-(?:match-id|matchid|match_id)'
        r'\s*=\s*["\'](\d{4,12})["\']',

        r'data-(?:game-id|gameid|game_id)'
        r'\s*=\s*["\'](\d{4,12})["\']',

        r'data-(?:event-id|eventid|event_id)'
        r'\s*=\s*["\'](\d{4,12})["\']',

        r'data-(?:fixture-id|fixtureid|fixture_id)'
        r'\s*=\s*["\'](\d{4,12})["\']',

        r'"(?:matchId|matchID|match_id)"'
        r'\s*:\s*["\']?(\d{4,12})',

        r'"(?:gameId|gameID|game_id)"'
        r'\s*:\s*["\']?(\d{4,12})',

        r'"(?:eventId|eventID|event_id)"'
        r'\s*:\s*["\']?(\d{4,12})',

        r'"(?:fixtureId|fixtureID|fixture_id)"'
        r'\s*:\s*["\']?(\d{4,12})',

        r'/(?:match|game|event|fixture)/'
        r'(\d{4,12})',

        r'[?&](?:id|mid|matchid|gameid|eventid)'
        r'=(\d{4,12})',

        r'(?:match|game|event|fixture)'
        r'Id\s*[:=]\s*["\']?'
        r'(\d{4,12})',

        r'(?:match|game|event|fixture)'
        r'_?id\s*[:=]\s*["\']?'
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

        match_id = (
            extract_match_id_from_url(
                url
            )
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

    return list(
        unique.values()
    )


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

        for tag in soup.find_all(
            "iframe"
        ):

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
                result.append(
                    url
                )

    except Exception:
        pass

    return result


# ============================================================
# SCRIPT
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

        for tag in soup.find_all(
            "script"
        ):

            src = tag.get("src")

            if src:

                url = urljoin(
                    page_url,
                    src,
                )

                if url not in result:
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
    source_html,
):

    result = []

    if not source_html:
        return result

    patterns = [

        r'https?://[^"\'\s<>]+',

        r'["\']([^"\']{1,1000}'
        r'(?:/api/|/ajax/|/data/|'
        r'/json/|/service/|/interface/)'
        r'[^"\']*)["\']',

        r'["\']([^"\']{1,1000}'
        r'(?:\.json|\.ashx|\.asmx)'
        r'[^"\']*)["\']',

        r'url\s*[:=]\s*["\']([^"\']+)["\']',

        r'endpoint\s*[:=]\s*["\']([^"\']+)["\']',

        r'apiUrl\s*[:=]\s*["\']([^"\']+)["\']',

        r'api_url\s*[:=]\s*["\']([^"\']+)["\']',

        r'ajaxUrl\s*[:=]\s*["\']([^"\']+)["\']',
    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                source_html,
                re.I,
            )

            for value in found:

                if isinstance(
                    value,
                    tuple
                ):
                    value = value[0]

                value = html_lib.unescape(
                    str(value)
                )

                value = value.replace(
                    "\\/",
                    "/"
                )

                if not value:
                    continue

                if value.startswith(
                    "//"
                ):
                    value = (
                        "https:"
                        + value
                    )

                elif value.startswith(
                    "/"
                ):
                    value = urljoin(
                        page_url,
                        value,
                    )

                elif not value.startswith(
                    (
                        "http://",
                        "https://",
                    )
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
                        ".woff",
                        ".ttf",
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
                    or "api" in low
                    or "ajax" in low
                ):

                    if value not in result:
                        result.append(
                            value
                        )

        except Exception:
            pass

    return result


# ============================================================
# JS/API 내부 URL 확장
# ============================================================

def extract_urls_from_text(
    base_url,
    text,
):

    result = []

    if not text:
        return result

    patterns = [

        r'["\'](\/[^"\']{2,500})["\']',

        r'["\'](https?://[^"\']{2,1000})["\']',

        r'url\s*\(\s*["\']?([^"\')\s]+)',

        r'["\']([^"\']*(?:api|ajax|json)'
        r'[^"\']*)["\']',
    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                re.I,
            )

            for value in found:

                value = (
                    html_lib.unescape(
                        str(value)
                    )
                    .replace(
                        "\\/",
                        "/"
                    )
                )

                if not value:
                    continue

                if value.startswith(
                    "/"
                ):
                    value = urljoin(
                        base_url,
                        value,
                    )

                if not value.startswith(
                    (
                        "http://",
                        "https://",
                    )
                ):
                    continue

                low = value.lower()

                if (
                    "api" in low
                    or "ajax" in low
                    or "json" in low
                    or "data" in low
                    or "service" in low
                    or "interface" in low
                ):

                    if value not in result:
                        result.append(
                            value
                        )

        except Exception:
            pass

    return result


# ============================================================
# 재귀 JSON 순회
# ============================================================

def walk_json(
    value,
    path="",
):

    if isinstance(
        value,
        dict
    ):

        yield value, path

        for key, child in value.items():

            child_path = (
                f"{path}.{key}"
                if path
                else str(key)
            )

            yield from walk_json(
                child,
                child_path,
            )

    elif isinstance(
        value,
        list
    ):

        for index, child in enumerate(
            value
        ):

            child_path = (
                f"{path}[{index}]"
            )

            yield from walk_json(
                child,
                child_path,
            )


# ============================================================
# JSON 경기 데이터
# ============================================================

def extract_matches_from_json(
    data,
):

    results = []

    if data is None:
        return results

    for obj, path in walk_json(
        data
    ):

        if not isinstance(
            obj,
            dict
        ):
            continue

        match_id = None

        id_keys = [
            "matchId",
            "matchID",
            "match_id",
            "gameId",
            "gameID",
            "game_id",
            "eventId",
            "eventID",
            "event_id",
            "fixtureId",
            "fixtureID",
            "fixture_id",
            "fid",
            "mid",
        ]

        for key in id_keys:

            if key not in obj:
                continue

            candidate = str(
                obj.get(key)
            ).strip()

            candidate = re.sub(
                r"\D",
                "",
                candidate,
            )

            try:

                if (
                    candidate
                    and int(candidate) >= 1000
                ):
                    match_id = candidate
                    break

            except Exception:
                pass

        if not match_id:
            continue

        item = {
            "id": match_id,
            "url": "",
            "json": obj,
            "path": path,
        }

        results.append(
            item
        )

    unique = {}

    for item in results:
        unique[item["id"]] = item

    return list(
        unique.values()
    )


# ============================================================
# JSON 팀명
# ============================================================

def get_value_case_insensitive(
    obj,
    keys,
):

    if not isinstance(
        obj,
        dict
    ):
        return None

    lowered = {
        str(k).lower(): v
        for k, v in obj.items()
    }

    for key in keys:

        value = lowered.get(
            key.lower()
        )

        if value is not None:
            return value

    return None


def extract_teams_from_object(
    obj
):

    if not isinstance(
        obj,
        dict
    ):
        return None

    home_keys = [
        "homeTeam",
        "home_team",
        "homeName",
        "home_name",
        "hometeam",
        "home",
        "HomeTeam",
        "HomeName",
    ]

    away_keys = [
        "awayTeam",
        "away_team",
        "awayName",
        "away_name",
        "awayteam",
        "away",
        "AwayTeam",
        "AwayName",
    ]

    home = get_value_case_insensitive(
        obj,
        home_keys,
    )

    away = get_value_case_insensitive(
        obj,
        away_keys,
    )

    if isinstance(
        home,
        dict
    ):
        home = (
            home.get("name")
            or home.get("teamName")
            or home.get("team_name")
            or ""
        )

    if isinstance(
        away,
        dict
    ):
        away = (
            away.get("name")
            or away.get("teamName")
            or away.get("team_name")
            or ""
        )

    home = clean_text(
        home
    )

    away = clean_text(
        away
    )

    if (
        2 <= len(home) <= 150
        and 2 <= len(away) <= 150
    ):
        return (
            home,
            away,
        )

    return None


# ============================================================
# JSON 스코어
# ============================================================

def extract_score_from_object(
    obj
):

    if not isinstance(
        obj,
        dict
    ):
        return None

    home_keys = [
        "homeScore",
        "home_score",
        "homescore",
        "HomeScore",
        "scoreHome",
        "homeResult",
    ]

    away_keys = [
        "awayScore",
        "away_score",
        "awayscore",
        "AwayScore",
        "scoreAway",
        "awayResult",
    ]

    home = get_value_case_insensitive(
        obj,
        home_keys,
    )

    away = get_value_case_insensitive(
        obj,
        away_keys,
    )

    h = valid_score(
        home
    )

    a = valid_score(
        away
    )

    if (
        h is not None
        and a is not None
    ):
        return (
            h,
            a,
        )

    return None


# ============================================================
# JSON 배당
# ============================================================

def extract_odds_from_object(
    obj
):

    if not isinstance(
        obj,
        dict
    ):
        return []

    combinations = [

        (
            [
                "home",
                "homeOdds",
                "odds1",
                "win",
                "winOdds",
            ],
            [
                "draw",
                "drawOdds",
                "oddsX",
            ],
            [
                "away",
                "awayOdds",
                "odds2",
                "lose",
                "loseOdds",
            ],
        ),

        (
            [
                "one",
                "1",
                "odds_1",
                "home_price",
            ],
            [
                "x",
                "X",
                "odds_x",
                "draw_price",
            ],
            [
                "two",
                "2",
                "odds_2",
                "away_price",
            ],
        ),
    ]

    results = []

    for home_keys, draw_keys, away_keys in combinations:

        h = get_value_case_insensitive(
            obj,
            home_keys,
        )

        d = get_value_case_insensitive(
            obj,
            draw_keys,
        )

        a = get_value_case_insensitive(
            obj,
            away_keys,
        )

        h = valid_odd(h)
        d = valid_odd(d)
        a = valid_odd(a)

        if (
            h is not None
            and d is not None
            and a is not None
        ):

            value = (
                h,
                d,
                a,
            )

            if value not in results:
                results.append(
                    value
                )

    return results


# ============================================================
# JSON 전체에서 경기 데이터
# ============================================================

def parse_json_matches(
    data
):

    results = []

    for obj, path in walk_json(
        data
    ):

        if not isinstance(
            obj,
            dict
        ):
            continue

        match_id = None

        for key in [
            "matchId",
            "matchID",
            "match_id",
            "gameId",
            "gameID",
            "game_id",
            "eventId",
            "eventID",
            "event_id",
            "fixtureId",
            "fixtureID",
            "fixture_id",
            "fid",
            "mid",
        ]:

            value = obj.get(
                key
            )

            if value is None:
                continue

            digits = re.sub(
                r"\D",
                "",
                str(value)
            )

            try:

                if (
                    digits
                    and int(digits) >= 1000
                ):
                    match_id = digits
                    break

            except Exception:
                pass

        if not match_id:
            continue

        teams = extract_teams_from_object(
            obj
        )

        score = extract_score_from_object(
            obj
        )

        odds = extract_odds_from_object(
            obj
        )

        results.append(
            {
                "match_id": match_id,
                "teams": teams,
                "score": score,
                "odds": odds,
                "object": obj,
                "path": path,
            }
        )

    unique = {}

    for item in results:

        key = item["match_id"]

        if key not in unique:
            unique[key] = item
            continue

        old = unique[key]

        if not old.get(
            "teams"
        ) and item.get(
            "teams"
        ):
            old["teams"] = item["teams"]

        if not old.get(
            "score"
        ) and item.get(
            "score"
        ):
            old["score"] = item["score"]

        if not old.get(
            "odds"
        ) and item.get(
            "odds"
        ):
            old["odds"] = item["odds"]

    return list(
        unique.values()
    )


# ============================================================
# 일반 HTML 팀명
# ============================================================

def extract_teams(
    source_html
):

    result = []

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
            r'"HomeTeam"\s*:\s*"([^"]+)".{0,2000}?'
            r'"AwayTeam"\s*:\s*"([^"]+)"'
        ),

        (
            r'"home_name"\s*:\s*"([^"]+)".{0,2000}?'
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

                home = clean_text(
                    pair[0]
                )

                away = clean_text(
                    pair[1]
                )

                if (
                    2 <= len(home) <= 150
                    and 2 <= len(away) <= 150
                ):

                    item = (
                        home,
                        away,
                    )

                    if item not in result:
                        result.append(
                            item
                        )

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

        for tag in soup.find_all(
            [
                "script",
                "style",
                "noscript",
            ]
        ):
            tag.decompose()

        text = clean_text(
            soup.get_text(
                " "
            )
        )

        patterns = [

            r"([A-Za-zÀ-ÿ0-9가-힣][^|]{1,80})"
            r"\s+(?:vs\.?|VS|v)\s+"
            r"([^|]{1,80})",

            r"([A-Za-zÀ-ÿ0-9가-힣][^|]{1,80})"
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

                    home = clean_text(
                        pair[0]
                    )

                    away = clean_text(
                        pair[1]
                    )

                    if (
                        2 <= len(home) <= 100
                        and 2 <= len(away) <= 100
                    ):

                        value = (
                            home,
                            away,
                        )

                        if value not in result:
                            result.append(
                                value
                            )

            except Exception:
                pass

    except Exception:
        pass

    return result


# ============================================================
# 스코어
# ============================================================

def extract_score(
    source_html
):

    patterns = [

        (
            r'"homeScore"\s*:\s*["\']?'
            r'(\d{1,2})["\']?.{0,1500}?'
            r'"awayScore"\s*:\s*["\']?'
            r'(\d{1,2})'
        ),

        (
            r'"home_score"\s*:\s*["\']?'
            r'(\d{1,2})["\']?.{0,1500}?'
            r'"away_score"\s*:\s*["\']?'
            r'(\d{1,2})'
        ),

        (
            r'"HomeScore"\s*:\s*["\']?'
            r'(\d{1,2})["\']?.{0,1500}?'
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

def extract_odds(
    source_html
):

    result = []

    patterns = [

        (
            r'"homeOdds"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,2000}?'
            r'"drawOdds"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,2000}?'
            r'"awayOdds"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
        ),

        (
            r'"odds1"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,2000}?'
            r'"oddsX"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,2000}?'
            r'"odds2"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
        ),

        (
            r'"win"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,2000}?'
            r'"draw"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,2000}?'
            r'"lose"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
        ),

        (
            r'"1"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,2000}?'
            r'"X"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,2000}?'
            r'"2"\s*:\s*'
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
                    result.append(
                        value
                    )

        except Exception:
            pass

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
# API 응답에서 경기 추출
# ============================================================

def inspect_api(
    api_url,
    referer=None,
):

    response = request_get(
        api_url,
        referer=referer,
        timeout=15,
    )

    if response is None:
        return None

    if response.status_code != 200:
        return None

    text = response.text

    parsed = try_json(
        text
    )

    json_matches = []

    if parsed is not None:

        json_matches = (
            parse_json_matches(
                parsed
            )
        )

    html_ids = extract_match_ids(
        text
    )

    return {
        "url": response.url,
        "status": response.status_code,
        "text": text,
        "json": parsed,
        "json_matches": json_matches,
        "ids": html_ids,
        "size": len(
            response.content
        ),
        "content_type":
            response.headers.get(
                "Content-Type",
                "",
            ),
    }


# ============================================================
# 상세 페이지 URL
# ============================================================

def candidate_match_urls(
    match_id
):

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
# 상세 페이지 검사
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

        teams = (
            extract_teams_from_visible_text(
                source_html
            )
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
        "teams": (
            teams[0]
            if teams
            else None
        ),
        "score": score,
        "odds": odds,
        "size": len(
            response.content
        ),
        "status_code":
            response.status_code,
    }


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
        urls.append(
            source_url
        )

    for url in candidate_match_urls(
        match_id
    ):

        if url not in urls:
            urls.append(
                url
            )

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

            if detail.get(
                "teams"
            ):
                score += 10

            if detail.get(
                "odds"
            ):
                score += 20

            if detail.get(
                "score"
            ):
                score += 5

            if detail.get(
                "size",
                0
            ) > 5000:
                score += 2

            detail[
                "_score"
            ] = score

            if (
                best is None
                or score > best[
                    "_score"
                ]
            ):
                best = detail

            if (
                detail.get("teams")
                and detail.get("odds")
            ):
                return detail

        if attempt < retry_count:
            time.sleep(
                retry_delay
            )

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

            (
                f"{base_url}"
                f"?date={date_string}"
                f"&sport=1"
            ),
        ]

        for url in candidates:

            response = request_get(
                url
            )

            if response is None:
                continue

            if response.status_code != 200:
                continue

            if len(
                response.content
            ) < 5000:
                continue

            source_html = response.text

            links = (
                extract_real_match_links(
                    response.url,
                    source_html,
                )
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
                + len(apis) * 5
                + len(iframes) * 3
                + len(scripts)
                + len(
                    response.content
                ) // 100000
            )

            candidate = {
                "url":
                    response.url,

                "html":
                    source_html,

                "links":
                    links,

                "ids":
                    ids,

                "iframes":
                    iframes,

                "scripts":
                    scripts,

                "apis":
                    apis,

                "score":
                    score,
            }

            if (
                best is None
                or score > best[
                    "score"
                ]
            ):
                best = candidate

    return best


# ============================================================
# API에서 경기 후보 수집
# ============================================================

def discover_api_matches(
    page,
    date_string,
    log_callback=None,
):

    matches = []

    if not page:
        return matches

    api_urls = list(
        page.get(
            "apis",
            []
        )
    )

    # JS 파일 내부 API도 탐색
    for script_url in page.get(
        "scripts",
        []
    ):

        response = request_get(
            script_url,
            referer=page.get(
                "url"
            ),
        )

        if response is None:
            continue

        if response.status_code != 200:
            continue

        found = (
            extract_urls_from_text(
                script_url,
                response.text,
            )
        )

        for url in found:

            if url not in api_urls:
                api_urls.append(
                    url
                )

    log(
        log_callback,
        f"🔌 실제 API 호출 후보: {len(api_urls)}개",
    )

    seen_ids = set()

    for index, api_url in enumerate(
        api_urls[:80],
        1,
    ):

        log(
            log_callback,
            (
                f"API [{index}/"
                f"{min(80, len(api_urls))}] "
                f"{api_url}"
            ),
        )

        try:

            result = inspect_api(
                api_url,
                referer=page.get(
                    "url"
                ),
            )

            if result is None:
                continue

            json_matches = result.get(
                "json_matches",
                []
            )

            for item in json_matches:

                match_id = item.get(
                    "match_id"
                )

                if not match_id:
                    continue

                if match_id in seen_ids:
                    continue

                seen_ids.add(
                    match_id
                )

                matches.append(
                    {
                        "id":
                            match_id,

                        "url":
                            "",

                        "api_url":
                            api_url,

                        "api_data":
                            item,
                    }
                )

            # JSON이 아닌 응답
            text = result.get(
                "text",
                ""
            )

            for match_id in (
                result.get(
                    "ids",
                    set()
                )
            ):

                if match_id in seen_ids:
                    continue

                seen_ids.add(
                    match_id
                )

                matches.append(
                    {
                        "id":
                            match_id,

                        "url":
                            "",

                        "api_url":
                            api_url,
                    }
                )

        except Exception as e:

            log(
                log_callback,
                f"  API 검사 오류: {e}",
            )

    return matches


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
        "🔎 7M API/경기 데이터 진단",
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

        "date":
            date_string,

        "http":
            0,

        "html_bytes":
            0,

        "js_bytes":
            0,

        "match_links":
            0,

        "match_ids":
            0,

        "match_candidates":
            0,

        "iframes":
            0,

        "scripts":
            0,

        "apis":
            0,

        "api_candidates":
            [],

        "script_urls":
            [],

        "iframe_urls":
            [],

        "matches":
            [],

        "page_url":
            "",
    }

    if page is None:

        log(
            log_callback,
            "❌ 7M 시작 페이지 실패",
        )

        return result

    source_html = page[
        "html"
    ]

    result[
        "http"
    ] = 200

    result[
        "page_url"
    ] = page[
        "url"
    ]

    result[
        "html_bytes"
    ] = len(
        source_html.encode(
            errors="ignore"
        )
    )

    result[
        "iframes"
    ] = len(
        page[
            "iframes"
        ]
    )

    result[
        "scripts"
    ] = len(
        page[
            "scripts"
        ]
    )

    result[
        "apis"
    ] = len(
        page[
            "apis"
        ]
    )

    result[
        "api_candidates"
    ] = page[
        "apis"
    ]

    result[
        "script_urls"
    ] = page[
        "scripts"
    ]

    result[
        "iframe_urls"
    ] = page[
        "iframes"
    ]

    # --------------------------------------------------------
    # JS 크기
    # --------------------------------------------------------

    js_bytes = 0

    for script_url in page[
        "scripts"
    ]:

        try:

            script_response = request_get(
                script_url,
                referer=page[
                    "url"
                ],
            )

            if (
                script_response
                is not None
                and script_response.status_code
                == 200
            ):

                js_bytes += len(
                    script_response.content
                )

        except Exception:
            pass

    result[
        "js_bytes"
    ] = js_bytes

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
    # 일반 HTML 경기
    # --------------------------------------------------------

    matches = list(
        page[
            "links"
        ]
    )

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
                "id":
                    match_id,

                "url":
                    "",
            }
        )

    # --------------------------------------------------------
    # JS 내부 경기 ID
    # --------------------------------------------------------

    js_match_ids = set()

    for script_url in page[
        "scripts"
    ]:

        try:

            script_response = request_get(
                script_url,
                referer=page[
                    "url"
                ],
            )

            if (
                script_response
                is None
                or script_response.status_code
                != 200
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

        if any(
            item["id"]
            == match_id
            for item in matches
        ):
            continue

        matches.append(
            {
                "id":
                    match_id,

                "url":
                    "",
            }
        )

    # --------------------------------------------------------
    # ★ 핵심: API 실제 호출
    # --------------------------------------------------------

    api_matches = (
        discover_api_matches(
            page,
            date_string,
            log_callback=log_callback,
        )
    )

    for item in api_matches:

        match_id = item.get(
            "id"
        )

        if not match_id:
            continue

        found = False

        for existing in matches:

            if existing.get(
                "id"
            ) == match_id:

                # API 데이터 보강
                if item.get(
                    "api_url"
                ):
                    existing[
                        "api_url"
                    ] = item[
                        "api_url"
                    ]

                if item.get(
                    "api_data"
                ):
                    existing[
                        "api_data"
                    ] = item[
                        "api_data"
                    ]

                found = True
                break

        if not found:
            matches.append(
                item
            )

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

    unique = {}

    for item in matches:

        match_id = item.get(
            "id"
        )

        if not match_id:
            continue

        unique[
            match_id
        ] = item

    matches = list(
        unique.values()
    )

    result[
        "matches"
    ] = matches

    result[
        "match_links"
    ] = len(matches)

    result[
        "match_ids"
    ] = len(matches)

    result[
        "match_candidates"
    ] = len(matches)

    log(
        log_callback,
        f"🎯 최종 경기 후보: {len(matches)}",
    )

    # --------------------------------------------------------
    # API 후보 로그
    # --------------------------------------------------------

    if page[
        "apis"
    ]:

        log(
            log_callback,
            "",
        )

        log(
            log_callback,
            "🔌 API 후보:",
        )

        for api in page[
            "apis"
        ][:40]:

            log(
                log_callback,
                f"  {api}",
            )

    # --------------------------------------------------------
    # 샘플 상세 검사
    # --------------------------------------------------------

    log(
        log_callback,
        "",
    )

    log(
        log_callback,
        "🧪 실제 경기 샘플 검사",
    )

    valid = []

    for index, item in enumerate(
        matches[:5],
        1,
    ):

        match_id = item[
            "id"
        ]

        log(
            log_callback,
            (
                f"[샘플 {index}/"
                f"{min(5, len(matches))}] "
                f"ID={match_id}"
            ),
        )

        detail = get_match(
            match_id,
            source_url=(
                item.get(
                    "url"
                )
                or None
            ),
            retry_count=1,
            retry_delay=0.3,
        )

        # API에서 이미 데이터가 있는 경우
        api_data = item.get(
            "api_data"
        )

        if detail is None:
            detail = {}

        if (
            not detail.get(
                "teams"
            )
            and api_data
        ):

            detail[
                "teams"
            ] = extract_teams_from_object(
                api_data.get(
                    "object",
                    {}
                )
            )

        if (
            not detail.get(
                "score"
            )
            and api_data
        ):

            detail[
                "score"
            ] = extract_score_from_object(
                api_data.get(
                    "object",
                    {}
                )
            )

        if (
            not detail.get(
                "odds"
            )
            and api_data
        ):

            detail[
                "odds"
            ] = extract_odds_from_object(
                api_data.get(
                    "object",
                    {}
                )
            )

        teams = detail.get(
            "teams"
        )

        odds = detail.get(
            "odds"
        )

        score = detail.get(
            "score"
        )

        if (
            teams
            or odds
            or score
        ):

            log(
                log_callback,
                (
                    f"  ✅ "
                    f"팀={teams} "
                    f"배당="
                    f"{odds[-1] if odds else None} "
                    f"결과="
                    f"{make_result(score)}"
                ),
            )

            valid.append(
                detail
            )

        else:

            log(
                log_callback,
                "  ⚠️ 상세 데이터 부족",
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
        "진단 결과",
    )

    log(
        log_callback,
        f"경기 후보: {len(matches)}",
    )

    log(
        log_callback,
        (
            f"샘플 데이터 성공: "
            f"{len(valid)}/"
            f"{min(5, len(matches))}"
        ),
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
            "❌ 경기 후보를 찾지 못했습니다.",
        )

        return []

    results = []

    total = len(
        matches
    )

    log(
        log_callback,
        "",
    )

    log(
        log_callback,
        (
            f"🎯 실제 경기 후보 "
            f"{total}개 수집 시작"
        ),
    )

    for index, item in enumerate(
        matches,
        1,
    ):

        match_id = item[
            "id"
        ]

        log(
            log_callback,
            (
                f"[{index}/{total}] "
                f"ID {match_id}"
            ),
        )

        detail = get_match(
            match_id,
            source_url=(
                item.get(
                    "url"
                )
                or None
            ),
            retry_count=retry_count,
            retry_delay=retry_delay,
        )

        # API 데이터 보강
        api_data = item.get(
            "api_data"
        )

        if detail is None:
            detail = {}

        if api_data:

            api_object = api_data.get(
                "object",
                {}
            )

            if not detail.get(
                "teams"
            ):

                detail[
                    "teams"
                ] = extract_teams_from_object(
                    api_object
                )

            if not detail.get(
                "score"
            ):

                detail[
                    "score"
                ] = extract_score_from_object(
                    api_object
                )

            if not detail.get(
                "odds"
            ):

                detail[
                    "odds"
                ] = extract_odds_from_object(
                    api_object
                )

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

            final_odds = (
                odds_list[-1]
            )

        result_value = make_result(
            score
        )

        # 최소한 ID만 있는 가짜 후보 방지
        if (
            not home_team
            and not away_team
            and not final_odds
            and not score
        ):

            log(
                log_callback,
                "  ⚠️ 실제 경기 데이터 없음",
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
                (
                    score[0]
                    if score
                    else None
                ),

            "away_score":
                (
                    score[1]
                    if score
                    else None
                ),

            "result":
                result_value,

            "home_odds":
                (
                    final_odds[0]
                    if final_odds
                    else None
                ),

            "draw_odds":
                (
                    final_odds[1]
                    if final_odds
                    else None
                ),

            "away_odds":
                (
                    final_odds[2]
                    if final_odds
                    else None
                ),

            "bookmaker":
                "7M",

            "cid":
                cid or "",

            "url":
                detail.get(
                    "url"
                )
                or item.get(
                    "api_url"
                )
                or "",
        }

        results.append(
            item_result
        )

        log(
            log_callback,
            (
                "  ✅ "
                f"{home_team or '-'} "
                f"vs "
                f"{away_team or '-'} | "
                f"{final_odds or '-'} | "
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
        (
            f"실제 경기 저장 대상: "
            f"{len(results)}"
        ),
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

    if start > end:
        return []

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

        unique[
            key
        ] = item

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
        (
            f"총 실제 경기: "
            f"{len(all_results)}"
        ),
    )

    odds_count = sum(
        1
        for x in all_results
        if (
            x.get(
                "home_odds"
            ) is not None
            and x.get(
                "draw_odds"
            ) is not None
            and x.get(
                "away_odds"
            ) is not None
        )
    )

    result_count = sum(
        1
        for x in all_results
        if x.get(
            "result"
        )
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
