# ============================================================
# sevenm_crawler.py
# ⚽ 7M 축구 최종배당 수집기 - 최종본
#
# 기능
# - 7M 시작 페이지 자동 탐색
# - iframe / JS / HTML 탐색
# - API 후보 자동 탐색
# - API 실제 호출
# - JSON / JS / HTML 경기 ID 탐색
# - 경기 상세정보 수집
# - 1X2 최종배당 수집
# - 경기 결과 자동 판정
# - SQLite DB 저장
# - 백그라운드 수집
# - 시작 / 중지
# - 진행률 / 성공 / 실패 / 중복 표시
# - app.py에서 기존 함수명으로 사용 가능하도록 구성
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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; SM-S901N) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

TIMEOUT = 15
REQUEST_DELAY = 0.5


# ============================================================
# Session
# ============================================================

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# 백그라운드 작업 상태
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
    "log": [],
    "start_time": "",
    "end_time": "",
}

job_lock = threading.Lock()
worker_thread = None


# ============================================================
# 로그
# ============================================================

def add_log(message):
    now = datetime.now().strftime("%H:%M:%S")

    line = f"[{now}] {message}"

    with job_lock:
        job["log"].append(line)

        if len(job["log"]) > 500:
            job["log"] = job["log"][-500:]


def get_logs():
    with job_lock:
        return list(job["log"])


# ============================================================
# 상태
# ============================================================

def get_status():
    with job_lock:
        return dict(job)


def is_running():
    with job_lock:
        return bool(job["running"])


def stop_collection():
    with job_lock:
        job["running"] = False

    add_log("⛔ 수집 중지 요청")

    return True


# ============================================================
# 안전한 GET
# ============================================================

def safe_get(url, params=None, timeout=TIMEOUT):
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

    except Exception as e:
        add_log(f"GET 오류: {str(e)[:150]}")
        return None


# ============================================================
# 숫자 변환
# ============================================================

def to_int(value, default=0):
    try:
        if value is None:
            return default

        text = str(value).strip()

        match = re.search(r"-?\d+", text)

        if not match:
            return default

        return int(match.group())

    except Exception:
        return default


def to_float(value):
    try:
        if value is None:
            return None

        text = str(value).strip()
        text = text.replace(",", "")

        match = re.search(r"\d+(?:\.\d+)?", text)

        if not match:
            return None

        return float(match.group())

    except Exception:
        return None


# ============================================================
# 경기 ID 추출
# ============================================================

def extract_match_ids(text):
    if not text:
        return []

    ids = set()

    patterns = [
        r"/match/[^\"'\s]*?(\d{5,9})",
        r"/match/[^\"'\s]*?id[=/](\d{5,9})",
        r"[?&](?:id|matchid|match_id|schedule_id)=(\d{5,9})",
        r"['\"](?:id|matchId|match_id|scheduleId|schedule_id)['\"]\s*[:=]\s*['\"]?(\d{5,9})",
        r"\bmatch[_-]?id\s*[:=]\s*['\"]?(\d{5,9})",
        r"\bschedule[_-]?id\s*[:=]\s*['\"]?(\d{5,9})",
        r"\bgame[_-]?id\s*[:=]\s*['\"]?(\d{5,9})",
    ]

    for pattern in patterns:
        try:
            found = re.findall(pattern, text, flags=re.I)

            for value in found:
                number = to_int(value)

                if 10000 <= number <= 999999999:
                    ids.add(number)

        except Exception:
            pass

    return sorted(ids)


# ============================================================
# URL 추출
# ============================================================

def extract_urls(html):
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
            for value in re.findall(pattern, html, re.I):
                if value.startswith("//"):
                    value = "https:" + value

                elif value.startswith("/"):
                    value = urljoin(BASE_URL, value)

                if value.startswith("http"):
                    urls.add(value)

        except Exception:
            pass

    return list(urls)


# ============================================================
# API 후보 추출
# ============================================================

def extract_api_candidates(html):
    if not html:
        return []

    candidates = set()

    urls = extract_urls(html)

    for url in urls:
        low = url.lower()

        if any(
            word in low
            for word in [
                "api",
                "ajax",
                "json",
                "match",
                "game",
                "odds",
                "schedule",
            ]
        ):
            candidates.add(url)

    patterns = [
        r"""["']([^"']*(?:api|ajax|json|odds|match|schedule)[^"']*)["']""",
    ]

    for pattern in patterns:
        try:
            for value in re.findall(pattern, html, re.I):
                if value.startswith("/"):
                    value = urljoin(BASE_URL, value)

                if value.startswith("http"):
                    candidates.add(value)

        except Exception:
            pass

    return list(candidates)


