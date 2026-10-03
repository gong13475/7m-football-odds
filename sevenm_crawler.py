# ============================================================
# sevenm_crawler.py
# ⚽ 7M 축구 최종배당 수집기
#
# 최종 수정본
#
# 기능
# ------------------------------------------------------------
# 1. 7M 경기 페이지 탐색
# 2. 경기 ID 범위 수집
# 3. 경기 정보 수집
# 4. 홈팀 / 원정팀
# 5. 경기 날짜
# 6. 최종 경기 결과
# 7. 1X2 승 / 무 / 패 배당
# 8. 업체명별 배당 저장 지원
# 9. 중복 경기 확인
# 10. 백그라운드 수집
# 11. 수집 시작 / 중지
# 12. 진행률
# 13. 성공 / 중복 / 실패
# 14. 로그
# 15. database.py 자동 연결
#
# app.py에서는
#
# sevenm_crawler.start_background_collection()
#
# sevenm_crawler.stop_collection()
#
# sevenm_crawler.get_status()
#
# 등을 사용할 수 있음
# ============================================================

import re
import json
import time
import threading
from datetime import datetime
from urllib.parse import urljoin

import requests

import database


# ============================================================
# 기본 설정
# ============================================================

BASE_URL = "https://www.7m.com.cn"

REQUEST_DELAY = 0.5
TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Linux; Android 13; SM-S901N) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0.0.0 "
        "Mobile Safari/537.36"
    ),
    "Accept": (
        "text/html,"
        "application/xhtml+xml,"
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


# ============================================================
# Session
# ============================================================

session = requests.Session()

session.headers.update(
    HEADERS
)


# ============================================================
# 수집 상태
# ============================================================

job = {
    "running": False,
    "finished": False,

    "current": 0,
    "total": 0,

    "success": 0,
    "exists": 0,
    "failed": 0,

    "odds": 0,

    "start_id": 0,
    "end_id": 0,

    "last_completed_id": 0,

    "result": "",
    "error": "",

    "start_time": "",
    "end_time": "",

    "selected_companies": [],

    "log": [],
}


job_lock = threading.Lock()

worker_thread = None


# ============================================================
# 로그
# ============================================================

def add_log(message):

    now = datetime.now().strftime(
        "%H:%M:%S"
    )

    line = f"[{now}] {message}"

    with job_lock:

        job["log"].append(line)

        if len(job["log"]) > 500:
            job["log"] = job["log"][-500:]


def get_logs():

    with job_lock:
        return list(job["log"])


def clear_logs():

    with job_lock:
        job["log"] = []


# ============================================================
# 상태
# ============================================================

def get_status():

    with job_lock:
        return dict(job)


def is_running():

    with job_lock:
        return bool(
            job["running"]
        )


# ============================================================
# 수집 중지
# ============================================================

def stop_collection():

    with job_lock:
        job["running"] = False

    add_log(
        "⛔ 수집 중지 요청"
    )

    return True


# ============================================================
# 숫자 변환
# ============================================================

def to_int(
    value,
    default=0
):

    try:

        if value is None:
            return default

        text = str(
            value
        ).strip()

        match = re.search(
            r"-?\d+",
            text
        )

        if not match:
            return default

        return int(
            match.group()
        )

    except Exception:

        return default


def to_float(value):

    try:

        if value is None:
            return None

        text = str(
            value
        ).strip()

        text = text.replace(
            ",",
            ""
        )

        match = re.search(
            r"\d+(?:\.\d+)?",
            text
        )

        if not match:
            return None

        number = float(
            match.group()
        )

        if number <= 0:
            return None

        return number

    except Exception:

        return None


# ============================================================
# 안전한 GET
# ============================================================

def safe_get(
    url,
    params=None,
    timeout=TIMEOUT
):

    try:

        response = session.get(
            url,
            params=params,
            timeout=timeout,
            allow_redirects=True,
        )

        if response.status_code != 200:

            return None

        return response

    except Exception:

        return None


# ============================================================
# 경기 ID 추출
# ============================================================

def extract_match_ids(
    text
):

    if not text:
        return []

    ids = set()

    patterns = [

        # /match/123456
        r"/match/[^\"'\s]*?(\d{5,9})",

        # id=123456
        r"[?&]"
        r"(?:id|matchid|match_id|"
        r"schedule_id|scheduleId)"
        r"="
        r"(\d{5,9})",

        # "matchId":123456
        r"['\"]"
        r"(?:id|matchId|match_id|"
        r"scheduleId|schedule_id)"
        r"['\"]"
        r"\s*[:=]\s*"
        r"['\"]?"
        r"(\d{5,9})",

        # matchId = 123456
        r"\bmatch[_-]?id"
        r"\s*[:=]\s*"
        r"['\"]?"
        r"(\d{5,9})",

        # scheduleId = 123456
        r"\bschedule[_-]?id"
        r"\s*[:=]\s*"
        r"['\"]?"
        r"(\d{5,9})",

        # gameId = 123456
        r"\bgame[_-]?id"
        r"\s*[:=]\s*"
        r"['\"]?"
        r"(\d{5,9})",
    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                text,
                flags=re.I
            )

            for value in found:

                number = to_int(
                    value
                )

                if (
                    10000
                    <= number
                    <= 999999999
                ):
                    ids.add(
                        number
                    )

        except Exception:
            continue

    return sorted(
        ids
    )


# ============================================================
# URL 추출
# ============================================================

def extract_urls(
    html
):

    if not html:
        return []

    urls = set()

    patterns = [

        r"""href\s*=\s*["']([^"']+)["']""",

        r"""src\s*=\s*["']([^"']+)["']""",

        r"""url\s*[:=]\s*["']([^"']+)["']""",

    ]

    for pattern in patterns:

        try:

            values = re.findall(
                pattern,
                html,
                flags=re.I
            )

            for value in values:

                value = value.strip()

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
                        BASE_URL,
                        value
                    )

                if value.startswith(
                    "http"
                ):

                    urls.add(
                        value
                    )

        except Exception:
            continue

    return list(
        urls
    )


