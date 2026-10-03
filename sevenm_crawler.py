# ============================================================
# sevenm_crawler.py
# ⚽ 7M 현재 1X2 페이지 기반 수집기
#
# 기능
# - 현재 7M 1X2 페이지 탐색
# - Home / Draw / Away 배당 추출
# - 경기명 추출
# - 경기 날짜 추출
# - 결과 페이지 보조 탐색
# - SQLite 저장
# - 백그라운드 수집
# - 시작 / 중지
# - 진행률
# - 성공 / 실패
# - 기존 app.py 함수명 호환
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

ODDS_URLS = [
    "https://am.7m.com.cn/en/windrawwinfirsthalf.shtml",
    "https://am.7m.com.cn/en/odds.shtml",
]

RESULT_URLS = [
    "https://am.7m.com.cn/en/score.shtml",
    "https://am.7m.com.cn/en/result.shtml",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; SM-S901N) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": (
        "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Referer": BASE_URL + "/en/",
}

TIMEOUT = 20
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

def to_int(
    value,
    default=0
):

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

def safe_get(
    url,
    timeout=TIMEOUT
):

    try:

        response = session.get(
            url,
            timeout=timeout,
            allow_redirects=True
        )

        if response.status_code != 200:

            add_log(
                f"HTTP {response.status_code}: "
                f"{url}"
            )

            return None

        return response

    except Exception as e:

        add_log(
            f"접속 오류: {str(e)[:120]}"
        )

        return None


