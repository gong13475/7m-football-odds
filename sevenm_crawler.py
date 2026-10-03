# ============================================================
# sevenm_crawler.py
# ⚽ 7M 축구 최종배당 수집기
# ============================================================

import re
import time
import threading
from datetime import datetime

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
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

TIMEOUT = 15
REQUEST_DELAY = 0.5


# ============================================================
# Session
# ============================================================

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# 작업 상태
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


# ============================================================
# 중지
# ============================================================

def stop_collection():

    with job_lock:
        job["running"] = False

    add_log("⛔ 수집 중지 요청")

    return True


# ============================================================
# 숫자
# ============================================================

def to_int(value, default=0):

    try:

        if value is None:
            return default

        match = re.search(
            r"-?\d+",
            str(value)
        )

        if not match:
            return default

        return int(match.group())

    except Exception:

        return default


def to_float(value):

    try:

        if value is None:
            return None

        text = str(value)
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
# GET
# ============================================================

def safe_get(url, timeout=TIMEOUT):

    try:

        response = session.get(
            url,
            timeout=timeout,
            allow_redirects=True,
        )

        if response.status_code != 200:
            return None

        return response

    except Exception as e:

        add_log(
            f"GET 오류: {str(e)[:100]}"
        )

        return None


# ============================================================
# 경기 URL 후보
# ============================================================

def match_url_candidates(match_id):

    mid = str(match_id)

    return [
        f"{BASE_URL}/match/{mid}",
        f"{BASE_URL}/match/{mid}/",
        f"{BASE_URL}/match/data-{mid}",
        f"{BASE_URL}/match/data-{mid}/",
        f"https://www.7m.com.cn/match/{mid}",
        f"https://www.7m.com.cn/match/{mid}/",
    ]


# ============================================================
# 경기 페이지
# ============================================================

def get_match_page(match_id):

    for url in match_url_candidates(match_id):

        if not is_running():
            return None, None

        response = safe_get(url)

        if response is None:
            continue

        html = response.text

        if len(html) < 100:
            continue

        return url, html

    return None, None


# ============================================================
# HTML 정리
# ============================================================

def clean_html(text):

    if not text:
        return ""

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

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# 팀명
# ============================================================

def find_team_names(html):

    home = ""
    away = ""

    if not html:
        return home, away

    patterns = [
        (
            r'"homeTeam"\s*:\s*"([^"]+)"',
            r'"awayTeam"\s*:\s*"([^"]+)"'
        ),
        (
            r'"homeName"\s*:\s*"([^"]+)"',
            r'"awayName"\s*:\s*"([^"]+)"'
        ),
        (
            r'"home_name"\s*:\s*"([^"]+)"',
            r'"away_name"\s*:\s*"([^"]+)"'
        ),
        (
            r'data-home=["\']([^"\']+)["\']',
            r'data-away=["\']([^"\']+)["\']'
        ),
    ]

    for home_pattern, away_pattern in patterns:

        hm = re.search(
            home_pattern,
            html,
            re.I
        )

        am = re.search(
            away_pattern,
            html,
            re.I
        )

        if hm and am:

            home = clean_html(
                hm.group(1)
            )

            away = clean_html(
                am.group(1)
            )

            if home and away:
                return home, away

    return "", ""


# ============================================================
# 점수
# ============================================================