# ============================================================
# API 후보 찾기
# ============================================================

def extract_api_candidates(
    html
):

    if not html:
        return []

    candidates = set()

    urls = extract_urls(
        html
    )

    for url in urls:

        low = url.lower()

        keywords = [
            "api",
            "ajax",
            "json",
            "odds",
            "match",
            "schedule",
            "game",
        ]

        if any(
            word in low
            for word in keywords
        ):

            candidates.add(
                url
            )

    patterns = [

        r"""["']([^"']*
        (?:api|ajax|json|odds|match|schedule)
        [^"']*)["']""",

    ]

    for pattern in patterns:

        try:

            values = re.findall(
                pattern,
                html,
                flags=re.I | re.X
            )

            for value in values:

                value = value.strip()

                if value.startswith(
                    "/"
                ):

                    value = urljoin(
                        BASE_URL,
                        value
                    )

                if value.startswith(
                    "http"
                ):

                    candidates.add(
                        value
                    )

        except Exception:
            continue

    return list(
        candidates
    )


# ============================================================
# 7M 시작 페이지 탐색
# ============================================================

def discover_7m():

    urls = [

        BASE_URL,

        "https://www.7m.com.cn/",

        "https://www.7m.com.cn/index.shtml",

        "https://data.7m.com.cn/",

        "https://data.7m.com.cn/database/",

        "https://am.7m.com.cn/en/odds.shtml",

    ]

    all_ids = set()

    all_api = set()

    for url in urls:

        if not is_running():
            break

        response = safe_get(
            url
        )

        if not response:
            continue

        html = response.text

        ids = extract_match_ids(
            html
        )

        apis = extract_api_candidates(
            html
        )

        all_ids.update(
            ids
        )

        all_api.update(
            apis
        )

        add_log(
            f"🔎 7M 탐색 "
            f"{len(ids)}개 ID / "
            f"API {len(apis)}개"
        )

    return (
        sorted(all_ids),
        sorted(all_api)
    )


# ============================================================
# 경기 URL 후보
# ============================================================

