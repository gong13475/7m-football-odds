# ============================================================
# sevenm_crawler.py
# ⚽ 7M 축구 최종배당 수집기 - 최종 교체본
#
# app.py 수정 불필요
#
# 기능
# - 7M 경기 목록 탐색
# - default / default_odds 페이지 탐색
# - iframe 탐색
# - script / JS 탐색
# - 경기 ID 탐색
# - 실제 경기 상세 페이지 탐색
# - 7M 1X2 배당 탐색
# - Initial / Trend 중 최종값 우선 추출
# - 스코어 / 승무패 추출
# - 날짜별 수집
# - 기존 app.py의 diagnose()/collect() 호환
# ============================================================

import re
import time
import html as html_lib
import requests

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, parse_qs, unquote


# ============================================================
# 기본 설정
# ============================================================

BASE_URL = "https://live.7msport.com"

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
}

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# 7M 시작 페이지
# ============================================================

START_URLS = [
    f"{BASE_URL}/default_en.aspx",
    f"{BASE_URL}/default_kr.aspx",
    f"{BASE_URL}/default_odds_en.aspx",
    f"{BASE_URL}/default_odds_kr.aspx",
]


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

    if value is None:
        return None

    try:

        value = str(value).strip()

        value = value.replace(
            ",",
            "",
        )

        value = value.replace(
            '"',
            "",
        )

        value = value.replace(
            "'",
            "",
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
            str(value).strip()
        )

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

        return value.strftime(
            "%Y-%m-%d"
        )

    value = str(value).strip()

    value = value.replace(
        ".",
        "-",
    )

    value = value.replace(
        "/",
        "-",
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
# URL
# ============================================================

def absolute_url(
    page_url,
    value,
):

    if not value:
        return ""

    value = html_lib.unescape(
        str(value).strip()
    )

    if value.startswith(
        "javascript:"
    ):
        return ""

    return urljoin(
        page_url,
        value,
    )


# ============================================================
# 링크 추출
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

            if not href:
                continue

            url = absolute_url(
                page_url,
                href,
            )

            if not url:
                continue

            if url not in result:
                result.append(url)

    except Exception:
        pass

    return result


# ============================================================
# 경기 ID 추출
# ============================================================

def extract_match_id_from_url(
    url
):

    if not url:
        return None

    decoded = unquote(
        str(url)
    )

    # query
    patterns = [

        r"[?&](?:id|mid|matchid|match_id)="
        r"(\d{4,12})",

        r"[?&](?:gameid|game_id)="
        r"(\d{4,12})",

        r"[?&](?:eventid|event_id)="
        r"(\d{4,12})",

        r"[?&](?:fixtureid|fixture_id)="
        r"(\d{4,12})",

        r"[?&](?:fid)="
        r"(\d{4,12})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            decoded,
            re.I,
        )

        if match:
            return match.group(1)

    # path
    patterns = [

        r"/match(?:es)?/"
        r"(\d{4,12})",

        r"/game(?:s)?/"
        r"(\d{4,12})",

        r"/event(?:s)?/"
        r"(\d{4,12})",

        r"/fixture(?:s)?/"
        r"(\d{4,12})",

        r"/odds/[^/?]+"
        r"(?:\.shtml)?\?id="
        r"(\d{4,12})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            decoded,
            re.I,
        )

        if match:
            return match.group(1)

    return None


# ============================================================
# HTML 경기 ID
# ============================================================

def extract_match_ids(
    source_html
):

    ids = set()

    patterns = [

        # data
        r'data-(?:match-id|matchid|match_id)'
        r'\s*=\s*["\'](\d{4,12})["\']',

        r'data-(?:game-id|gameid|game_id)'
        r'\s*=\s*["\'](\d{4,12})["\']',

        r'data-(?:event-id|eventid|event_id)'
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

        # URL
        r'(?:match|game|event|fixture)'
        r'[^0-9]{0,20}'
        r'(\d{5,12})',
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
                        10000
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
# 경기 링크 추출
# ============================================================

def extract_real_match_links(
    page_url,
    source_html,
):

    result = []

    for url in extract_links(
        page_url,
        source_html,
    ):

        match_id = (
            extract_match_id_from_url(
                url
            )
        )

        if not match_id:
            continue

        low = url.lower()

        if any(
            ext in low
            for ext in (
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

        result.append({
            "id": match_id,
            "url": url,
        })

    unique = {}

    for item in result:

        unique[
            item["id"]
        ] = item

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

            url = absolute_url(
                page_url,
                src,
            )

            if url and url not in result:
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

            if not src:
                continue

            url = absolute_url(
                page_url,
                src,
            )

            if url and url not in result:
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

    patterns = [

        r'https?://[^"\'\s<>]+',

        r'["\']([^"\']{1,500}'
        r'(?:/api/|/ajax/|/data/|'
        r'/json/|/service/|/interface/)'
        r'[^"\']*)["\']',

        r'["\']([^"\']{1,500}'
        r'(?:\.json|\.ashx|\.asmx)'
        r'[^"\']*)["\']',
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
                    tuple,
                ):
                    value = value[0]

                value = html_lib.unescape(
                    str(value)
                )

                if value.startswith(
                    ("//", "/")
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
                    ext in low
                    for ext in (
                        ".png",
                        ".jpg",
                        ".jpeg",
                        ".gif",
                        ".svg",
                        ".css",
                    )
                ):
                    continue

                if any(
                    x in low
                    for x in (
                        "/api/",
                        "/ajax/",
                        "/data/",
                        "/json/",
                        "/service/",
                        "/interface/",
                        ".json",
                        ".ashx",
                        ".asmx",
                    )
                ):

                    if value not in result:
                        result.append(
                            value
                        )

        except Exception:
            pass

    return result


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
                    and 2 <= len(away) <= 150
                    and home.lower()
                    not in (
                        "home",
                        "home team",
                    )
                    and away.lower()
                    not in (
                        "away",
                        "away team",
                    )
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

    return result


# ============================================================
# 화면에서 팀명 추출
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
                    and away is not None
                ):
                    return (
                        home,
                        away,
                    )

        except Exception:
            pass

    # HTML 일반 점수
    score_patterns = [

        r">\s*(\d{1,2})\s*-\s*(\d{1,2})\s*<",

        r">\s*(\d{1,2})\s*:\s*(\d{1,2})\s*<",

        r"\b(\d{1,2})\s*-\s*(\d{1,2})\b",
    ]

    for pattern in score_patterns:

        try:

            match = re.search(
                pattern,
                source_html,
                re.I,
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
# 7M 1X2 배당
# ============================================================

def extract_odds(
    source_html
):

    candidates = []

    # --------------------------------------------------------
    # JSON 형태
    # --------------------------------------------------------

    json_patterns = [

        (
            r'"homeOdds"\s*:\s*'
            r'([0-9]+(?:\.[0-9]+)?)'
            r'.{0,1500}?'
            r'"drawOdds"\s*:\s*'
            r'([0-9]+(?:\.[0-9]+)?)'
            r'.{0,1500}?'
            r'"awayOdds"\s*:\s*'
            r'([0-9]+(?:\.[0-9]+)?)'
        ),

        (
            r'"odds1"\s*:\s*'
            r'([0-9]+(?:\.[0-9]+)?)'
            r'.{0,1500}?'
            r'"oddsX"\s*:\s*'
            r'([0-9]+(?:\.[0-9]+)?)'
            r'.{0,1500}?'
            r'"odds2"\s*:\s*'
            r'([0-9]+(?:\.[0-9]+)?)'
        ),

        (
            r'"home"\s*:\s*'
            r'([0-9]+(?:\.[0-9]+)?)'
            r'.{0,1500}?'
            r'"draw"\s*:\s*'
            r'([0-9]+(?:\.[0-9]+)?)'
            r'.{0,1500}?'
            r'"away"\s*:\s*'
            r'([0-9]+(?:\.[0-9]+)?)'
        ),
    ]

    for pattern in json_patterns:

        try:

            found = re.findall(
                pattern,
                source_html,
                re.I | re.S,
            )

            for item in found:

                if len(item) != 3:
                    continue

                odds = (
                    valid_odd(item[0]),
                    valid_odd(item[1]),
                    valid_odd(item[2]),
                )

                if all(
                    x is not None
                    for x in odds
                ):
                    candidates.append(
                        odds
                    )

        except Exception:
            pass

    # --------------------------------------------------------
    # 7M HTML 테이블의 1x2 행
    #
    # 실제 페이지에는
    #
    # 1x2 | 3.25 | 3.40 | 1.95
    #
    # 형태의 데이터가 노출될 수 있음.
    # --------------------------------------------------------

    try:

        soup = BeautifulSoup(
            source_html,
            "html.parser",
        )

        # table row 우선
        for row in soup.find_all(
            ["tr", "div"]
        ):

            text = clean_text(
                row.get_text(" ")
            )

            if not text:
                continue

            low = text.lower()

            if (
                "1x2" not in low
                and "1 x 2" not in low
                and "1x2" not in low.replace(
                    " ",
                    "",
                )
            ):
                continue

            numbers = re.findall(
                r"(?<![\d.])"
                r"\d{1,3}(?:\.\d{1,3})?"
                r"(?![\d.])",
                text,
            )

            values = []

            for number in numbers:

                odd = valid_odd(
                    number
                )

                if odd is not None:
                    values.append(
                        odd
                    )

            # 1X2는 최소 3개
            if len(values) >= 3:

                # 첫 3개
                for i in range(
                    0,
                    min(
                        len(values) - 2,
                        10,
                    ),
                ):

                    candidate = (
                        values[i],
                        values[i + 1],
                        values[i + 2],
                    )

                    # 너무 이상한 조합 제외
                    if all(
                        1.01 <= x <= 100
                        for x in candidate
                    ):
                        candidates.append(
                            candidate
                        )

    except Exception:
        pass

    # --------------------------------------------------------
    # 일반 텍스트
    # --------------------------------------------------------

    text = clean_text(
        BeautifulSoup(
            source_html,
            "html.parser",
        ).get_text(" ")
    )

    # 1x2 뒤의 숫자 3개
    pattern = re.compile(
        r"1\s*x\s*2"
        r".{0,1000}?"
        r"(\d+(?:\.\d+)?)"
        r"\s+"
        r"(\d+(?:\.\d+)?)"
        r"\s+"
        r"(\d+(?:\.\d+)?)",
        re.I | re.S,
    )

    for match in pattern.finditer(
        text
    ):

        odds = (
            valid_odd(match.group(1)),
            valid_odd(match.group(2)),
            valid_odd(match.group(3)),
        )

        if all(
            x is not None
            for x in odds
        ):
            candidates.append(
                odds
            )

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

    unique = []

    for item in candidates:

        rounded = tuple(
            round(x, 3)
            for x in item
        )

        if rounded not in unique:
            unique.append(
                rounded
            )

    return [
        tuple(x)
        for x in unique
    ]


# ============================================================
# 7M 최종배당 선택
# ============================================================

def choose_final_odds(
    odds_list
):

    if not odds_list:
        return None

    # 현재 7M HTML의 마지막/최신 데이터가
    # 가장 최근 값일 가능성이 높으므로 마지막 후보 사용
    return odds_list[-1]


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
# 상세 URL 후보
# ============================================================

def candidate_match_urls(
    match_id
):

    return [

        # 실제 7M Odds 페이지 우선
        f"{BASE_URL}/odds/en/1x2.shtml?id={match_id}",
        f"{BASE_URL}/odds/en/1X2.shtml?id={match_id}",

        # 일반 odds
        f"{BASE_URL}/odds/en/odds.shtml?id={match_id}",
        f"{BASE_URL}/odds/en/index.shtml?id={match_id}",

        # 상세
        f"{BASE_URL}/match.aspx?id={match_id}",
        f"{BASE_URL}/match.shtml?id={match_id}",

        f"{BASE_URL}/match_data.aspx?id={match_id}",
        f"{BASE_URL}/match_data.shtml?id={match_id}",

        f"{BASE_URL}/game.aspx?id={match_id}",
        f"{BASE_URL}/game.shtml?id={match_id}",

        f"{BASE_URL}/event.aspx?id={match_id}",
        f"{BASE_URL}/event.shtml?id={match_id}",
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

        teams = extract_teams_from_visible_text(
            source_html
        )

    score = extract_score(
        source_html
    )

    odds = extract_odds(
        source_html
    )

    final_odds = choose_final_odds(
        odds
    )

    # 점수/팀/배당이 하나라도 있으면
    # 유효한 상세 후보
    quality = 0

    if teams:
        quality += 30

    if score:
        quality += 20

    if final_odds:
        quality += 40

    if len(response.content) > 5000:
        quality += 5

    low_url = response.url.lower()

    if "/odds/" in low_url:
        quality += 10

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
        "final_odds": final_odds,
        "size": len(
            response.content
        ),
        "status_code":
            response.status_code,
        "_quality":
            quality,
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

            if (
                best is None
                or detail["_quality"]
                > best["_quality"]
            ):
                best = detail

            # 팀 + 배당 확보시 성공
            if (
                detail.get("teams")
                and detail.get(
                    "final_odds"
                )
            ):
                return detail

        if attempt < retry_count:
            time.sleep(
                retry_delay
            )

    return best


# ============================================================
# 시작 페이지 후보
# ============================================================

def start_page_candidates(
    date_string
):

    urls = []

    # 날짜를 쿼리로 전달
    for base in START_URLS:

        urls.append(
            f"{base}?date={date_string}"
        )

        urls.append(
            f"{base}?date={date_string}"
            f"&line=no"
        )

        urls.append(
            f"{base}?date={date_string}"
            f"&view=all"
        )

        urls.append(
            f"{base}?date={date_string}"
            f"&line=no&view=all"
        )

    # 기본 페이지
    urls.extend(
        START_URLS
    )

    unique = []

    for url in urls:

        if url not in unique:
            unique.append(
                url
            )

    return unique


# ============================================================
# 시작 페이지
# ============================================================

def get_start_page(
    date_string,
    log_callback=None,
):

    best = None

    for url in start_page_candidates(
        date_string
    ):

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

        # iframe 내부도 경기 ID 확인
        iframe_ids = set()

        for iframe_url in iframes[:10]:

            iframe_response = request_get(
                iframe_url,
                referer=response.url,
            )

            if (
                iframe_response is None
                or iframe_response.status_code != 200
            ):
                continue

            iframe_ids.update(
                extract_match_ids(
                    iframe_response.text
                )
            )

        ids.update(
            iframe_ids
        )

        score = (
            len(links) * 50
            + len(ids) * 30
            + len(iframes) * 10
            + len(apis) * 5
            + len(scripts)
            + len(response.content)
            // 100000
        )

        # odds 페이지는 우선순위 상승
        if "default_odds" in response.url:
            score += 100

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
        "🔎 7M 실제 연결 / 경기 진단",
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
        log_callback,
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
            "❌ 7M 시작 페이지를 찾지 못했습니다.",
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
    ][:30]:

        try:

            script_response = request_get(
                script_url,
                referer=page[
                    "url"
                ],
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
    # 경기 링크
    # --------------------------------------------------------

    matches = list(
        page["links"]
    )

    existing_ids = {
        item["id"]
        for item in matches
    }

    # HTML ID
    for match_id in sorted(
        page["ids"],
        key=lambda x: int(x),
    ):

        if match_id in existing_ids:
            continue

        matches.append({
            "id":
                match_id,

            "url":
                "",
        })

    # --------------------------------------------------------
    # JS 내부 ID
    # --------------------------------------------------------

    js_match_ids = set()

    for script_url in page[
        "scripts"
    ][:30]:

        try:

            script_response = request_get(
                script_url,
                referer=page[
                    "url"
                ],
            )

            if (
                script_response is None
                or script_response.status_code != 200
            ):
                continue

            js_match_ids.update(
                extract_match_ids(
                    script_response.text
                )
            )

        except Exception:
            pass

    for match_id in sorted(
        js_match_ids,
        key=lambda x: int(x),
    ):

        if any(
            item["id"] == match_id
            for item in matches
        ):
            continue

        matches.append({
            "id":
                match_id,

            "url":
                "",
        })

    # --------------------------------------------------------
    # iframe 경기 ID
    # --------------------------------------------------------

    for iframe_url in page[
        "iframes"
    ][:10]:

        try:

            iframe_response = request_get(
                iframe_url,
                referer=page[
                    "url"
                ],
            )

            if (
                iframe_response is None
                or iframe_response.status_code != 200
            ):
                continue

            iframe_ids = extract_match_ids(
                iframe_response.text
            )

            for match_id in iframe_ids:

                if any(
                    x["id"] == match_id
                    for x in matches
                ):
                    continue

                matches.append({
                    "id":
                        match_id,

                    "url":
                        iframe_url,
                })

        except Exception:
            pass

    # --------------------------------------------------------
    # 중복
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
    ] = len(
        matches
    )

    result[
        "match_ids"
    ] = len(
        matches
    )

    result[
        "match_candidates"
    ] = len(
        matches
    )

    log(
        log_callback,
        f"발견 후보: {len(matches)}",
    )

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    if page[
        "apis"
    ]:

        log(
            log_callback,
            "🔌 API 후보:",
        )

        for api in page[
            "apis"
        ][:15]:

            log(
                log_callback,
                f"  {api}",
            )

    # --------------------------------------------------------
    # 실제 경기 샘플
    # --------------------------------------------------------

    log(
        log_callback,
        "",
    )

    log(
        log_callback,
        "🧪 실제 경기 상세 샘플 검사",
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
                item.get("url")
                or None
            ),
            retry_count=1,
            retry_delay=0.3,
        )

        if detail is None:

            log(
                log_callback,
                "  ❌ 상세 페이지 없음",
            )

            continue

        teams = detail.get(
            "teams"
        )

        odds = detail.get(
            "final_odds"
        )

        score = detail.get(
            "score"
        )

        log(
            log_callback,
            (
                f"  팀={teams or '-'} | "
                f"최종배당={odds or '-'} | "
                f"스코어={score or '-'} | "
                f"결과={make_result(score) or '-'}"
            ),
        )

        if (
            teams
            or odds
            or score
        ):
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
            f"상세 확인 성공: "
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
            "❌ 경기 후보를 발견하지 못했습니다.",
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
            f"🎯 7M 경기 "
            f"{total}개 후보 수집 시작"
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
                f"ID={match_id}"
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

        final_odds = detail.get(
            "final_odds"
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

        result_value = make_result(
            score
        )

        # ----------------------------------------------------
        # 최소 검증
        #
        # 팀도 없고 배당도 없고 스코어도 없으면
        # 실제 경기로 저장하지 않음.
        # ----------------------------------------------------

        if (
            not home_team
            and not away_team
            and not final_odds
            and not score
        ):

            log(
                log_callback,
                "  ⚠️ 경기 데이터 부족 → 제외",
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
                ),
        }

        results.append(
            item_result
        )

        log(
            log_callback,
            (
                "  ✅ "
                f"{home_team or '?'} "
                f"vs "
                f"{away_team or '?'} | "
                f"배당="
                f"{final_odds or '-'} | "
                f"결과="
                f"{result_value or '-'}"
            ),
        )

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

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
        f"경기: {len(results)}",
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
        f"1X2 최종배당: {odds_count}",
    )

    log(
        log_callback,
        f"실제결과: {result_count}",
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

        raise ValueError(
            "시작 날짜가 종료 날짜보다 늦습니다."
        )

    all_results = []

    current = start

    while current <= end:

        date_string = current.strftime(
            "%Y-%m-%d"
        )

        log(
            log_callback,
            "",
        )

        log(
            log_callback,
            (
                f"📅 날짜 처리: "
                f"{date_string}"
            ),
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

    # --------------------------------------------------------
    # 전체 중복 제거
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 통계
    # --------------------------------------------------------

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
        "",
    )

    log(
        log_callback,
        "==========================================",
    )

    log(
        log_callback,
        "🏆 7M 전체 수집 완료",
    )

    log(
        log_callback,
        f"총 경기: {len(all_results)}",
    )

    log(
        log_callback,
        f"최종 1X2 배당: {odds_count}",
    )

    log(
        log_callback,
        f"실제 결과: {result_count}",
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
        "=========================================="
    )

    print(
        "7M CRAWLER TEST"
    )

    print(
        f"DATE: {today}"
    )

    print(
        "=========================================="
    )

    result = diagnose(
        today,
        log_callback=print,
    )

    print(
        ""
    )

    print(
        "TEST RESULT:"
    )

    print(
        result
                    )
