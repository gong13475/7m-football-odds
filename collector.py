import re
import time
import requests

from database import save_match


BASE_URL = "https://1x2.7mkr.com/result_kr.shtml"

DATA_BASE = (
    "https://px-1x2.7mdt.com/"
    "data/history/kr"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "ko-KR,ko;q=0.9"
}


def download_day(
    target_date,
    cid="",
    retries=3,
    timeout=30
):
    dt = target_date.strftime("%Y-%m-%d")

    filename = cid if cid else "index"

    url = (
        f"{DATA_BASE}/"
        f"{dt}/"
        f"{filename}.js"
    )

    last_error = None

    for attempt in range(retries):
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=timeout
            )

            response.raise_for_status()

            response.encoding = (
                response.apparent_encoding
                or "utf-8"
            )

            return response.text

        except Exception as error:
            last_error = error

            if attempt < retries - 1:
                time.sleep(
                    2 ** attempt
                )

    raise RuntimeError(
        f"다운로드 실패: {last_error}"
    )


def _number(value):
    try:
        return float(value)
    except Exception:
        return None


def _valid_odds(values):
    return [
        x for x in values
        if 1.01 <= x <= 100
    ]


def extract_matches(js):
    """
    7M history JS에서
    결과와 1X2 배당 후보를 추출한다.

    사이트 JS 구조가 변경될 경우
    이 함수만 수정하면 된다.
    """

    results = []

    score_pattern = re.compile(
        r"(\d+)\s*-\s*(\d+)"
    )

    scores = list(
        score_pattern.finditer(js)
    )

    used_positions = set()

    for score_match in scores:

        if score_match.start() in used_positions:
            continue

        home_score = int(
            score_match.group(1)
        )

        away_score = int(
            score_match.group(2)
        )

        if home_score > away_score:
            result = "H"
        elif home_score < away_score:
            result = "A"
        else:
            result = "D"

        start = max(
            0,
            score_match.start() - 4000
        )

        end = min(
            len(js),
            score_match.end() + 4000
        )

        block = js[start:end]

        number_strings = re.findall(
            r"(?<![\d.])"
            r"([1-9]\d*(?:\.\d+)?)"
            r"(?![\d.])",
            block
        )

        numbers = _valid_odds([
            _number(x)
            for x in number_strings
        ])

        found = None

        for i in range(
            len(numbers) - 2
        ):
            candidate = numbers[
                i:i + 3
            ]

            if len(candidate) != 3:
                continue

            if all(
                1.01 <= x <= 100
                for x in candidate
            ):
                found = candidate
                break

        if found is None:
            continue

        results.append({
            "home_odds": found[0],
            "draw_odds": found[1],
            "away_odds": found[2],
            "result": result
        })

        used_positions.add(
            score_match.start()
        )

    return results


def collect_day(
    target_date,
    cid=""
):
    try:
        js = download_day(
            target_date,
            cid=cid
        )

        rows = extract_matches(js)

        saved = 0

        for row in rows:

            home_odds = row["home_odds"]
            draw_odds = row["draw_odds"]
            away_odds = row["away_odds"]

            data = {
                "match_date":
                    target_date.isoformat(),

                "league":
                    "",

                "home_team":
                    "",

                "away_team":
                    "",

                "company":
                    cid if cid else "전체",

                "home_odds":
                    home_odds,

                "draw_odds":
                    draw_odds,

                "away_odds":
                    away_odds,

                "result":
                    row["result"],

                "home_probability":
                    round(
                        100 / home_odds,
                        2
                    ),

                "draw_probability":
                    round(
                        100 / draw_odds,
                        2
                    ),

                "away_probability":
                    round(
                        100 / away_odds,
                        2
                    ),

                "source":
                    DATA_BASE
            }

            try:
                saved += int(
                    save_match(data)
                )

            except Exception:
                continue

        return {
            "success": True,
            "found": len(rows),
            "saved": saved,
            "error": None
        }

    except Exception as error:

        return {
            "success": False,
            "found": 0,
            "saved": 0,
            "error": str(error)
        }


def diagnose(
    target_date,
    cid=""
):
    try:

        js = download_day(
            target_date,
            cid=cid
        )

        rows = extract_matches(js)

        return {
            "status": 200,
            "size": len(js),
            "has_result":
                len(js) > 0,
            "has_compare":
                "비교" in js,
            "found": len(rows),
            "html": js[:10000]
        }

    except Exception as error:

        return {
            "status": 0,
            "size": 0,
            "has_result": False,
            "has_compare": False,
            "found": 0,
            "html":
                f"ERROR: {error}"
        }