def match_url_candidates(
    match_id
):

    mid = str(
        match_id
    )

    return [

        f"{BASE_URL}/match/{mid}",

        f"{BASE_URL}/match/{mid}/",

        f"{BASE_URL}/match/data-{mid}",

        f"{BASE_URL}/match/data-{mid}/",

        f"{BASE_URL}/match/detail-{mid}",

        f"{BASE_URL}/match/detail-{mid}/",

        f"{BASE_URL}/match/{mid}.html",

        f"https://www.7m.com.cn/match/{mid}",

        f"https://www.7m.com.cn/match/{mid}/",

    ]


# ============================================================
# 경기 페이지 가져오기
# ============================================================

def get_match_page(
    match_id
):

    for url in match_url_candidates(
        match_id
    ):

        if not is_running():
            return (
                None,
                None
            )

        response = safe_get(
            url
        )

        if not response:
            continue

        html = response.text

        if len(html) < 100:
            continue

        return (
            url,
            html
        )

    return (
        None,
        None
    )


# ============================================================
# JSON 재귀 탐색
# ============================================================

def walk_json(
    obj,
    path=""
):

    if isinstance(
        obj,
        dict
    ):

        yield (
            obj,
            path
        )

        for key, value in obj.items():

            new_path = (
                f"{path}.{key}"
                if path
                else str(key)
            )

            yield from walk_json(
                value,
                new_path
            )

    elif isinstance(
        obj,
        list
    ):

        for index, value in enumerate(
            obj
        ):

            new_path = (
                f"{path}[{index}]"
            )

            yield from walk_json(
                value,
                new_path
            )


# ============================================================
# 업체명 정규화
# ============================================================

def normalize_company_name(
    name
):

    if name is None:
        return ""

    value = str(
        name
    ).strip()

    if not value:
        return ""

    low = value.lower()

    mapping = {

        "macau": "마카오",
        "macao": "마카오",
        "macauslot": "마카오",

        "bet365": "Bet365",

        "18bet": "18Bet",

        "sbobet": "Sbobet",
        "sbo": "Sbobet",

        "williamhill": "William Hill",
        "william hill": "William Hill",

        "188bet": "188Bet",

        "ladbrokes": "Ladbrokes",

        "bwin": "Bwin",

        "betway": "Betway",

        "10bet": "10Bet",

        "unibet": "Unibet",

    }

    if low in mapping:
        return mapping[low]

    return value


# ============================================================
# 업체명 추출
# ============================================================

def find_company_name(
    item=None,
    text=""
):

    if isinstance(
        item,
        dict
    ):

        keys = [

            "company",

            "companyName",

            "bookmaker",

            "bookmakerName",

            "corp",

            "corpName",

            "name",

            "cn",

            "title",

        ]

        for key in keys:

            if key not in item:
                continue

            value = item.get(
                key
            )

            if value is None:
                continue

            value = str(
                value
            ).strip()

            if value:

                return normalize_company_name(
                    value
                )

    patterns = [

        r'"companyName"\s*:\s*"([^"]+)"',

        r'"bookmakerName"\s*:\s*"([^"]+)"',

        r'"corpName"\s*:\s*"([^"]+)"',

        r'"company"\s*:\s*"([^"]+)"',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.I
        )

        if match:

            return normalize_company_name(
                match.group(1)
            )

    return "7M"


# ============================================================
# 팀명 추출
# ============================================================

def find_team_names(
    text
):

    if not text:
        return (
            "",
            ""
        )

    patterns = [

        (
            r'"homeTeam"\s*:\s*"([^"]+)"',
            r'"awayTeam"\s*:\s*"([^"]+)"',
        ),

        (
            r'"home_name"\s*:\s*"([^"]+)"',
            r'"away_name"\s*:\s*"([^"]+)"',
        ),

        (
            r'"homeName"\s*:\s*"([^"]+)"',
            r'"awayName"\s*:\s*"([^"]+)"',
        ),

        (
            r'"home"\s*:\s*"([^"]+)"',
            r'"away"\s*:\s*"([^"]+)"',
        ),

        (
            r'"homeTeamName"\s*:\s*"([^"]+)"',
            r'"awayTeamName"\s*:\s*"([^"]+)"',
        ),

    ]

    for home_pattern, away_pattern in patterns:

        hm = re.search(
            home_pattern,
            text,
            flags=re.I
        )

        am = re.search(
            away_pattern,
            text,
            flags=re.I
        )

        if hm and am:

            home = hm.group(
                1
            ).strip()

            away = am.group(
                1
            ).strip()

            if home and away:

                return (
                    home,
                    away
                )

    return (
        "",
        ""
    )


