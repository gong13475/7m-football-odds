import re
import time
import requests

from bs4 import BeautifulSoup

from database import save_match
from retry_manager import retry


BASE_URL = "https://1x2.7mkr.com/result_kr.shtml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Linux; Android 10) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9"
}

REQUEST_DELAY = 1.5


def probability(odds):
    if odds <= 0:
        return 0.0

    return round(
        100 / odds,
        2
    )


def result_code(score):
    match = re.search(
        r"(\d+)\s*-\s*(\d+)",
        score or ""
    )

    if not match:
        return None

    home = int(match.group(1))
    away = int(match.group(2))

    if home > away:
        return "H"

    if home == away:
        return "D"

    return "A"


def extract_odds(text):
    """
    1.93 3.60 3.10
    형태의 1X2 배당 3개 추출
    """

    values = re.findall(
        r"(?<![\d.])\d+(?:\.\d+)?",
        text
    )

    if len(values) < 3:
        return None

    try:
        return (
            float(values[0]),
            float(values[1]),
            float(values[2])
        )

    except ValueError:
        return None


def clean(text):
    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def parse_text_page(
    html,
    target_date
):
    """
    페이지의 텍스트 구조를 기준으로 파싱.

    핵심 규칙:

    초기배당
    결과
    비교
    최종배당

    여기서 비교 이후 첫 번째
    1X2 숫자 3개를 최종배당으로 사용.
    """

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    lines = [
        clean(x)
        for x in soup.get_text("\n").splitlines()
        if clean(x)
    ]

    results = []

    for index, line in enumerate(lines):

        score_match = re.search(
            r"\(\s*\d+\s*-\s*\d+\s*\)|"
            r"\d+\s*-\s*\d+",
            line
        )

        if not score_match:
            continue

        score = score_match.group(0)

        score = score.replace(
            "(",
            ""
        ).replace(
            ")",
            ""
        )

        result = result_code(score)

        if result is None:
            continue

        start = max(
            0,
            index - 12
        )

        end = min(
            len(lines),
            index + 12
        )

        block = lines[start:end]

        compare_index = None

        for i, item in enumerate(block):

            if "비교" in item:
                compare_index = i
                break

        if compare_index is None:
            continue

        after_compare = block[
            compare_index + 1:
        ]

        final_odds = None

        for item in after_compare:

            odds = extract_odds(item)

            if odds is None:
                continue

            final_odds = odds
            break

        if final_odds is None:
            continue

        home, draw, away = final_odds

        if (
            home <= 1.0
            or draw <= 1.0
            or away <= 1.0
        ):
            continue

        results.append({
            "match_date":
                target_date.isoformat(),

            "league": "",

            "home_odds":
                home,

            "draw_odds":
                draw,

            "away_odds":
                away,

            "result":
                result,

            "home_probability":
                probability(home),

            "draw_probability":
                probability(draw),

            "away_probability":
                probability(away),

            "source":
                BASE_URL
        })

    return results


def download_day(
    target_date,
    cid=""
):
    """
    실제 확인된 형식:

    result_kr.shtml?cid=&dt=YYYY-MM-DD

    cid가 없으면 빈 값 사용.
    """

    response = requests.get(
        BASE_URL,
        params={
            "cid": cid,
            "dt":
                target_date.isoformat()
        },
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    # 일시적인 과도한 요청 방지
    time.sleep(REQUEST_DELAY)

    return response.text


def collect_day(
    target_date,
    cid=""
):
    ok, result = retry(
        lambda:
            download_day(
                target_date,
                cid
            ),
        attempts=3,
        delay=3
    )

    if not ok:

        return {
            "success": False,
            "saved": 0,
            "error": str(result)
        }

    try:

        rows = parse_text_page(
            result,
            target_date
        )

        saved = 0

        for row in rows:

            inserted = save_match(row)

            if inserted:
                saved += inserted

        return {
            "success": True,
            "saved": saved,
            "found": len(rows),
            "error": None
        }

    except Exception as error:

        return {
            "success": False,
            "saved": 0,
            "found": 0,
            "error": str(error)
                }