def extract_score(html):

    if not html:
        return None, None

    patterns = [
        (
            r'"homeScore"\s*:\s*(\d+)'
            r'.*?'
            r'"awayScore"\s*:\s*(\d+)'
        ),
        (
            r'"home_score"\s*:\s*(\d+)'
            r'.*?'
            r'"away_score"\s*:\s*(\d+)'
        ),
        (
            r'"homeGoals"\s*:\s*(\d+)'
            r'.*?'
            r'"awayGoals"\s*:\s*(\d+)'
        ),
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if match:

            return (
                to_int(match.group(1)),
                to_int(match.group(2)),
            )

    return None, None


# ============================================================
# 결과
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
# 날짜
# ============================================================

def extract_match_date(html):

    if not html:
        return ""

    patterns = [
        r'"matchDate"\s*:\s*"([^"]+)"',
        r'"match_date"\s*:\s*"([^"]+)"',
        r'"startTime"\s*:\s*"([^"]+)"',
        r'"date"\s*:\s*"([^"]+)"',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I
        )

        if match:
            return match.group(1).strip()

    return ""


# ============================================================
# 배당 추출
# ============================================================

def extract_odds(html):

    results = []

    if not html:
        return results

    patterns = [
        (
            r"(\d{1,2}\.\d{1,3})"
            r"\s*[,/|]\s*"
            r"(\d{1,2}\.\d{1,3})"
            r"\s*[,/|]\s*"
            r"(\d{1,2}\.\d{1,3})"
        ),
        (
            r'"homeOdds"\s*:\s*"?'
            r"(\d+(?:\.\d+)?)"
            r'".*?'
            r'"drawOdds"\s*:\s*"?'
            r"(\d+(?:\.\d+)?)"
            r'".*?'
            r'"awayOdds"\s*:\s*"?'
            r"(\d+(?:\.\d+)?)"
        ),
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            re.I | re.S
        )

        for match in matches:

            if len(match) != 3:
                continue

            home = to_float(match[0])
            draw = to_float(match[1])
            away = to_float(match[2])

            if (
                home is None
                or draw is None
                or away is None
            ):
                continue

            if not (
                1.01 <= home <= 100
                and 1.01 <= draw <= 100
                and 1.01 <= away <= 100
            ):
                continue

            results.append({
                "company": "7M",
                "home": home,
                "draw": draw,
                "away": away,
            })

    unique = {}

    for item in results:

        key = (
            item["company"],
            item["home"],
            item["draw"],
            item["away"],
        )

        unique[key] = item

    return list(
        unique.values()
    )


# ============================================================
# 경기 데이터
# ============================================================

def parse_match_data(
    match_id,
    html
):

    home, away = find_team_names(
        html
    )

    home_score, away_score = (
        extract_score(html)
    )

    result = calculate_result(
        home_score,
        away_score
    )

    match_date = (
        extract_match_date(html)
    )

    odds = extract_odds(
        html
    )

    data = {
        "schedule_id": int(match_id),
        "match_date": match_date,
        "home_team": home,
        "away_team": away,
        "home_score": home_score,
        "away_score": away_score,
        "result": result,
        "source": "7M",
        "odds": odds,
    }

    return data


# ============================================================
# DB 저장
# ============================================================

def save_match_to_database(
    data
):

    try:

        return database.save_match(
            data
        )

    except Exception as e:

        add_log(
            "DB 저장 오류 "
            f"ID {data.get('schedule_id')}: "
            f"{str(e)[:150]}"
        )

        return False


# ============================================================
# 경기 1개 수집
# ============================================================

def collect_one_match(
    match_id
):

    if not is_running():

        return {
            "status": "stopped",
            "match_id": match_id,
        }

    try:

        url, html = get_match_page(
            match_id
        )

        if html is None:

            return {
                "status": "failed",
                "match_id": match_id,
                "error": "경기 페이지 없음",
            }

        data = parse_match_data(
            match_id,
            html
        )

        data["url"] = url

        if (
            not data["home_team"]
            or not data["away_team"]
        ):

            return {
                "status": "failed",
                "match_id": match_id,
                "error": "팀명 추출 실패",
            }

        saved = save_match_to_database(
            data
        )

        if not saved:

            return {
                "status": "failed",
                "match_id": match_id,
                "error": "DB 저장 실패",
            }

        return {
            "status": "success",
            "match_id": match_id,
            "odds": len(
                data["odds"]
            ),
            "data": data,
        }

    except Exception as e:

        return {
            "status": "failed",
            "match_id": match_id,
            "error": str(e),
        }


# ============================================================
# 범위 수집
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

    if start_id <= 0 or end_id <= 0:

        raise ValueError(
            "경기 ID가 올바르지 않습니다."
        )

    if end_id < start_id:

        start_id, end_id = (
            end_id,
            start_id
        )

    total = (
        end_id
        - start_id
        + 1
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
        job["start_time"] = (
            datetime.now().isoformat()
        )
        job["end_time"] = ""

    add_log(
        f"🚀 7M 수집 시작 "
        f"{start_id:,} ~ {end_id:,}"
    )

    for match_id in range(
        start_id,
        end_id + 1
    ):

        if not is_running():

            add_log(
                "⛔ 수집 중지"
            )

            break

        result = collect_one_match(
            match_id
        )

        status = result.get(
            "status"
        )

        with job_lock:

            job["current"] += 1
            job["last_completed_id"] = (
                match_id
            )

        if status == "success":

            odds_count = result.get(
                "odds",
                0
            )

            data = result.get(
                "data",
                {}
            )

            with job_lock:

                job["success"] += 1
                job["odds"] += odds_count

            add_log(
                f"✅ {match_id} | "
                f"{data.get('home_team', '')} "
                f"vs "
                f"{data.get('away_team', '')} | "
                f"결과 {data.get('result', '')} | "
                f"배당 {odds_count}개"
            )

        elif status == "stopped":

            break

        else:

            with job_lock:
                job["failed"] += 1

            add_log(
                f"❌ {match_id} | "
                f"{result.get('error', '실패')}"
            )

        if delay > 0:

            time.sleep(
                float(delay)
            )

    with job_lock:

        job["running"] = False
        job["finished"] = True
        job["end_time"] = (
            datetime.now().isoformat()
        )

        if (
            job["current"]
            >= job["total"]
        ):
            job["result"] = "수집 완료"

        else:
            job["result"] = "수집 중지"

        success = job["success"]
        failed = job["failed"]
        odds = job["odds"]

    add_log(
        f"🏁 수집 종료 | "
        f"성공 {success} | "
        f"실패 {failed} | "
        f"배당 {odds}"
    )

    return get_status()


# ============================================================
# 백그라운드
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

        try:

            collect_range(
                start_id=start_id,
                end_id=end_id,
                selected_companies=(
                    selected_companies
                ),
                delay=delay,
            )

        except Exception as e:

            with job_lock:

                job["running"] = False
                job["finished"] = True
                job["error"] = str(e)
                job["result"] = "오류"

            add_log(
                f"🔥 수집 오류: {str(e)}"
            )

    worker_thread = threading.Thread(
        target=worker,
        daemon=True
    )

    worker_thread.start()

    return True


# ============================================================
# 별칭
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
            f"{progress['current']:,}/"
            f"{progress['total']:,} "
            f"({progress['percent']:.1f}%)"
        )

    if status["finished"]:

        return (
            f"{status['result']} | "
            f"성공 {status['success']:,} | "
            f"실패 {status['failed']:,}"
        )

    return "대기"


# ============================================================
# 모듈 테스트
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("⚽ 7M 축구 최종배당 수집기")
    print("=" * 60)
    print("정상적으로 로드되었습니다.")
    print("BASE_URL:", BASE_URL)
