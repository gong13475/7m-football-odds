# ============================================================
# sevenm_crawler.py
# 7M 축구 최종배당 수집기
# ============================================================

import re
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# 기본 설정
# ============================================================

BASE_URL = "https://data.7msport.com"

LIVE_URL = "https://live.7msport.com"

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
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

TIMEOUT = 12


# ============================================================
# Session
# ============================================================

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# 로그
# ============================================================

def _log(callback, message):

    if callback:

        try:
            callback(str(message))
        except Exception:
            pass


# ============================================================
# HTTP
# ============================================================

def _get(url, timeout=TIMEOUT):

    try:

        r = session.get(
            url,
            timeout=timeout,
            allow_redirects=True
        )

        if not r.encoding:

            r.encoding = "utf-8"

        return r

    except Exception:

        return None


# ============================================================
# 숫자
# ============================================================

def _float(value):

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

        v = float(
            m.group(0)
        )

        if v <= 1:
            return None

        if v > 100:
            return None

        return v

    except Exception:

        return None


# ============================================================
# HTML 텍스트
# ============================================================

def _text(value):

    if value is None:
        return ""

    value = re.sub(
        r"<[^>]+>",
        " ",
        str(value)
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# 승무패
# ============================================================

def _result(home, away):

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
# 날짜 변환
# ============================================================

def _date_parts(date_string):

    d = datetime.strptime(
        date_string,
        "%Y-%m-%d"
    )

    return (
        d.year,
        d.month,
        d.day
    )


# ============================================================
# 7M 결과 페이지
# ============================================================

def _result_urls(date_string):

    year, month, day = _date_parts(
        date_string
    )

    dates = [
        f"{year}-{month:02d}-{day:02d}",
        f"{year}-{month}-{day}",
        f"{year}/{month:02d}/{day:02d}",
        f"{year},{month:02d},{day:02d}",
    ]

    urls = []

    for d in dates:

        urls.extend([

            f"{BASE_URL}/result_data/"
            f"default_en.shtml?date={d}",

            f"{BASE_URL}/result/"
            f"default_en.shtml?date={d}",

        ])

    return list(
        dict.fromkeys(urls)
    )


# ============================================================
# Fixture 페이지
# ============================================================

def _fixture_urls(date_string):

    year, month, day = _date_parts(
        date_string
    )

    dates = [
        f"{year}-{month:02d}-{day:02d}",
        f"{year}-{month}-{day}",
        f"{year}/{month:02d}/{day:02d}",
        f"{year},{month:02d},{day:02d}",
    ]

    urls = []

    for d in dates:

        urls.extend([

            f"{BASE_URL}/fixture_data/"
            f"default_en.shtml?date={d}",

            f"{BASE_URL}/fixture/"
            f"default_en.shtml?date={d}",

        ])

    return list(
        dict.fromkeys(urls)
    )


# ============================================================
# 날짜 페이지 요청
# ============================================================

def _load_date_page(
    date_string,
    log_callback=None
):

    # 결과 페이지 먼저
    for url in _result_urls(
        date_string
    ):

        _log(
            log_callback,
            f"7M 결과 페이지 확인: {url}"
        )

        r = _get(url)

        if r is not None and r.status_code == 200:

            if len(r.text) > 500:

                _log(
                    log_callback,
                    f"성공 HTTP 200 / "
                    f"{len(r.text):,} bytes"
                )

                return (
                    url,
                    r.text
                )

    # Fixture
    for url in _fixture_urls(
        date_string
    ):

        _log(
            log_callback,
            f"7M 경기 페이지 확인: {url}"
        )

        r = _get(url)

        if r is not None and r.status_code == 200:

            if len(r.text) > 500:

                _log(
                    log_callback,
                    f"Fixture 성공 / "
                    f"{len(r.text):,} bytes"
                )

                return (
                    url,
                    r.text
                )

    return (
        "",
        ""
    )


# ============================================================
# 경기 링크 추출
# ============================================================

def _find_match_links(
    page_url,
    page_html
):

    result = []

    try:

        soup = BeautifulSoup(
            page_html,
            "html.parser"
        )

    except Exception:

        return result

    for a in soup.find_all(
        "a"
    ):

        href = (
            a.get("href")
            or ""
        ).strip()

        if not href:
            continue

        full = urljoin(
            page_url,
            href
        )

        low = full.lower()

        # 경기/배당 상세 링크 후보
        if any(
            key in low
            for key in [
                "odds",
                "match",
                "fixture",
                "game",
                "detail",
                "matches_data",
            ]
        ):

            if full not in result:

                result.append(
                    full
                )

    return result


# ============================================================
# 경기 ID 추출
# ============================================================

def _find_ids(
    text
):

    ids = set()

    patterns = [

        r"[?&](?:id|sid|mid|fid|matchid|gameid)"
        r"=(\d{4,12})",

        r"(?:matchid|match_id)"
        r"\s*[=:]\s*[\"']?(\d{4,12})",

        r"(?:gameid|game_id)"
        r"\s*[=:]\s*[\"']?(\d{4,12})",

        r"/(\d{5,12})"
        r"(?:\.shtml|\.html|\.aspx)",

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

                    n = int(
                        value
                    )

                    if (
                        10000
                        <= n
                        <= 999999999999
                    ):

                        ids.add(
                            str(n)
                        )

                except Exception:

                    pass

        except Exception:

            pass

    return sorted(
        ids,
        key=lambda x: int(x)
    )


# ============================================================
# 경기 텍스트 파싱
# ============================================================

def _parse_matches(
    page_html,
    date_string
):

    matches = []

    soup = BeautifulSoup(
        page_html,
        "html.parser"
    )

    # --------------------------------------------------------
    # 1. 테이블 기반
    # --------------------------------------------------------

    for tr in soup.find_all(
        "tr"
    ):

        raw = tr.get_text(
            " ",
            strip=True
        )

        if not raw:
            continue

        # 점수
        score_match = re.search(
            r"\b(\d{1,2})\s*[-:]\s*(\d{1,2})\b",
            raw
        )

        # 팀명이 없는 일반 행 제외
        if score_match:

            home_score = int(
                score_match.group(1)
            )

            away_score = int(
                score_match.group(2)
            )

            before = raw[
                :score_match.start()
            ]

            after = raw[
                score_match.end():
            ]

            parts = re.split(
                r"\s{2,}|\s+\|\s+",
                before
            )

            if len(parts) >= 2:

                home = _text(
                    parts[-2]
                )

                away = _text(
                    parts[-1]
                )

                if (
                    home
                    and away
                    and home != away
                ):

                    matches.append({

                        "match_date":
                            date_string,

                        "home_team":
                            home,

                        "away_team":
                            away,

                        "home_score":
                            home_score,

                        "away_score":
                            away_score,

                        "result":
                            _result(
                                home_score,
                                away_score
                            ),

                    })

    # --------------------------------------------------------
    # 2. 일반 텍스트
    # --------------------------------------------------------

    text = soup.get_text(
        "\n",
        strip=True
    )

    lines = [
        x.strip()
        for x in text.splitlines()
        if x.strip()
    ]

    for line in lines:

        m = re.search(
            r"(.{2,80}?)\s+"
            r"(\d{1,2})\s*-\s*(\d{1,2})\s+"
            r"(.{2,80})",
            line
        )

        if not m:
            continue

        home = _text(
            m.group(1)
        )

        away = _text(
            m.group(4)
        )

        home_score = int(
            m.group(2)
        )

        away_score = int(
            m.group(3)
        )

        # 날짜/리그 문자열 제외
        if (
            len(home) > 100
            or len(away) > 100
        ):
            continue

        if any(
            x in home.lower()
            for x in [
                "2026",
                "2025",
                "http",
            ]
        ):
            continue

        matches.append({

            "match_date":
                date_string,

            "home_team":
                home,

            "away_team":
                away,

            "home_score":
                home_score,

            "away_score":
                away_score,

            "result":
                _result(
                    home_score,
                    away_score
                ),

        })

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

    unique = {}

    for item in matches:

        key = (
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

    return list(
        unique.values()
    )


# ============================================================
# 배당 숫자 추출
# ============================================================

def _extract_odds(
    text
):

    result = []

    patterns = [

        # 1.85 3.20 3.60
        r"\b"
        r"([1-9]\d?\.\d{1,3})"
        r"\s+"
        r"([1-9]\d?\.\d{1,3})"
        r"\s+"
        r"([1-9]\d?\.\d{1,3})"
        r"\b",

        # JSON
        r'"home"\s*:\s*'
        r'([0-9]+\.[0-9]+)'
        r'.{0,300}?'
        r'"draw"\s*:\s*'
        r'([0-9]+\.[0-9]+)'
        r'.{0,300}?'
        r'"away"\s*:\s*'
        r'([0-9]+\.[0-9]+)',

        r'"odds1"\s*:\s*'
        r'([0-9]+\.[0-9]+)'
        r'.{0,300}?'
        r'"oddsX"\s*:\s*'
        r'([0-9]+\.[0-9]+)'
        r'.{0,300}?'
        r'"odds2"\s*:\s*'
        r'([0-9]+\.[0-9]+)',

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

                h = _float(
                    item[0]
                )

                d = _float(
                    item[1]
                )

                a = _float(
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

        except Exception:

            continue

    return result


# ============================================================
# 진단
# ============================================================

def diagnose(
    date_string,
    cid="",
    log_callback=None
):

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

    }

    _log(
        log_callback,
        "=========================================="
    )

    _log(
        log_callback,
        "7M 데이터 서버 직접 진단"
    )

    _log(
        log_callback,
        f"날짜: {date_string}"
    )

    _log(
        log_callback,
        "=========================================="
    )

    url, text = _load_date_page(
        date_string,
        log_callback
    )

    if not text:

        _log(
            log_callback,
            "7M 데이터 페이지 접속 실패"
        )

        return result

    result[
        "http"
    ] = 200

    result[
        "html_bytes"
    ] = len(text)

    try:

        soup = BeautifulSoup(
            text,
            "html.parser"
        )

        result[
            "iframes"
        ] = len(
            soup.find_all(
                "iframe"
            )
        )

        result[
            "scripts"
        ] = len(
            soup.find_all(
                "script"
            )
        )

    except Exception:

        pass

    ids = _find_ids(
        text
    )

    links = _find_match_links(
        url,
        text
    )

    odds = _extract_odds(
        text
    )

    result[
        "match_candidates"
    ] = len(ids)

    result[
        "apis"
    ] = len(links)

    result[
        "odds_candidates"
    ] = len(odds)

    _log(
        log_callback,
        f"URL: {url}"
    )

    _log(
        log_callback,
        f"HTML: {len(text):,}"
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
        f"경기 ID 후보: {len(ids)}"
    )

    _log(
        log_callback,
        f"상세 링크 후보: {len(links)}"
    )

    _log(
        log_callback,
        f"배당 후보: {len(odds)}"
    )

    _log(
        log_callback,
        "=========================================="
    )

    return result


# ============================================================
# 날짜 경기 수집
# ============================================================

def collect_date(
    date_string,
    cid="",
    retry_count=3,
    retry_delay=1.0,
    log_callback=None
):

    result = []

    _log(
        log_callback,
        f""
    )

    _log(
        log_callback,
        f"📅 {date_string} 수집 시작"
    )

    url, text = _load_date_page(
        date_string,
        log_callback
    )

    if not text:

        _log(
            log_callback,
            "경기 페이지를 찾지 못했습니다."
        )

        return result

    # --------------------------------------------------------
    # 경기 파싱
    # --------------------------------------------------------

    matches = _parse_matches(
        text,
        date_string
    )

    _log(
        log_callback,
        f"경기 행 후보: {len(matches)}"
    )

    # --------------------------------------------------------
    # 링크 / ID
    # --------------------------------------------------------

    links = _find_match_links(
        url,
        text
    )

    ids = _find_ids(
        text
    )

    _log(
        log_callback,
        f"경기 상세 링크: {len(links)}"
    )

    _log(
        log_callback,
        f"경기 ID: {len(ids)}"
    )

    # --------------------------------------------------------
    # 경기 기본 데이터
    # --------------------------------------------------------

    for index, item in enumerate(
        matches
    ):

        item[
            "match_id"
        ] = ""

        item[
            "home_odds"
        ] = None

        item[
            "draw_odds"
        ] = None

        item[
            "away_odds"
        ] = None

        item[
            "cid"
        ] = cid

        item[
            "bookmaker"
        ] = "7M"

        result.append(
            item
        )

        if index >= 1000:
            break

    # --------------------------------------------------------
    # 페이지 전체에서 발견한
    # 1X2 배당 후보
    # --------------------------------------------------------

    odds = _extract_odds(
        text
    )

    if odds:

        _log(
            log_callback,
            f"1X2 배당 후보: {len(odds)}"
        )

    # 경기 수와 배당 수가 일치하는 경우
    if (
        len(odds) == len(result)
        and len(result) > 0
    ):

        for i in range(
            len(result)
        ):

            result[i][
                "home_odds"
            ] = odds[i][0]

            result[i][
                "draw_odds"
            ] = odds[i][1]

            result[i][
                "away_odds"
            ] = odds[i][2]

    _log(
        log_callback,
        f"현재 확보 경기: {len(result)}"
    )

    return result


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

                date_string=date_string,

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
                f"{date_string} 오류: {e}"
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

    _log(
        log_callback,
        "=========================================="
    )

    _log(
        log_callback,
        f"최종 수집 경기: {len(all_matches)}"
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
        f"최종배당 확보: {odds_count}"
    )

    _log(
        log_callback,
        f"실제결과 확보: {result_count}"
    )

    _log(
        log_callback,
        "7M 수집 완료"
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

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    print(
        "7M 진단:",
        today
    )

    data = diagnose(
        today,
        log_callback=print
    )

    print()
    print(data)