# ============================================================
# HTML 팀명 추출
# ============================================================

def find_team_names_html(
    html
):

    if not html:
        return (
            "",
            ""
        )

    patterns = [

        (
            r'class=["\'][^"\']*'
            r'(?:home|team-home)'
            r'[^"\']*["\'][^>]*>'
            r'(.*?)<',

            r'class=["\'][^"\']*'
            r'(?:away|team-away)'
            r'[^"\']*["\'][^>]*>'
            r'(.*?)<',
        ),

        (
            r'data-home=["\']'
            r'([^"\']+)'
            r'["\']',

            r'data-away=["\']'
            r'([^"\']+)'
            r'["\']',
        ),

    ]

    for home_pattern, away_pattern in patterns:

        hm = re.search(
            home_pattern,
            html,
            flags=re.I | re.S
        )

        am = re.search(
            away_pattern,
            html,
            flags=re.I | re.S
        )

        if hm and am:

            home = re.sub(
                r"<.*?>",
                "",
                hm.group(1)
            )

            away = re.sub(
                r"<.*?>",
                "",
                am.group(1)
            )

            home = re.sub(
                r"\s+",
                " ",
                home
            ).strip()

            away = re.sub(
                r"\s+",
                " ",
                away
            ).strip()

            if home and away:

                return (
                    home,
                    away
                )

    return (
        "",
        ""
    )


# ============================================================
# 점수 추출
# ============================================================

def extract_score(
    text
):

    if not text:
        return (
            None,
            None
        )

    patterns = [

        (
            r'"homeScore"\s*:\s*'
            r'(\d+)'
            r'.*?'
            r'"awayScore"\s*:\s*'
            r'(\d+)'
        ),

        (
            r'"home_score"\s*:\s*'
            r'(\d+)'
            r'.*?'
            r'"away_score"\s*:\s*'
            r'(\d+)'
        ),

        (
            r'"homeGoals"\s*:\s*'
            r'(\d+)'
            r'.*?'
            r'"awayGoals"\s*:\s*'
            r'(\d+)'
        ),

        (
            r'"hs"\s*:\s*'
            r'(\d+)'
            r'.*?'
            r'"as"\s*:\s*'
            r'(\d+)'
        ),

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.I | re.S
        )

        if match:

            return (
                to_int(
                    match.group(1)
                ),
                to_int(
                    match.group(2)
                )
            )

    return (
        None,
        None
    )


# ============================================================
# 결과 판정
# ============================================================

def calculate_result(
    home_score,
    away_score
):

    if (
        home_score is None
        or away_score is None
    ):
        return ""

    if home_score > away_score:
        return "승"

    if home_score < away_score:
        return "패"

    return "무"


# ============================================================
# 날짜 추출
# ============================================================

def extract_match_date(
    text
):

    patterns = [

        r'"matchDate"\s*:\s*"([^"]+)"',

        r'"match_date"\s*:\s*"([^"]+)"',

        r'"startTime"\s*:\s*"([^"]+)"',

        r'"date"\s*:\s*"([^"]+)"',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.I
        )

        if match:

            return match.group(
                1
            ).strip()

    return ""


# ============================================================
# 1X2 배당값 확인
# ============================================================

def valid_odd(
    value
):

    number = to_float(
        value
    )

    if number is None:
        return False

    return (
        1.01
        <= number
        <= 100.0
    )


# ============================================================
# JSON 1X2 탐색
# ============================================================