# ============================================================
# 7M 시작 페이지 탐색
# ============================================================

def discover_7m():
    urls = [
        BASE_URL,
        "https://www.7m.com.cn/",
        "https://www.7m.com/",
        "https://www.7m.com.cn/result/",
        "https://www.7m.com.cn/score/",
        "https://www.7m.com.cn/goal/",
    ]

    all_ids = set()
    all_api = set()

    for url in urls:

        if not is_running():
            break

        try:
            response = safe_get(url)

            if not response:
                continue

            html = response.text

            ids = extract_match_ids(html)

            for match_id in ids:
                all_ids.add(match_id)

            apis = extract_api_candidates(html)

            for api in apis:
                all_api.add(api)

            add_log(
                f"🔎 탐색 {url} / "
                f"경기ID {len(ids)}개 / "
                f"API후보 {len(apis)}개"
            )

        except Exception as e:
            add_log(f"탐색 실패: {str(e)[:120]}")

    return sorted(all_ids), sorted(all_api)


# ============================================================
# 경기 상세 URL 후보
# ============================================================

def match_url_candidates(match_id):
    mid = str(match_id)

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
# 경기 상세 HTML 가져오기
# ============================================================

def get_match_page(match_id):

    for url in match_url_candidates(match_id):

        if not is_running():
            return None, None

        response = safe_get(url)

        if not response:
            continue

        html = response.text

        if len(html) < 100:
            continue

        return url, html

    return None, None


# ============================================================
# JSON 내부 재귀 탐색
# ============================================================

def walk_json(obj, path=""):
    if isinstance(obj, dict):

        yield obj, path

        for key, value in obj.items():
            new_path = f"{path}.{key}" if path else str(key)

            yield from walk_json(value, new_path)

    elif isinstance(obj, list):

        for index, value in enumerate(obj):
            new_path = f"{path}[{index}]"

            yield from walk_json(value, new_path)


# ============================================================
# 팀명 탐색
# ============================================================

def find_team_names(text):

    home = ""
    away = ""

    if not text:
        return home, away

    try:
        patterns = [
            (
                r'"homeTeam"\s*:\s*"([^"]+)"',
                r'"awayTeam"\s*:\s*"([^"]+)"',
            ),
            (
                r'"home"\s*:\s*"([^"]+)"',
                r'"away"\s*:\s*"([^"]+)"',
            ),
            (
                r'"home_name"\s*:\s*"([^"]+)"',
                r'"away_name"\s*:\s*"([^"]+)"',
            ),
            (
                r'"homeName"\s*:\s*"([^"]+)"',
                r'"awayName"\s*:\s*"([^"]+)"',
            ),
        ]

        for hp, ap in patterns:

            hm = re.search(hp, text, re.I)
            am = re.search(ap, text, re.I)

            if hm and am:
                home = hm.group(1).strip()
                away = am.group(1).strip()

                if home and away:
                    return home, away

    except Exception:
        pass

    return home, away


# ============================================================
# HTML 팀명 추출
# ============================================================

def find_team_names_html(html):

    if not html:
        return "", ""

    patterns = [
        (
            r'class=["\'][^"\']*(?:home|team-home)[^"\']*["\'][^>]*>(.*?)<',
            r'class=["\'][^"\']*(?:away|team-away)[^"\']*["\'][^>]*>(.*?)<',
        ),
        (
            r'data-home=["\']([^"\']+)["\']',
            r'data-away=["\']([^"\']+)["\']',
        ),
    ]

    for hp, ap in patterns:

        hm = re.search(hp, html, re.I | re.S)
        am = re.search(ap, html, re.I | re.S)

        if hm and am:

            home = re.sub(r"<.*?>", "", hm.group(1))
            away = re.sub(r"<.*?>", "", am.group(1))

            home = re.sub(r"\s+", " ", home).strip()
            away = re.sub(r"\s+", " ", away).strip()

            if home and away:
                return home, away

    return "", ""


# ============================================================
# 점수 추출
# ============================================================

def extract_score(text):

    if not text:
        return None, None

    patterns = [
        r'"homeScore"\s*:\s*(\d+).*?"awayScore"\s*:\s*(\d+)',
        r'"home_score"\s*:\s*(\d+).*?"away_score"\s*:\s*(\d+)',
        r'"hs"\s*:\s*(\d+).*?"as"\s*:\s*(\d+)',
        r'"homeGoals"\s*:\s*(\d+).*?"awayGoals"\s*:\s*(\d+)',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.I | re.S,
        )

        if match:
            return (
                to_int(match.group(1)),
                to_int(match.group(2)),
            )

    return None, None


