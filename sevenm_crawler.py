# ============================================================
# sevenm_crawler.py
# 7M 축구 최종배당 수집기
# ============================================================

import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse


# ============================================================
# 기본 설정
# ============================================================

BASE_URL = "https://live.7msport.com"

DATA_URL = "https://data.7msport.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 16; SM-S901N) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Connection": "keep-alive",
}

TIMEOUT = 15

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

def request_get(url, referer=None):

    try:

        headers = {}

        if referer:
            headers["Referer"] = referer

        r = session.get(
            url,
            headers=headers,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        r.encoding = (
            r.apparent_encoding
            or r.encoding
            or "utf-8"
        )

        return r

    except Exception:

        return None


# ============================================================
# 텍스트 정리
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    value = str(value)

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

        n = float(
            str(value).replace(",", "").strip()
        )

        if 1.01 <= n <= 100:
            return n

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
# HTML 링크 추출
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

        for a in soup.find_all("a"):

            href = (
                a.get("href")
                or a.get("data-href")
                or a.get("data-url")
                or ""
            )

            href = href.strip()

            if not href:
                continue

            url = urljoin(
                page_url,
                href
            )

            if url not in result:

                result.append(url)

    except Exception:
        pass

    return result


# ============================================================
# 실제 경기 링크 판별
# ============================================================

def is_match_link(url):

    low = url.lower()

    # 광고/이미지/JS 제외
    if any(
        x in low
        for x in (
            ".js",
            ".css",
            ".png",
            ".jpg",
            ".gif",
            ".svg",
            "javascript:",
            "mailto:",
            "ad.",
            "ads.",
        )
    ):

        return False

    # 명백한 경기 상세 주소
    if any(
        x in low
        for x in (
            "match",
            "game",
            "fixture",
            "odds",
            "event",
        )
    ):

        return True

    # 숫자 ID가 query로 붙는 경우
    if re.search(
        r"[?&](?:id|mid|matchid|gameid)="
        r"\d{5,10}",
        low
    ):

        return True

    return False


# ============================================================
# 링크에서 정확한 경기 ID
# ============================================================

def extract_match_id_from_url(url):

    patterns = [

        # ?id=123456
        r"[?&]id=(\d{5,10})(?:&|$)",

        # ?mid=123456
        r"[?&]mid=(\d{5,10})(?:&|$)",

        # ?matchid=123456
        r"[?&]matchid=(\d{5,10})(?:&|$)",

        # ?gameid=123456
        r"[?&]gameid=(\d{5,10})(?:&|$)",

        # /match/123456
        r"/match/(\d{5,10})(?:/|$)",

        # /game/123456
        r"/game/(\d{5,10})(?:/|$)",

        # /event/123456
        r"/event/(\d{5,10})(?:/|$)",

        # match-123456
        r"match[-_](\d{5,10})",

    ]

    for pattern in patterns:

        m = re.search(
            pattern,
            url,
            re.I
        )

        if m:

            value = m.group(1)

            try:

                n = int(value)

                if 100000 <= n <= 9999999999:

                    return str(n)

            except Exception:
                pass

    return None


# ============================================================
# HTML 안의 경기 링크
# ============================================================

def extract_real_match_links(
    page_url,
    html
):

    result = []

    links = extract_links(
        page_url,
        html
    )

    for url in links:

        if not is_match_link(url):
            continue

        match_id = extract_match_id_from_url(
            url
        )

        if not match_id:
            continue

        result.append(
            {
                "id": match_id,
                "url": url
            }
        )

    # 중복 제거
    unique = {}

    for item in result:

        unique[item["url"]] = item

    return list(
        unique.values()
    )


# ============================================================
# HTML 내부 data-* 경기 정보
# ============================================================

def extract_data_match_links(
    page_url,
    html
):

    result = []

    patterns = [

        r'data-(?:match-id|matchid|game-id|gameid|event-id)'
        r'\s*=\s*["\'](\d{5,10})["\']',

        r'data-id\s*=\s*["\'](\d{5,10})["\']',

    ]

    ids = set()

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                html,
                re.I
            )

            for value in found:

                try:

                    n = int(value)

                    if 100000 <= n <= 9999999999:

                        ids.add(
                            str(n)
                        )

                except Exception:
                    pass

        except Exception:
            pass

    for match_id in sorted(
        ids,
        key=lambda x: int(x)
    ):

        # 실제 링크를 HTML에서 찾아본다
        patterns2 = [

            rf'href=["\']([^"\']*'
            rf'{re.escape(match_id)}'
            rf'[^"\']*)["\']',

            rf'data-url=["\']([^"\']*'
            rf'{re.escape(match_id)}'
            rf'[^"\']*)["\']',

        ]

        found_url = None

        for p in patterns2:

            m = re.search(
                p,
                html,
                re.I
            )

            if m:

                found_url = urljoin(
                    page_url,
                    m.group(1)
                )

                break

        if found_url:

            result.append(
                {
                    "id": match_id,
                    "url": found_url
                }
            )

    return result


