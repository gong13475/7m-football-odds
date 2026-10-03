# ============================================================
# sevenm_crawler.py
# ⚽ 7M 축구 최종배당 수집기
#
# 핵심 개선
# ------------------------------------------------------------
# 1. HTML 경기 링크 탐색
# 2. data-* 경기 ID 탐색
# 3. JS 내부 경기 ID 탐색
# 4. iframe 탐색
# 5. API 후보 탐색
# 6. API 후보 실제 호출
# 7. JSON 재귀 탐색
# 8. API 응답 내부 경기 ID 자동 추출
# 9. API 응답 내부 팀명 / 스코어 / 1X2 배당 탐색
# 10. 경기 상세 URL 자동 탐색
# 11. 최종배당은 발견된 배당값 중 마지막 값을 사용
# ============================================================

import re
import time
import json
import html as html_lib
import requests

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, parse_qs, unquote


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

TIMEOUT = 25

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

        if value is None:
            return None

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


def is_match_id(value):

    try:

        number = int(
            str(value).strip()
        )

        return (
            1000
            <= number
            <= 999999999999
        )

    except Exception:
        return False


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
# 링크
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
# URL 경기 ID
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

        r"/match(?:es)?/(\d{4,12})",
        r"/game(?:s)?/(\d{4,12})",
        r"/event(?:s)?/(\d{4,12})",
        r"/fixture(?:s)?/(\d{4,12})",
        r"/detail/(\d{4,12})",
        r"/odds/(\d{4,12})",

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

            value = match.group(1)

            if is_match_id(value):
                return str(value)

    return None


# ============================================================
# HTML 내부 경기 ID
# ============================================================