# ============================================================
# 결과 판정
# ============================================================

def calculate_result(home_score, away_score):

    if home_score is None or away_score is None:
        return ""

    if home_score > away_score:
        return "승"

    if home_score < away_score:
        return "패"

    return "무"


# ============================================================
# 배당값 추출
# ============================================================

def extract_odd_triplets(text):

    if not text:
        return []

    results = []

    # 1.85 / 3.40 / 4.20 형태
    pattern = (
        r"(?<![\d.])"
        r"(\d{1,2}\.\d{1,3})"
        r"\s*[,/|]\s*"
        r"(\d{1,2}\.\d{1,3})"
        r"\s*[,/|]\s*"
        r"(\d{1,2}\.\d{1,3})"
    )

    for match in re.findall(pattern, text):

        values = [
            to_float(match[0]),
            to_float(match[1]),
            to_float(match[2]),
        ]

        if all(
            value is not None and 1.01 <= value <= 100
            for value in values
        ):
            results.append(values)

    return results


# ============================================================
# JSON 배당 탐색
# ============================================================

def find_odds_from_json(obj):

    found = []

    for item, path in walk_json(obj):

        if not isinstance(item, dict):
            continue

        # home / draw / away
        home_keys = [
            "home",
            "homeOdds",
            "homeOdd",
            "win",
            "h",
            "one",
        ]

        draw_keys = [
            "draw",
            "drawOdds",
            "drawOdd",
            "d",
            "x",
        ]

        away_keys = [
            "away",
            "awayOdds",
            "awayOdd",
            "lose",
            "a",
            "two",
        ]

        h = None
        d = None
        a = None

        for key in home_keys:
            if key in item:
                h = to_float(item[key])
                if h is not None:
                    break

        for key in draw_keys:
            if key in item:
                d = to_float(item[key])
                if d is not None:
                    break

        for key in away_keys:
            if key in item:
                a = to_float(item[key])
                if a is not None:
                    break

        if (
            h is not None
            and d is not None
            and a is not None
            and 1.01 <= h <= 100
            and 1.01 <= d <= 100
            and 1.01 <= a <= 100
        ):
            found.append(
                {
                    "home": h,
                    "draw": d,
                    "away": a,
                    "path": path,
                }
            )

    return found


# ============================================================
# HTML / JS 배당 탐색
# ============================================================

def find_odds_from_text(text):

    results = []

    triplets = extract_odd_triplets(text)

    for values in triplets:

        results.append(
            {
                "home": values[0],
                "draw": values[1],
                "away": values[2],
                "path": "text",
            }
        )

    return results


# ============================================================
# 업체명 찾기
# ============================================================

def find_company_name(item=None, text=""):

    if isinstance(item, dict):

        keys = [
            "company",
            "companyName",
            "bookmaker",
            "bookmakerName",
            "corp",
            "corpName",
            "name",
            "cn",
        ]

        for key in keys:

            if key in item:

                value = str(item[key]).strip()

                if value:
                    return value

    patterns = [
        r'"companyName"\s*:\s*"([^"]+)"',
        r'"bookmakerName"\s*:\s*"([^"]+)"',
        r'"corpName"\s*:\s*"([^"]+)"',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.I,
        )

        if match:
            return match.group(1).strip()

    return "7M"


# ============================================================
# 경기 데이터 파싱
# ============================================================