# ============================================================
# 경기 페이지 후보
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

        f"{DATA_URL}/match/{match_id}",

    ]


# ============================================================
# 팀명 추출
# ============================================================

def extract_teams(
    html
):

    result = []

    patterns = [

        (
            r'"homeTeam"\s*:\s*"([^"]+)".{0,1000}?'
            r'"awayTeam"\s*:\s*"([^"]+)"'
        ),

        (
            r'"home_team"\s*:\s*"([^"]+)".{0,1000}?'
            r'"away_team"\s*:\s*"([^"]+)"'
        ),

        (
            r'"homeName"\s*:\s*"([^"]+)".{0,1000}?'
            r'"awayName"\s*:\s*"([^"]+)"'
        ),

        (
            r'"HomeTeam"\s*:\s*"([^"]+)".{0,1000}?'
            r'"AwayTeam"\s*:\s*"([^"]+)"'
        ),

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                html,
                re.I | re.S
            )

            for pair in found:

                home = clean_text(
                    pair[0]
                )

                away = clean_text(
                    pair[1]
                )

                if (
                    home
                    and away
                    and len(home) < 150
                    and len(away) < 150
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
# HTML에서 팀명 추정
# ============================================================

def extract_teams_from_visible_text(
    html
):

    result = []

    try:

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        text = clean_text(
            soup.get_text(" ")
        )

        # 흔한 VS 구조
        patterns = [

            r"([A-Za-zÀ-ÿ0-9가-힣][^|]{1,80})"
            r"\s+(?:vs\.?|VS|v)\s+"
            r"([^|]{1,80})",

        ]

        for pattern in patterns:

            found = re.findall(
                pattern,
                text,
                re.I
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

                    result.append(
                        (
                            home,
                            away
                        )
                    )

    except Exception:
        pass

    return result


# ============================================================
# 스코어
# ============================================================

def extract_score(
    html
):

    patterns = [

        (
            r'"homeScore"\s*:\s*["\']?'
            r'(\d{1,3})'
            r'["\']?.{0,500}?'
            r'"awayScore"\s*:\s*["\']?'
            r'(\d{1,3})'
        ),

        (
            r'"home_score"\s*:\s*["\']?'
            r'(\d{1,3})'
            r'["\']?.{0,500}?'
            r'"away_score"\s*:\s*["\']?'
            r'(\d{1,3})'
        ),

    ]

    for pattern in patterns:

        m = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if m:

            try:

                return (
                    int(m.group(1)),
                    int(m.group(2))
                )

            except Exception:
                pass

    return None


# ============================================================
# 1X2 배당 추출
# ============================================================

def extract_odds(
    html
):

    result = []

    patterns = [

        (
            r'"home"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1000}?'
            r'"draw"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1000}?'
            r'"away"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
        ),

        (
            r'"homeOdds"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1000}?'
            r'"drawOdds"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1000}?'
            r'"awayOdds"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
        ),

        (
            r'"odds1"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1000}?'
            r'"oddsX"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
            r'.{0,1000}?'
            r'"odds2"\s*:\s*'
            r'([0-9]+\.[0-9]+)'
        ),

    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                html,
                re.I | re.S
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
# 상세 경기 페이지 검사
# ============================================================

def inspect_match_url(
    url,
    match_id,
    referer=None
):

    r = request_get(
        url,
        referer=referer
    )

    if r is None:
        return None

    if r.status_code != 200:
        return None

    html = r.text

    teams = extract_teams(
        html
    )

    if not teams:

        teams = extract_teams_from_visible_text(
            html
        )

    score = extract_score(
        html
    )

    odds = extract_odds(
        html
    )

    # 실제 경기 페이지로 볼 수 있는 조건
    if not teams and not odds and not score:
        return None

    return {

        "match_id":
            match_id,

        "url":
            r.url,

        "html":
            html,

        "teams":
            teams[0] if teams else None,

        "score":
            score,

        "odds":
            odds,

        "size":
            len(r.content),

    }


# ============================================================
# 정확한 경기 상세 찾기
# ============================================================

def get_match(
    match_id,
    source_url=None,
    retry_count=2,
    retry_delay=0.5
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

            result = inspect_match_url(
                url,
                match_id,
                referer=(
                    source_url
                    or BASE_URL
                )
            )

            if result is None:
                continue

            score = 0

            if result["teams"]:
                score += 10

            if result["odds"]:
                score += 10

            if result["score"]:
                score += 5

            if result["size"] > 5000:
                score += 2

            result[
                "_score"
            ] = score

            if (
                best is None
                or score > best["_score"]
            ):

                best = result

            # 팀 + 배당이면 성공
            if (
                result["teams"]
                and result["odds"]
            ):

                return result

        if attempt < retry_count:

            time.sleep(
                retry_delay
            )

    return best


# ============================================================
# 시작 페이지
# ============================================================

def get_start_page(
    date_string
):

    candidates = [

        (
            f"{BASE_URL}/default_en.aspx"
            f"?classid=&view=all&match=&line=no"
        ),

        (
            f"{BASE_URL}/default_en.aspx"
        ),

        (
            f"{BASE_URL}/default_kr.aspx"
        ),

        (
            f"{BASE_URL}/default_ms.aspx"
        ),

        (
            f"{BASE_URL}/default_vn.aspx"
        ),

    ]

    best = None

    for url in candidates:

        r = request_get(
            url
        )

        if r is None:
            continue

        if r.status_code != 200:
            continue

        if len(r.content) < 10000:
            continue

        # 실제 경기 페이지인지 확인
        links = extract_real_match_links(
            r.url,
            r.text
        )

        data_links = extract_data_match_links(
            r.url,
            r.text
        )

        score = (
            len(links) * 10
            + len(data_links) * 10
            + len(r.content) // 100000
        )

        if (
            best is None
            or score > best["score"]
        ):

            best = {

                "url":
                    r.url,

                "html":
                    r.text,

                "links":
                    links,

                "data_links":
                    data_links,

                "score":
                    score,

            }

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
        ""
    )

    log(
        log_callback,
        "=========================================="
    )

    log(
        log_callback,
        "🔎 7M 실제 경기 링크 진단"
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
        date_string
    )

    result = {

        "date":
            date_string,

        "http":
            0,

        "html_bytes":
            0,

        "match_links":
            0,

        "match_ids":
            0,

        "matches":
            [],

        "page_url":
            "",

    }

    if page is None:

        log(
            log_callback,
            "❌ 7M 시작 페이지 실패"
        )

        return result

    result[
        "http"
    ] = 200

    result[
        "page_url"
    ] = page["url"]

    result[
        "html_bytes"
    ] = len(
        page["html"].encode(
            errors="ignore"
        )
    )

    log(
        log_callback,
        f"페이지: {page['url']}"
    )

    log(
        log_callback,
        "HTTP: 200"
    )

    log(
        log_callback,
        f"HTML: {result['html_bytes']:,}"
    )

    # 실제 링크
    matches = list(
        page["links"]
    )

    # data-id 링크
    for item in page["data_links"]:

        exists = any(
            x["id"] == item["id"]
            for x in matches
        )

        if not exists:

            matches.append(
                item
            )

    # ID 중복 제거
    unique = {}

    for item in matches:

        mid = item.get(
            "id"
        )

        if not mid:
            continue

        unique[mid] = item

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

    log(
        log_callback,
        f"실제 경기 링크: {len(matches)}"
    )

    # --------------------------------------------------------
    # 처음 5개만 검증
    # --------------------------------------------------------

    log(
        log_callback,
        ""
    )

    log(
        log_callback,
        "🧪 실제 경기 5개 샘플 검사"
    )

    valid = []

    for index, item in enumerate(
        matches[:5],
        1
    ):

        log(
            log_callback,
            (
                f"[샘플 {index}/5] "
                f"ID={item['id']}"
            )
        )

        detail = get_match(
            item["id"],
            source_url=item.get("url")
        )

        if detail is None:

            log(
                log_callback,
                "  ❌ 상세 데이터 없음"
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
            )
        )

        valid.append(
            detail
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
        "진단 결과"
    )

    log(
        log_callback,
        f"실제 경기 링크: {len(matches)}"
    )

    log(
        log_callback,
        f"샘플 성공: {len(valid)}/5"
    )

    log(
        log_callback,
        "=========================================="
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
    log_callback=None
):

    date_string = normalize_date(
        date_string
    )

    diagnosis = diagnose(
        date_string,
        cid=cid,
        log_callback=log_callback
    )

    matches = diagnosis.get(
        "matches",
        []
    )

    if not matches:

        log(
            log_callback,
            "❌ 실제 경기 링크가 없습니다."
        )

        return []

    # 처음부터 500개 제한하지 않는다.
    # 실제 경기 링크만 사용한다.
    results = []

    total = len(matches)

    log(
        log_callback,
        ""
    )

    log(
        log_callback,
        f"🎯 실제 경기 {total}개 수집 시작"
    )

    for index, item in enumerate(
        matches,
        1
    ):

        match_id = item["id"]

        log(
            log_callback,
            f"[{index}/{total}] ID {match_id}"
        )

        detail = get_match(
            match_id,
            source_url=item.get("url"),
            retry_count=retry_count,
            retry_delay=retry_delay
        )

        if detail is None:

            log(
                log_callback,
                "  ❌ 상세 데이터 없음"
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

            # 마지막 배당을 최종배당으로 사용
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

        # 최소한 팀명 또는 배당이 있어야 저장
        if (
            not home_team
            and not away_team
            and not final_odds
        ):

            log(
                log_callback,
                "  ⚠️ 경기 정보 부족"
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
        f"경기 저장 대상: {len(results)}"
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
        f"7M 테스트: {today}"
    )

    diagnose(
        today,
        log_callback=print
                           )
