# ============================================================
# sevenm_crawler.py
# 7M 축구 1X2 최종배당 수집기
# ============================================================

import re
import time
import threading
from datetime import datetime
from urllib.parse import urljoin

import requests
import database


# ============================================================
# 기본 설정
# ============================================================

BASE_URL = "https://am.7m.com.cn"

ODDS_URL = (
    "https://am.7m.com.cn/en/windrawwinfirsthalf.shtml"
)

TIMEOUT = 20
REQUEST_DELAY = 0.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; SM-S901N) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": (
        "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
}


# ============================================================
# Session
# ============================================================

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# 백그라운드 상태
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
        return job["running"]


# ============================================================
# 중지
# ============================================================

def stop_collection():

    with job_lock:
        job["running"] = False

    add_log("⛔ 수집 중지 요청")

    return True


# ============================================================
# 숫자 변환
# ============================================================

def to_int(value, default=0):

    try:

        if value is None:
            return default

        match = re.search(r"-?\d+", str(value))

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

        match = re.search(
            r"\d+(?:\.\d+)?",
            text
        )

        if not match:
            return None

        return float(match.group())

    except Exception:

        return None


# ============================================================
# HTTP
# ============================================================

def safe_get(url):

    try:

        response = session.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        if response.status_code != 200:

            add_log(
                f"HTTP 오류 {response.status_code}"
            )

            return None

        return response

    except Exception as e:

        add_log(
            f"접속 오류: {str(e)[:150]}"
        )

        return None


# ============================================================
# HTML 문자 정리
# ============================================================