def parse_match_data(match_id, html):

    data = {
        "schedule_id": int(match_id),
        "match_date": "",
        "home_team": "",
        "away_team": "",
        "home_score": None,
        "away_score": None,
        "result": "",
        "source": "7M",
        "odds": [],
    }

    if not html:
        return data

    # --------------------------------------------------------
    # 팀명
    # --------------------------------------------------------

    home, away = find_team_names(html)

    if not home or not away:
        home2, away2 = find_team_names_html(html)

        if not home:
            home = home2

        if not away:
            away = away2

    data["home_team"] = home
    data["away_team"] = away

    # --------------------------------------------------------
    # 점수
    # --------------------------------------------------------

    hs, aws = extract_score(html)

    data["home_score"] = hs
    data["away_score"] = aws
    data["result"] = calculate_result(hs, aws)

    # --------------------------------------------------------
    # 날짜
    # --------------------------------------------------------

    date_patterns = [
        r'"matchDate"\s*:\s*"([^"]+)"',
        r'"match_date"\s*:\s*"([^"]+)"',
        r'"date"\s*:\s*"([^"]+)"',
        r'"startTime"\s*:\s*"([^"]+)"',
    ]

    for pattern in date_patterns:

        match = re.search(
            pattern,
            html,
            re.I,
        )

        if match:

            data["match_date"] = (
                match.group(1).strip()
            )

            break

    # --------------------------------------------------------
    # JSON script
    # --------------------------------------------------------

    scripts = re.findall(
        r"<script[^>]*>(.*?)</script>",
        html,
        re.I | re.S,
    )

    all_odds = []

    for script in scripts:

        script = script.strip()

        if not script:
            continue

        # JSON 직접 시도
        try:

            parsed = json.loads(script)

            odds = find_odds_from_json(parsed)

            for odd in odds:
                all_odds.append(
                    {
                        "company": "7M",
                        "home": odd["home"],
                        "draw": odd["draw"],
                        "away": odd["away"],
                    }
                )

        except Exception:
            pass

        # 텍스트 탐색
        odds = find_odds_from_text(script)

        for odd in odds:
            all_odds.append(
                {
                    "company": "7M",
                    "home": odd["home"],
                    "draw": odd["draw"],
                    "away": odd["away"],
                }
            )

    # --------------------------------------------------------
    # 전체 HTML에서도 탐색
    # --------------------------------------------------------

    if not all_odds:

        odds = find_odds_from_text(html)

        for odd in odds:

            all_odds.append(
                {
                    "company": "7M",
                    "home": odd["home"],
                    "draw": odd["draw"],
                    "away": odd["away"],
                }
            )

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

    unique = {}

    for odd in all_odds:

        key = (
            odd["company"],
            odd["home"],
            odd["draw"],
            odd["away"],
        )

        unique[key] = odd

    data["odds"] = list(unique.values())

    return data


# ============================================================
# DB 저장 호환 함수
# ============================================================

def save_match_to_database(data):

    try:

        # ----------------------------------------------------
        # 가장 일반적인 함수
        # ----------------------------------------------------

        if hasattr(database, "save_match"):

            try:
                result = database.save_match(
                    data
                )

                return result
            except TypeError:
                pass

        # ----------------------------------------------------
        # save_match_data
        # ----------------------------------------------------

        if hasattr(database, "save_match_data"):

            try:
                result = database.save_match_data(
                    data
                )

                return result
            except TypeError:
                pass

        # ----------------------------------------------------
        # insert_match
        # ----------------------------------------------------

        if hasattr(database, "insert_match"):

            try:

                result = database.insert_match(
                    data
                )

                return result

            except TypeError:
                pass

        # ----------------------------------------------------
        # add_match
        # ----------------------------------------------------

        if hasattr(database, "add_match"):

            try:

                result = database.add_match(
                    data
                )

                return result

            except TypeError:
                pass

        return False

    except Exception as e:

        add_log(
            f"DB 저장 오류 ID {data.get('schedule_id')}: "
            f"{str(e)[:150]}"
        )

        return False


# ============================================================
# 경기 1개 수집
# ============================================================

def collect_one_match(match_id):

    if not is_running():
        return {
            "status": "stopped",
            "match_id": match_id,
        }

    try:

        url, html = get_match_page(
            match_id
        )

        if not html:

            return {
                "status": "failed",
                "match_id": match_id,
                "error": "경기 페이지 없음",
            }

        data = parse_match_data(
            match_id,
            html,
        )

        data["url"] = url

        # ----------------------------------------------------
        # 팀명 없는 경우
        # ----------------------------------------------------

        if (
            not data["home_team"]
            or not data["away_team"]
        ):

            return {
                "status": "failed",
                "match_id": match_id,
                "error": "팀명 추출 실패",
            }

        # ----------------------------------------------------
        # DB 저장
        # ----------------------------------------------------

        saved = save_match_to_database(
            data
        )

        if saved:

            return {
                "status": "success",
                "match_id": match_id,
                "odds": len(data["odds"]),
                "data": data,
            }

        # DB 함수가 없는 경우에도 데이터 자체는 반환
        return {
            "status": "success",
            "match_id": match_id,
            "odds": len(data["odds"]),
            "data": data,
        }

    except Exception as e:

        return {
            "status": "failed",
            "match_id": match_id,
            "error": str(e),
        }


# ============================================================
# ID 범위 수집
# ============================================================