def extract_match_ids(
    source_html
):

    ids = set()

    patterns = [

        r'data-(?:match-id|matchid|match_id)'
        r'\s*=\s*["\'](\d{4,12})["\']',

        r'data-(?:game-id|gameid|game_id)'
        r'\s*=\s*["\'](\d{4,12})["\']',

        r'data-(?:event-id|eventid|event_id)'
        r'\s*=\s*["\'](\d{4,12})["\']',

        r'data-(?:fixture-id|fixtureid)'
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

                if is_match_id(value):
                    ids.add(
                        str(value)
                    )

        except Exception:
            pass

    return ids


# ============================================================
# 실제 경기 링크
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
                result.append(url)

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

    patterns = [

        r'["\']([^"\']{1,1000}'
        r'(?:/api/|/ajax/|/data/|'
        r'/json/|/service/|/interface/)'
        r'[^"\']*)["\']',

        r'["\']([^"\']{1,1000}'
        r'(?:\.json|\.ashx|\.asmx)'
        r'[^"\']*)["\']',

        r'https?://[^"\'\s<>]+',
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

                if not value.startswith(
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
                        result.append(
                            value
                        )

        except Exception:
            pass

    return result


# ============================================================
# JSON 파싱
# ============================================================

def try_json(text):

    if not text:
        return None

    text = text.strip()

    # BOM
    text = text.lstrip(
        "\ufeff"
    )

    try:
        return json.loads(text)

    except Exception:
        pass

    # JSONP
    match = re.match(
        r"^[^(]+\((.*)\)\s*;?\s*$",
        text,
        re.S,
    )

    if match:

        try:
            return json.loads(
                match.group(1)
            )
        except Exception:
            pass

    return None


# ============================================================
# JSON 재귀 탐색
# ============================================================

def walk_json(
    obj,
    path="",
):

    if isinstance(
        obj,
        dict
    ):

        for key, value in obj.items():

            current = (
                f"{path}.{key}"
                if path
                else str(key)
            )

            yield (
                current,
                str(key),
                value,
            )

            yield from walk_json(
                value,
                current,
            )

    elif isinstance(
        obj,
        list
    ):

        for index, value in enumerate(
            obj
        ):

            current = (
                f"{path}[{index}]"
            )

            yield (
                current,
                str(index),
                value,
            )

            yield from walk_json(
                value,
                current,
            )


# ============================================================
# 키 정규화
# ============================================================

def normalized_key(key):

    return re.sub(
        r"[^a-z0-9]",
        "",
        str(key).lower(),
    )


# ============================================================
# JSON 경기 ID
# ============================================================

def extract_match_ids_from_json(
    data
):

    ids = set()

    id_keys = {
        "matchid",
        "gameid",
        "eventid",
        "fixtureid",
        "matchno",
        "gamecode",
        "eventcode",
        "fixturecode",
    }

    for _, key, value in walk_json(
        data
    ):

        nk = normalized_key(
            key
        )

        if nk not in id_keys:
            continue

        if is_match_id(value):
            ids.add(
                str(value)
            )

    return ids


# ============================================================
# JSON 문자열 내부 ID
# ============================================================

def extract_ids_from_text(
    text
):

    ids = set()

    if not text:
        return ids

    ids.update(
        extract_match_ids(
            text
        )
    )

    return ids


# ============================================================
# 팀명 추출
# ============================================================

def extract_teams(
    source_html
):

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
            r'"home_name"\s*:\s*"([^"]+)".{0,1500}?'
            r'"away_name"\s*:\s*"([^"]+)"'
        ),

        (
            r'"home"\s*:\s*"([^"]+)".{0,1500}?'
            r'"away"\s*:\s*"([^"]+)"'
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
                    and
                    2 <= len(away) <= 150
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
# JSON 팀명
# ============================================================

def extract_teams_from_json(
    data
):

    home = None
    away = None

    home_keys = {
        "hometeam",
        "homename",
        "hometeamname",
        "home_name",
        "home",
    }

    away_keys = {
        "awayteam",
        "awayname",
        "awayteamname",
        "away_name",
        "away",
    }

    for _, key, value in walk_json(
        data
    ):

        nk = normalized_key(
            key
        )

        if not isinstance(
            value,
            (str, int, float)
        ):
            continue

        text = clean_text(
            value
        )

        if not (
            2 <= len(text) <= 150
        ):
            continue

        if (
            nk in home_keys
            and home is None
        ):
            home = text

        if (
            nk in away_keys
            and away is None
        ):
            away = text

    if home and away:
        return (
            home,
            away,
        )

    return None


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

        for tag in soup(
            [
                "script",
                "style",
                "noscript",
            ]
        ):
            tag.decompose()

        text = clean_text(
            soup.get_text(" ")
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
                        and
                        2 <= len(away) <= 100
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
                    and
                    away is not None
                ):
                    return (
                        home,
                        away,
                    )

        except Exception:
            pass

    return None


# ============================================================
# JSON 스코어
# ============================================================

def extract_score_from_json(
    data
):

    home = None
    away = None

    home_keys = {
        "homescore",
        "home_score",
        "scorehome",
        "homescore1",
        "homegoals",
    }

    away_keys = {
        "awayscore",
        "away_score",
        "scoreaway",
        "awayscore1",
        "awaygoals",
    }

    for _, key, value in walk_json(
        data
    ):

        nk = normalized_key(
            key
        )

        if nk in home_keys:

            score = valid_score(
                value
            )

            if score is not None:
                home = score

        elif nk in away_keys:

            score = valid_score(
                value
            )

            if score is not None:
                away = score

    if (
        home is not None
        and
        away is not None
    ):
        return (
            home,
            away,
        )

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
# JSON 배당
# ============================================================

def extract_odds_from_json(
    data
):

    result = []

    # 직접적인 키 조합
    key_groups = [

        (
            {
                "homeodds",
                "homeodd",
                "odds1",
                "odd1",
                "winodds",
                "win",
            },
            {
                "drawodds",
                "drawodd",
                "oddsx",
                "oddx",
                "draw",
            },
            {
                "awayodds",
                "awayodd",
                "odds2",
                "odd2",
                "loseodds",
                "lose",
            },
        )
    ]

    values = {}

    for _, key, value in walk_json(
        data
    ):

        nk = normalized_key(
            key
        )

        odd = valid_odd(
            value
        )

        if odd is not None:
            values.setdefault(
                nk,
                []
            ).append(
                odd
            )

    for home_keys, draw_keys, away_keys in key_groups:

        homes = []
        draws = []
        aways = []

        for key in home_keys:
            homes.extend(
                values.get(
                    normalized_key(key),
                    []
                )
            )

        for key in draw_keys:
            draws.extend(
                values.get(
                    normalized_key(key),
                    []
                )
            )

        for key in away_keys:
            aways.extend(
                values.get(
                    normalized_key(key),
                    []
                )
            )

        for h in homes:
            for d in draws:
                for a in aways:

                    value = (
                        h,
                        d,
                        a,
                    )

                    if value not in result:
                        result.append(
                            value
                        )

    # --------------------------------------------------------
    # 배열형 odds
    # --------------------------------------------------------

    def scan_arrays(obj):

        if isinstance(
            obj,
            list
        ):

            numbers = []

            for value in obj:

                odd = valid_odd(
                    value
                )

                if odd is not None:
                    numbers.append(
                        odd
                    )

            if len(numbers) == 3:

                value = (
                    numbers[0],
                    numbers[1],
                    numbers[2],
                )

                if value not in result:
                    result.append(
                        value
                    )

            for value in obj:
                scan_arrays(
                    value
                )

        elif isinstance(
            obj,
            dict
        ):

            for value in obj.values():
                scan_arrays(
                    value
                )

    scan_arrays(
        data
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
# API 응답 분석
# ============================================================

def inspect_api_response(
    response
):

    if response is None:
        return None

    text = response.text

    data = try_json(
        text
    )

    ids = set()

    teams = []
    scores = []
    odds = []

    if data is not None:

        ids.update(
            extract_match_ids_from_json(
                data
            )
        )

        team = extract_teams_from_json(
            data
        )

        if team:
            teams.append(
                team
            )

        score = extract_score_from_json(
            data
        )

        if score:
            scores.append(
                score
            )

        odds.extend(
            extract_odds_from_json(
                data
            )
        )

    # JSON이 아니어도 HTML/JS 검색
    ids.update(
        extract_ids_from_text(
            text
        )
    )

    html_teams = extract_teams(
        text
    )

    for team in html_teams:
        if team not in teams:
            teams.append(
                team
            )

    html_score = extract_score(
        text
    )

    if html_score:
        scores.append(
            html_score
        )

    odds.extend(
        extract_odds(
            text
        )
    )

    unique_odds = []

    for value in odds:

        if value not in unique_odds:
            unique_odds.append(
                value
            )

    return {
        "url":
            response.url,

        "status_code":
            response.status_code,

        "text":
            text,

        "json":
            data,

        "ids":
            ids,

        "teams":
            teams,

        "scores":
            scores,

        "odds":
            unique_odds,
    }


# ============================================================
# API 호출
# ============================================================

def fetch_api_candidates(
    page,
    date_string,
    log_callback=None,
):

    results = []

    api_urls = list(
        page.get(
            "apis",
            []
        )
    )

    if not api_urls:
        return results

    log(
        log_callback,
        f"🔌 API 실제 호출 시작: {len(api_urls)}개",
    )

    for index, api_url in enumerate(
        api_urls[:30],
        1,
    ):

        # 날짜가 URL에 없으면 후보 파라미터도 시도
        urls_to_try = [
            api_url
        ]

        parsed = urlparse(
            api_url
        )

        query = parse_qs(
            parsed.query
        )

        has_date = any(
            key.lower()
            in {
                "date",
                "day",
                "matchdate",
                "startdate",
            }
            for key in query
        )

        if not has_date:

            urls_to_try.append(
                api_url
                + (
                    "&"
                    if "?" in api_url
                    else "?"
                )
                + f"date={date_string}"
            )

        for url in urls_to_try:

            log(
                log_callback,
                f"[API {index}] {url}",
            )

            response = request_get(
                url,
                referer=page["url"],
            )

            if response is None:

                log(
                    log_callback,
                    "  ❌ 응답 없음",
                )

                continue

            log(
                log_callback,
                (
                    f"  HTTP={response.status_code} "
                    f"bytes={len(response.content):,}"
                ),
            )

            if response.status_code != 200:
                continue

            parsed_result = inspect_api_response(
                response
            )

            if parsed_result is None:
                continue

            if (
                parsed_result["ids"]
                or parsed_result["teams"]
                or parsed_result["odds"]
            ):

                results.append(
                    parsed_result
                )

                log(
                    log_callback,
                    (
                        "  ✅ API 데이터 발견 "
                        f"ID={len(parsed_result['ids'])} "
                        f"팀={len(parsed_result['teams'])} "
                        f"배당={len(parsed_result['odds'])}"
                    ),
                )

                break

    return results


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

            response = request_get(
                url
            )

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
                + len(apis) * 10
                + len(iframes) * 3
                + len(scripts)
                + len(response.content)
                // 100000
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
                or
                score > best["score"]
            ):
                best = candidate

    return best


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

    data = try_json(
        source_html
    )

    if data is not None:

        team = extract_teams_from_json(
            data
        )

        if team:
            teams = [team]

        json_score = (
            extract_score_from_json(
                data
            )
        )

        if json_score:
            score = json_score

        json_odds = (
            extract_odds_from_json(
                data
            )
        )

        if json_odds:
            odds.extend(
                json_odds
            )

    unique_odds = []

    for value in odds:

        if value not in unique_odds:
            unique_odds.append(
                value
            )

    return {
        "match_id":
            match_id,

        "url":
            response.url,

        "html":
            source_html,

        "teams":
            teams[0]
            if teams
            else None,

        "score":
            score,

        "odds":
            unique_odds,

        "size":
            len(response.content),

        "status_code":
            response.status_code,
    }


# ============================================================
# 상세 URL
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

            score_value = 0

            if detail.get(
                "teams"
            ):
                score_value += 10

            if detail.get(
                "odds"
            ):
                score_value += 10

            if detail.get(
                "score"
            ):
                score_value += 5

            if detail.get(
                "size",
                0
            ) > 5000:
                score_value += 2

            detail["_score"] = (
                score_value
            )

            if (
                best is None
                or
                score_value
                > best["_score"]
            ):
                best = detail

            if (
                detail.get("teams")
                and
                detail.get("odds")
            ):
                return detail

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
    log_callback=None,
):

    date_string = normalize_date(
        date_string
    )

    log(
        log_callback,
        "==========================================",
    )

    log(
        log_callback,
        "🔎 7M 실제 경기/API 진단",
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

    source_html = page["html"]

    result["http"] = 200

    result["page_url"] = (
        page["url"]
    )

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

    result["api_candidates"] = (
        page["apis"]
    )

    result["script_urls"] = (
        page["scripts"]
    )

    result["iframe_urls"] = (
        page["iframes"]
    )

    # --------------------------------------------------------
    # JS 크기
    # --------------------------------------------------------

    js_bytes = 0

    for script_url in page["scripts"]:

        response = request_get(
            script_url,
            referer=page["url"],
        )

        if (
            response is not None
            and
            response.status_code == 200
        ):

            js_bytes += len(
                response.content
            )

    result["js_bytes"] = (
        js_bytes
    )

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
    # 일반 링크
    # --------------------------------------------------------

    matches = list(
        page["links"]
    )

    existing_ids = {
        item["id"]
        for item in matches
    }

    # --------------------------------------------------------
    # HTML ID
    # --------------------------------------------------------

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
    # JS 경기 ID
    # --------------------------------------------------------

    js_match_ids = set()

    for script_url in page["scripts"]:

        response = request_get(
            script_url,
            referer=page["url"],
        )

        if (
            response is None
            or
            response.status_code != 200
        ):
            continue

        js_match_ids.update(
            extract_match_ids(
                response.text
            )
        )

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
    # API 실제 호출
    # --------------------------------------------------------

    api_results = (
        fetch_api_candidates(
            page,
            date_string,
            log_callback=log_callback,
        )
    )

    api_ids = set()

    for api_result in api_results:

        api_ids.update(
            api_result.get(
                "ids",
                set()
            )
        )

    log(
        log_callback,
        (
            f"🔌 API에서 발견한 경기 ID: "
            f"{len(api_ids)}"
        ),
    )

    # --------------------------------------------------------
    # API 경기 ID 추가
    # --------------------------------------------------------

    for match_id in sorted(
        api_ids,
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
    # 중복 제거
    # --------------------------------------------------------

    unique = {}

    for item in matches:

        match_id = item.get(
            "id"
        )

        if not match_id:
            continue

        unique[match_id] = item

    matches = list(
        unique.values()
    )

    result["matches"] = matches

    result["match_links"] = len(
        matches
    )

    result["match_ids"] = len(
        matches
    )

    result["match_candidates"] = len(
        matches
    )

    log(
        log_callback,
        (
            f"🎯 최종 경기 후보: "
            f"{len(matches)}"
        ),
    )

    # --------------------------------------------------------
    # 샘플 상세 검사
    # --------------------------------------------------------

    valid = []

    log(
        log_callback,
        "",
    )

    log(
        log_callback,
        "🧪 실제 경기 샘플 검사",
    )

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
            source_url=(
                item.get("url")
                or None
            ),
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
        (
            f"샘플 성공: "
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
# 1일 수집
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
            "❌ 경기 후보 0개",
        )

        log(
            log_callback,
            (
                "⚠️ API 후보는 발견되었지만 "
                "응답에서 경기 ID를 찾지 못했습니다."
            ),
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
            f"🎯 실제 경기 "
            f"{total}개 수집 시작"
        ),
    )

    for index, item in enumerate(
        matches,
        1,
    ):

        match_id = item["id"]

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
                item.get("url")
                or None
            ),
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
            final_odds = (
                odds_list[-1]
            )

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
                f"{home_team} vs "
                f"{away_team} | "
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
        (
            f"🏁 {date_string} "
            f"수집 완료"
        ),
    )

    log(
        log_callback,
        (
            f"경기 저장 대상: "
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

    all_results = []

    current = start

    while current <= end:

        date_string = (
            current.strftime(
                "%Y-%m-%d"
            )
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

    odds_count = sum(
        1
        for x in all_results
        if (
            x.get("home_odds")
            is not None
            and
            x.get("draw_odds")
            is not None
            and
            x.get("away_odds")
            is not None
        )
    )

    result_count = sum(
        1
        for x in all_results
        if x.get("result")
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
            f"총 경기: "
            f"{len(all_results)}"
        ),
    )

    log(
        log_callback,
        (
            f"최종배당: "
            f"{odds_count}"
        ),
    )

    log(
        log_callback,
        (
            f"실제결과: "
            f"{result_count}"
        ),
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