def find_odds_from_json(
    obj
):

    found = []

    for item, path in walk_json(
        obj
    ):

        if not isinstance(
            item,
            dict
        ):
            continue

        home = None
        draw = None
        away = None

        home_keys = [
            "homeOdds",
            "homeOdd",
            "home_odd",
            "home",
            "win",
            "one",
            "h",
            "u",
        ]

        draw_keys = [
            "drawOdds",
            "drawOdd",
            "draw_odd",
            "draw",
            "x",
            "d",
        ]

        away_keys = [
            "awayOdds",
            "awayOdd",
            "away_odd",
            "away",
            "lose",
            "two",
            "a",
            "g",
        ]

        for key in home_keys:

            if key in item:

                value = to_float(
                    item[key]
                )

                if valid_odd(
                    value
                ):

                    home = value
                    break

        for key in draw_keys:

            if key in item:

                value = to_float(
                    item[key]
                )

                if valid_odd(
                    value
                ):

                    draw = value
                    break

        for key in away_keys:

            if key in item:

                value = to_float(
                    item[key]
                )

                if valid_odd(
                    value
                ):

                    away = value
                    break

        if (
            home is not None
            and draw is not None
            and away is not None
        ):

            company = find_company_name(
                item
            )

            found.append(
                {
                    "company": company,
                    "home": home,
                    "draw": draw,
                    "away": away,
                    "path": path,
                }
            )

    return found


# ============================================================
# 일반적인 3개 배당 패턴
# ============================================================

def extract_odd_triplets(
    text
):

    if not text:
        return []

    results = []

    pattern = (
        r"(?<![\d.])"
        r"(\d{1,2}\.\d{1,3})"
        r"\s*[,/|]\s*"
        r"(\d{1,2}\.\d{1,3})"
        r"\s*[,/|]\s*"
        r"(\d{1,2}\.\d{1,3})"
    )

    matches = re.findall(
        pattern,
        text
    )

    for match in matches:

        values = [
            to_float(
                match[0]
            ),
            to_float(
                match[1]
            ),
            to_float(
                match[2]
            ),
        ]

        if all(
            valid_odd(value)
            for value in values
        ):

            results.append(
                values
            )

    return results


# ============================================================
# 텍스트 배당 탐색
# ============================================================

def find_odds_from_text(
    text
):

    results = []

    triplets = extract_odd_triplets(
        text
    )

    for values in triplets:

        results.append(
            {
                "company": "7M",
                "home": values[0],
                "draw": values[1],
                "away": values[2],
            }
        )

    return results


# ============================================================
# 중복 배당 제거
# ============================================================

def unique_odds(
    odds
):

    result = {}

    for odd in odds:

        company = normalize_company_name(
            odd.get(
                "company",
                "7M"
            )
        )

        home = to_float(
            odd.get(
                "home"
            )
        )

        draw = to_float(
            odd.get(
                "draw"
            )
        )

        away = to_float(
            odd.get(
                "away"
            )
        )

        if not (
            valid_odd(home)
            and valid_odd(draw)
            and valid_odd(away)
        ):
            continue

        key = (
            company,
            round(home, 3),
            round(draw, 3),
            round(away, 3),
        )

        result[key] = {
            "company": company,
            "home": home,
            "draw": draw,
            "away": away,
        }

    return list(
        result.values()
    )


# ============================================================
# 업체 필터
# ============================================================

def filter_companies(
    odds,
    selected_companies
):

    if not selected_companies:
        return odds

    selected = {
        normalize_company_name(
            item
        )
        for item in selected_companies
        if item
    }

    if (
        not selected
        or "전체" in selected
        or "ALL" in selected
    ):
        return odds

    result = []

    for odd in odds:

        company = normalize_company_name(
            odd.get(
                "company",
                ""
            )
        )

        if company in selected:

            result.append(
                odd
            )

    return result


# ============================================================
# 경기 데이터 파싱
# ============================================================

def parse_match_data(
    match_id,
    html,
    selected_companies=None
):

    data = {

        "schedule_id": int(
            match_id
        ),

        "match_date": "",

        "home_team": "",

        "away_team": "",