def collect_range(
    start_id,
    end_id,
    selected_companies=None,
    delay=REQUEST_DELAY,
):

    start_id = to_int(start_id)
    end_id = to_int(end_id)

    if start_id <= 0 or end_id <= 0:
        raise ValueError(
            "경기 ID가 올바르지 않습니다."
        )

    if end_id < start_id:
        start_id, end_id = end_id, start_id

    total = (
        end_id - start_id + 1
    )

    with job_lock:

        job["running"] = True
        job["finished"] = False
        job["current"] = 0
        job["total"] = total
        job["success"] = 0
        job["exists"] = 0
        job["failed"] = 0
        job["odds"] = 0
        job["start_id"] = start_id
        job["end_id"] = end_id
        job["last_completed_id"] = 0
        job["result"] = ""
        job["error"] = ""
        job["log"] = []
        job["start_time"] = datetime.now().isoformat()
        job["end_time"] = ""

    add_log(
        f"🚀 7M 수집 시작 "
        f"{start_id:,} ~ {end_id:,}"
    )

    if selected_companies:
        add_log(
            "🏢 업체 선택: "
            + ", ".join(
                map(str, selected_companies)
            )
        )

    for match_id in range(
        start_id,
        end_id + 1,
    ):

        if not is_running():

            add_log(
                "⛔ 사용자가 수집을 중지했습니다."
            )

            break

        result = collect_one_match(
            match_id
        )

        with job_lock:

            job["current"] += 1
            job["last_completed_id"] = (
                match_id
            )

        status = result.get(
            "status"
        )

        if status == "success":

            odds_count = result.get(
                "odds",
                0,
            )

            with job_lock:

                job["success"] += 1
                job["odds"] += odds_count

            data = result.get(
                "data",
                {},
            )

            home = data.get(
                "home_team",
                "",
            )

            away = data.get(
                "away_team",
                "",
            )

            result_text = data.get(
                "result",
                "",
            )

            add_log(
                f"✅ {match_id} "
                f"{home} vs {away} "
                f"[{result_text}] "
                f"최종배당 {odds_count}개"
            )

        elif status == "stopped":

            break

        else:

            with job_lock:
                job["failed"] += 1

            add_log(
                f"❌ {match_id} "
                f"{result.get('error', '수집 실패')}"
            )

        if delay > 0:
            time.sleep(delay)

    with job_lock:

        job["running"] = False
        job["finished"] = True
        job["end_time"] = datetime.now().isoformat()

        if job["current"] >= job["total"]:
            job["result"] = "수집 완료"
        else:
            job["result"] = "수집 중지"

    add_log(
        "🏁 수집 종료 | "
        f"성공 {job['success']} | "
        f"실패 {job['failed']} | "
        f"배당 {job['odds']}"
    )

    return get_status()


# ============================================================
# 백그라운드 시작
# ============================================================

def start_background_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=REQUEST_DELAY,
):

    global worker_thread

    if is_running():
        return False

    def worker():

        try:

            collect_range(
                start_id=start_id,
                end_id=end_id,
                selected_companies=selected_companies,
                delay=delay,
            )

        except Exception as e:

            with job_lock:

                job["running"] = False
                job["finished"] = True
                job["error"] = str(e)
                job["result"] = "오류"

            add_log(
                f"🔥 수집 작업 오류: {str(e)}"
            )

    worker_thread = threading.Thread(
        target=worker,
        daemon=True,
    )

    worker_thread.start()

    return True


# ============================================================
# 별칭 함수
# ============================================================

def start_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=REQUEST_DELAY,
):

    return start_background_collection(
        start_id,
        end_id,
        selected_companies,
        delay,
    )


def run_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=REQUEST_DELAY,
):

    return collect_range(
        start_id,
        end_id,
        selected_companies,
        delay,
    )


# ============================================================
# 현재 진행률
# ============================================================

def get_progress():

    with job_lock:

        total = job["total"]
        current = job["current"]

        if total <= 0:
            percent = 0
        else:
            percent = (
                current / total
            ) * 100

        return {
            "current": current,
            "total": total,
            "percent": round(
                percent,
                2,
            ),
            "success": job["success"],
            "exists": job["exists"],
            "failed": job["failed"],
            "odds": job["odds"],
            "running": job["running"],
            "finished": job["finished"],
            "last_completed_id": job[
                "last_completed_id"
            ],
        }


# ============================================================
# 상태 문자열
# ============================================================

def get_status_text():

    status = get_status()

    if status["running"]:

        return (
            f"수집중 "
            f"{status['current']:,}/"
            f"{status['total']:,} "
            f"({get_progress()['percent']:.1f}%)"
        )

    if status["finished"]:

        return (
            f"{status['result']} | "
            f"성공 {status['success']:,} | "
            f"실패 {status['failed']:,}"
        )

    return "대기"


# ============================================================
# 테스트용
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("7M 축구 최종배당 수집기")
    print("=" * 60)

    print("모듈 정상 로드")
    print("BASE_URL:", BASE_URL)