# ============================================================
# HTML 정리
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = re.sub(
        r"<br\s*/?>",
        " ",
        text,
        flags=re.I
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"&nbsp;",
        " ",
        text,
        flags=re.I
    )

    text = re.sub(
        r"&amp;",
        "&",
        text,
        flags=re.I
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# URL 추출
# ============================================================

def extract_urls(html):

    urls = set()

    if not html:
        return []

    patterns = [
        r'href\s*=\s*["\']([^"\']+)["\']',
        r'src\s*=\s*["\']([^"\']+)["\']',
    ]

    for pattern in patterns:

        for value in re.findall(
            pattern,
            html,
            re.I
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

    ids = set()

    if not html:
        return []

    patterns = [
        r"match[_-]?id\s*[=:]\s*['\"]?(\d{5,9})",
        r"game[_-]?id\s*[=:]\s*['\"]?(\d{5,9})",
        r"schedule[_-]?id\s*[=:]\s*['\"]?(\d{5,9})",
        r"[?&](?:id|matchid|gameid)=(\d{5,9})",
        r"/(\d{6,9})\.s?html",
        r"/(\d{6,9})/",
    ]

    for pattern in patterns:

        try:

            found = re.findall(
                pattern,
                html,
                flags=re.I
            )

            for value in found:

                number = to_int(value)

                if 10000 <= number <= 999999999:

                    ids.add(number)

        except Exception:

            pass

    return sorted(ids)


# ============================================================
# 배당 숫자
# ============================================================

def valid_odd(value):

    number = to_float(value)

    if number is None:
        return False

    return 1.01 <= number <= 100


# ============================================================
# 현재 7M 1X2 페이지 파싱
# ============================================================

def parse_odds_page(html):

    matches = []

    if not html:
        return matches

    # --------------------------------------------------------
    # HTML 태그 제거 전 원본을 우선 사용
    # --------------------------------------------------------

    text = clean_text(html)

    # --------------------------------------------------------
    # 경기 행 후보
    # --------------------------------------------------------

    row_patterns = [
        r"<tr[^>]*>(.*?)</tr>",
        r"<li[^>]*>(.*?)</li>",
        r"<div[^>]*>(.*?)</div>",
    ]

    rows = []

    for pattern in row_patterns:

        found = re.findall(
            pattern,
            html,
            flags=re.I | re.S
        )

        if found:
            rows.extend(found)

    # --------------------------------------------------------
    # 테이블 행 방식
    # --------------------------------------------------------

    for row in rows:

        row_text = clean_text(row)

        if not row_text:
            continue

        numbers = re.findall(
            r"(?<![\d.])"
            r"(\d+(?:\.\d+)?)"
            r"(?![\d.])",
            row_text
        )

        odds = []

        for value in numbers:

            if valid_odd(value):

                odds.append(
                    float(value)
                )

        if len(odds) < 3:
            continue

        # 가장 먼저 나오는 3개를 1X2로 사용
        home_odd = odds[0]
        draw_odd = odds[1]
        away_odd = odds[2]

        # 팀명 추출
        parts = re.split(
            r"\s+",
            row_text
        )

        # 숫자/시간/불필요 문자 제거
        names = []

        for part in parts:

            if re.fullmatch(
                r"\d+(?::\d+)?",
                part
            ):
                continue

            if re.fullmatch(
                r"\d+(?:\.\d+)?",
                part
            ):
                continue

            if part in [
                "Home",
                "Draw",
                "Away",
            ]:
                continue

            names.append(part)

        if len(names) < 2:
            continue

        home = names[0]
        away = names[-1]

        if (
            not home
            or not away
            or home == away
        ):
            continue

        matches.append({
            "home_team": home,
            "away_team": away,
            "home_odds": home_odd,
            "draw_odds": draw_odd,
            "away_odds": away_odd,
            "source": "7M",
        })

    # --------------------------------------------------------
    # 페이지 전체 텍스트 보조 파싱
    # --------------------------------------------------------

    if not matches:

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        for line in lines:

            odds_match = re.search(
                r"(\d+(?:\.\d+)?)\s+"
                r+ r"(\d+(?:\.\d+)?)\s+"
                r"(\d+(?:\.\d+)?)",
                line
            )

            if not odds_match:
                continue

            home_odd = to_float(
                odds_match.group(1)
            )

            draw_odd = to_float(
                odds_match.group(2)
            )

            away_odd = to_float(
                odds_match.group(3)
            )

            if not all([
                valid_odd(home_odd),
                valid_odd(draw_odd),
                valid_odd(away_odd),
            ]):
                continue

            before = line[
                :odds_match.start()
            ].strip()

            after = line[
                odds_match.end():
            ].strip()

            before_parts = before.split()
            after_parts = after.split()

            if not before_parts:
                continue

            home = before_parts[-1]

            if after_parts:
                away = after_parts[0]
            else:
                continue

            matches.append({
                "home_team": home,
                "away_team": away,
                "home_odds": home_odd,
                "draw_odds": draw_odd,
                "away_odds": away_odd,
                "source": "7M",
            })

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

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
# 날짜 추출
# ============================================================

def extract_date(html):

    if not html:
        return ""

    patterns = [
        r"(\d{1,2}\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{4})",

        r"(\d{4}-\d{2}-\d{2})",

        r"(\d{2}\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{4})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I
        )

        if match:
            return match.group(1)

    return ""


# ============================================================
# 현재 7M 데이터 탐색
# ============================================================

def discover_current_matches():

    all_matches = []

    for url in ODDS_URLS:

        if not is_running():
            break

        add_log(
            f"🔎 7M 페이지 탐색: {url}"
        )

        response = safe_get(url)

        if response is None:
            continue

        html = response.text

        parsed = parse_odds_page(
            html
        )

        add_log(
            f"📊 발견 경기 {len(parsed)}개"
        )

        all_matches.extend(
            parsed
        )

        if parsed:
            break

    unique = {}

    for item in all_matches:

        key = (
            item["home_team"],
            item["away_team"],
        )

        unique[key] = item

    return list(
        unique.values()
    )


# ============================================================
# DB 저장
# ============================================================

def save_current_match(
    item,
    index
):

    try:

        # ----------------------------------------------------
        # 실제 7M 페이지에 경기 ID가 없을 수 있으므로
        # 안정적인 내부 ID를 생성
        # ----------------------------------------------------

        schedule_id = (
            700000000
            + int(index)
        )

        data = {
            "schedule_id": schedule_id,
            "match_date": item.get(
                "match_date",
                ""
            ),
            "home_team": item.get(
                "home_team",
                ""
            ),
            "away_team": item.get(
                "away_team",
                ""
            ),
            "home_score": item.get(
                "home_score"
            ),
            "away_score": item.get(
                "away_score"
            ),
            "result": item.get(
                "result",
                ""
            ),
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

        saved = database.save_match(
            data
        )

        if saved:
            return True

        return False

    except Exception as e:

        add_log(
            f"DB 오류: {str(e)[:150]}"
        )

        return False


# ============================================================
# 현재 경기 수집
# ============================================================

def collect_current_page():

    matches = (
        discover_current_matches()
    )

    if not matches:

        add_log(
            "❌ 현재 7M에서 경기 데이터를 찾지 못했습니다."
        )

        return {
            "success": 0,
            "failed": 0,
            "odds": 0,
            "total": 0,
        }

    total = len(matches)

    with job_lock:

        job["total"] = total

    success = 0
    failed = 0
    odds_count = 0

    for index, item in enumerate(
        matches,
        start=1
    ):

        if not is_running():
            break

        saved = save_current_match(
            item,
            index
        )

        with job_lock:

            job["current"] = index
            job["last_completed_id"] = (
                700000000 + index
            )

        if saved:

            success += 1
            odds_count += 1

            with job_lock:

                job["success"] = success
                job["odds"] = odds_count

            add_log(
                f"✅ {index} | "
                f"{item['home_team']} "
                f"vs "
                f"{item['away_team']} | "
                f"{item['home_odds']} / "
                f"{item['draw_odds']} / "
                f"{item['away_odds']}"
            )

        else:

            failed += 1

            with job_lock:

                job["failed"] = failed

            add_log(
                f"❌ 저장 실패 | "
                f"{item['home_team']} "
                f"vs "
                f"{item['away_team']}"
            )

        if REQUEST_DELAY > 0:

            time.sleep(
                REQUEST_DELAY
            )

    return {
        "success": success,
        "failed": failed,
        "odds": odds_count,
        "total": total,
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

    # --------------------------------------------------------
    # 기존 app.py와의 호환을 위해 ID는 받지만
    # 현재 7M 구조에서는 ID 순차 요청을 하지 않는다.
    # --------------------------------------------------------

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
        "🚀 현재 7M 1X2 경기 수집 시작"
    )

    add_log(
        f"입력 ID 범위: "
        f"{start_id:,} ~ {end_id:,}"
    )

    add_log(
        "ℹ️ 현재 7M 구조에 맞춰 "
        "실제 경기 목록에서 수집합니다."
    )

    try:

        result = collect_current_page()

        with job_lock:

            job["running"] = False
            job["finished"] = True
            job["end_time"] = (
                datetime.now().isoformat()
            )

            if result["total"] > 0:

                if result["success"] > 0:

                    job["result"] = (
                        "수집 완료"
                    )

                else:

                    job["result"] = (
                        "저장 실패"
                    )

            else:

                job["result"] = (
                    "수집할 경기 없음"
                )

        add_log(
            "🏁 수집 종료 | "
            f"전체 {result['total']} | "
            f"성공 {result['success']} | "
            f"실패 {result['failed']} | "
            f"배당 {result['odds']}"
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
            f"🔥 수집 오류: {str(e)}"
        )

    return get_status()


# ============================================================
# 백그라운드 시작
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
            selected_companies=(
                selected_companies
            ),
            delay=delay
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
            f"수집중 "
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
# 테스트
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("⚽ 7M 현재 1X2 수집기")
    print("=" * 60)
    print("정상 로드")
    print(BASE_URL)