def clean_text(value):

    if not value:
        return ""

    text = str(value)

    text = re.sub(
        r"<script.*?</script>",
        " ",
        text,
        flags=re.I | re.S
    )

    text = re.sub(
        r"<style.*?</style>",
        " ",
        text,
        flags=re.I | re.S
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = text.replace(
        "&nbsp;",
        " "
    )

    text = text.replace(
        "&amp;",
        "&"
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# HTML에서 링크 추출
# ============================================================

def extract_urls(html):

    if not html:
        return []

    urls = set()

    pattern = r'href\s*=\s*["\']([^"\']+)["\']'

    for value in re.findall(
        pattern,
        html,
        flags=re.I
    ):

        value = value.strip()

        if value.startswith("//"):
            value = "https:" + value

        elif value.startswith("/"):
            value = urljoin(
                BASE_URL,
                value
            )

        if value.startswith("http"):
            urls.add(value)

    return list(urls)


# ============================================================
# 경기 ID 추출
# ============================================================

def extract_match_ids(html):

    if not html:
        return []

    ids = set()

    patterns = [
        r"matchid\s*[=:]\s*['\"]?(\d{5,9})",
        r"match_id\s*[=:]\s*['\"]?(\d{5,9})",
        r"gameid\s*[=:]\s*['\"]?(\d{5,9})",
        r"game_id\s*[=:]\s*['\"]?(\d{5,9})",
        r"scheduleid\s*[=:]\s*['\"]?(\d{5,9})",
        r"schedule_id\s*[=:]\s*['\"]?(\d{5,9})",
    ]

    for pattern in patterns:

        try:

            values = re.findall(
                pattern,
                html,
                flags=re.I
            )

            for value in values:

                number = to_int(value)

                if 10000 <= number <= 999999999:
                    ids.add(number)

        except Exception:
            pass

    return sorted(ids)


# ============================================================
# 배당값 확인
# ============================================================

def valid_odd(value):

    number = to_float(value)

    if number is None:
        return False

    return 1.01 <= number <= 100


# ============================================================
# 3개 배당 추출
# ============================================================

def extract_triplets(text):

    if not text:
        return []

    results = []

    pattern = (
        r"(\d+(?:\.\d+)?)"
        r"\s*[,/|]\s*"
        r"(\d+(?:\.\d+)?)"
        r"\s*[,/|]\s*"
        r"(\d+(?:\.\d+)?)"
    )

    for match in re.findall(
        pattern,
        text
    ):

        h = to_float(match[0])
        d = to_float(match[1])
        a = to_float(match[2])

        if (
            valid_odd(h)
            and valid_odd(d)
            and valid_odd(a)
        ):

            results.append(
                (
                    h,
                    d,
                    a
                )
            )

    return results


# ============================================================
# 페이지에서 숫자 3개씩 찾기
# ============================================================

def extract_three_odds(text):

    if not text:
        return []

    numbers = re.findall(
        r"(?<![\d.])"
        r"\d+\.\d+"
        r"(?![\d.])",
        text
    )

    values = []

    for value in numbers:

        number = to_float(value)

        if valid_odd(number):
            values.append(number)

    results = []

    index = 0

    while index + 2 < len(values):

        h = values[index]
        d = values[index + 1]
        a = values[index + 2]

        results.append(
            (
                h,
                d,
                a
            )
        )

        index += 3

    return results


# ============================================================
# 팀명 후보 정리
# ============================================================

def clean_team_name(value):

    if not value:
        return ""

    text = clean_text(value)

    text = re.sub(
        r"^\d+[:.]\d+$",
        "",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# 경기 행 파싱
# ============================================================

def parse_rows(html):

    if not html:
        return []

    results = []

    rows = re.findall(
        r"<tr[^>]*>(.*?)</tr>",
        html,
        flags=re.I | re.S
    )

    for row in rows:

        text = clean_text(row)

        if not text:
            continue

        odds = extract_triplets(text)

        if not odds:
            odds = extract_three_odds(text)

        if not odds:
            continue

        home_odd, draw_odd, away_odd = odds[0]

        parts = re.split(
            r"\s{2,}|\|",
            text
        )

        parts = [
            clean_team_name(x)
            for x in parts
            if clean_team_name(x)
        ]

        if len(parts) < 2:
            continue

        home = ""
        away = ""

        for part in parts:

            if (
                "." in part
                and re.fullmatch(
                    r"[\d.\s]+",
                    part
                )
            ):
                continue

            if part.lower() in [
                "home",
                "draw",
                "away",
            ]:
                continue

            if not home:
                home = part
                continue

            if not away:
                away = part
                break

        if not home or not away:
            continue

        if home == away:
            continue

        results.append(
            {
                "home_team": home,
                "away_team": away,
                "home_odds": home_odd,
                "draw_odds": draw_odd,
                "away_odds": away_odd,
            }
        )

    return results


# ============================================================
# 전체 페이지 보조 파싱
# ============================================================

def parse_page_fallback(html):

    if not html:
        return []

    text = clean_text(html)

    results = []

    triplets = extract_triplets(
        text
    )

    for index, odd in enumerate(
        triplets
    ):

        h, d, a = odd

        results.append(
            {
                "home_team": f"7M 경기 {index + 1} 홈",
                "away_team": f"7M 경기 {index + 1} 원정",
                "home_odds": h,
                "draw_odds": d,
                "away_odds": a,
            }
        )

    return results


# ============================================================
# 현재 7M 경기 탐색
# ============================================================

def discover_matches():

    add_log(
        "🌐 7M 1X2 페이지 접속"
    )

    response = safe_get(
        ODDS_URL
    )

    if response is None:

        add_log(
            "❌ 7M 페이지 접속 실패"
        )

        return []

    html = response.text

    add_log(
        f"📄 페이지 수신 완료 "
        f"{len(html):,} bytes"
    )

    ids = extract_match_ids(
        html
    )

    add_log(
        f"🔎 경기 ID 후보 {len(ids)}개"
    )

    matches = parse_rows(
        html
    )

    add_log(
        f"📊 HTML 경기행 {len(matches)}개"
    )

    if not matches:

        matches = parse_page_fallback(
            html
        )

        add_log(
            f"📊 보조 파싱 경기 {len(matches)}개"
        )

    unique = {}

    for item in matches:

        key = (
            item["home_team"],
            item["away_team"],
            item["home_odds"],
            item["draw_odds"],
            item["away_odds"],
        )

        unique[key] = item

    return list(
        unique.values()
    )


# ============================================================
# DB 저장
# ============================================================

def save_match_to_database(
    item,
    index
):

    try:

        schedule_id = (
            700000000 + index
        )

        data = {
            "schedule_id": schedule_id,
            "match_date": "",
            "home_team": item[
                "home_team"
            ],
            "away_team": item[
                "away_team"
            ],
            "home_score": None,
            "away_score": None,
            "result": "",
            "source": "7M",
            "odds": [
                {
                    "company": "7M",
                    "home": item[
                        "home_odds"
                    ],
                    "draw": item[
                        "draw_odds"
                    ],
                    "away": item[
                        "away_odds"
                    ],
                }
            ],
        }

        # ----------------------------------------------------
        # 현재 database.py의 save_match 사용
        # ----------------------------------------------------

        if hasattr(
            database,
            "save_match"
        ):

            result = database.save_match(
                data
            )

            return bool(result)

        # ----------------------------------------------------
        # 다른 이름을 사용하는 DB와 호환
        # ----------------------------------------------------

        if hasattr(
            database,
            "save_match_data"
        ):

            result = database.save_match_data(
                data
            )

            return bool(result)

        if hasattr(
            database,
            "insert_match"
        ):

            result = database.insert_match(
                data
            )

            return bool(result)

        if hasattr(
            database,
            "add_match"
        ):

            result = database.add_match(
                data
            )

            return bool(result)

        add_log(
            "❌ database.py에 저장 함수가 없습니다."
        )

        return False

    except Exception as e:

        add_log(
            f"❌ DB 저장 오류: {str(e)[:150]}"
        )

        return False


# ============================================================
# 현재 경기 전체 수집
# ============================================================

def collect_current_matches(
    delay=REQUEST_DELAY
):

    matches = discover_matches()

    total = len(matches)

    with job_lock:

        job["total"] = total

    if total == 0:

        add_log(
            "❌ 수집 가능한 경기를 찾지 못했습니다."
        )

        return

    for index, item in enumerate(
        matches,
        start=1
    ):

        if not is_running():
            break

        saved = save_match_to_database(
            item,
            index
        )

        with job_lock:

            job["current"] = index
            job["last_completed_id"] = (
                700000000 + index
            )

        if saved:

            with job_lock:

                job["success"] += 1
                job["odds"] += 1

            add_log(
                "✅ "
                + str(index)
                + " | "
                + item["home_team"]
                + " vs "
                + item["away_team"]
                + " | "
                + str(item["home_odds"])
                + " / "
                + str(item["draw_odds"])
                + " / "
                + str(item["away_odds"])
            )

        else:

            with job_lock:
                job["failed"] += 1

            add_log(
                "❌ 저장 실패 | "
                + item["home_team"]
                + " vs "
                + item["away_team"]
            )

        if delay > 0:
            time.sleep(delay)


# ============================================================
# ID 범위 수집
# ============================================================

def collect_range(
    start_id,
    end_id,
    selected_companies=None,
    delay=REQUEST_DELAY
):

    start_id = to_int(
        start_id
    )

    end_id = to_int(
        end_id
    )

    with job_lock:

        job["running"] = True
        job["finished"] = False
        job["current"] = 0
        job["total"] = 0
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
        job["start_time"] = (
            datetime.now().isoformat()
        )
        job["end_time"] = ""

    add_log(
        "🚀 7M 수집 시작"
    )

    add_log(
        "입력 ID: "
        + str(start_id)
        + " ~ "
        + str(end_id)
    )

    add_log(
        "ℹ️ 현재 7M 경기 목록을 먼저 탐색합니다."
    )

    try:

        collect_current_matches(
            delay=delay
        )

        with job_lock:

            job["running"] = False
            job["finished"] = True
            job["end_time"] = (
                datetime.now().isoformat()
            )

            if job["success"] > 0:

                job["result"] = "수집 완료"

            elif job["failed"] > 0:

                job["result"] = "저장 실패"

            else:

                job["result"] = (
                    "수집할 경기 없음"
                )

        add_log(
            "🏁 수집 종료 | "
            "성공 "
            + str(job["success"])
            + " | 실패 "
            + str(job["failed"])
            + " | 배당 "
            + str(job["odds"])
        )

    except Exception as e:

        with job_lock:

            job["running"] = False
            job["finished"] = True
            job["error"] = str(e)
            job["result"] = "오류"
            job["end_time"] = (
                datetime.now().isoformat()
            )

        add_log(
            "🔥 수집 오류: "
            + str(e)
        )

    return get_status()


# ============================================================
# 백그라운드 수집
# ============================================================

def start_background_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=REQUEST_DELAY
):

    global worker_thread

    if is_running():
        return False

    def worker():

        collect_range(
            start_id=start_id,
            end_id=end_id,
            selected_companies=selected_companies,
            delay=delay
        )

    worker_thread = threading.Thread(
        target=worker,
        daemon=True
    )

    worker_thread.start()

    return True


# ============================================================
# 기존 app.py 호환
# ============================================================

def start_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=REQUEST_DELAY
):

    return start_background_collection(
        start_id,
        end_id,
        selected_companies,
        delay
    )


def run_collection(
    start_id,
    end_id,
    selected_companies=None,
    delay=REQUEST_DELAY
):

    return collect_range(
        start_id,
        end_id,
        selected_companies,
        delay
    )


# ============================================================
# 진행률
# ============================================================

def get_progress():

    with job_lock:

        total = job["total"]
        current = job["current"]

        if total > 0:

            percent = (
                current
                / total
                * 100
            )

        else:

            percent = 0

        return {
            "current": current,
            "total": total,
            "percent": round(
                percent,
                2
            ),
            "success": job["success"],
            "exists": job["exists"],
            "failed": job["failed"],
            "odds": job["odds"],
            "running": job["running"],
            "finished": job["finished"],
            "last_completed_id":
                job["last_completed_id"],
        }


# ============================================================
# 상태 문자열
# ============================================================

def get_status_text():

    status = get_status()

    if status["running"]:

        progress = get_progress()

        return (
            "수집중 "
            + str(progress["current"])
            + "/"
            + str(progress["total"])
            + " ("
            + str(progress["percent"])
            + "%)"
        )

    if status["finished"]:

        return (
            str(status["result"])
            + " | 성공 "
            + str(status["success"])
            + " | 실패 "
            + str(status["failed"])
        )

    return "대기"


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("7M 축구 최종배당 수집기")
    print("=" * 60)
    print("모듈 정상 로드")
    print(BASE_URL)
