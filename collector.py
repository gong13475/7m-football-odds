import re
import time
import requests

from database import (
    save_match,
    save_collection_day,
)


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
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def download_day(target_date, cid=""):
    dt = target_date.strftime("%Y-%m-%d")

    filename = cid if cid else "index"

    url = (
        f"{DATA_BASE}/"
        f"{dt}/"
        f"{filename}.js"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    response.encoding = (
        response.apparent_encoding or "utf-8"
    )

    return response.text


def extract_matches(js):
    results = []

    score_pattern = re.compile(
        r"(\d+)\s*-\s*(\d+)"
    )

    scores = list(
        score_pattern.finditer(js)
    )

    for score in scores:
        home_score = int(score.group(1))
        away_score = int(score.group(2))

        if home_score > away_score:
            result = "H"
        elif home_score < away_score:
            result = "A"
        else:
            result = "D"

        start = max(
            0,
            score.start() - 3000,
        )

        end = min(
            len(js),
            score.end() + 3000,
        )

        block = js[start:end]

        odds = re.findall(
            r"(?<![\d.])"
            r"([1-9]\d*(?:\.\d+)?)"
            r"(?![\d.])",
            block,
        )

        numbers = []

        for value in odds:
            try:
                number = float(value)

                if 1.01 <= number <= 100:
                    numbers.append(number)

            except ValueError:
                pass

        if len(numbers) < 3:
            continue

        found = None

        for i in range(len(numbers) - 2):
            candidate = numbers[i:i + 3]

            if all(x > 1 for x in candidate):
                found = candidate
                break

        if found is None:
            continue

        results.append({
            "home_odds": found[0],
            "draw_odds": found[1],
            "away_odds": found[2],
            "result": result,
        })

    return results


def collect_day(
    target_date,
    cid="",
    company="미지정",
    retries=3,
    retry_delay=2,
):
    last_error = ""

    for attempt in range(1, retries + 1):
        try:
            js = download_day(
                target_date,
                cid,
            )

            rows = extract_matches(js)

            saved = 0

            for row in rows:
                data = {
                    "match_date":
                        target_date.isoformat(),

                    "league": "",

                    "home_team": "",
                    "away_team": "",

                    "company":
                        company or "미지정",

                    "home_odds":
                        row["home_odds"],

                    "draw_odds":
                        row["draw_odds"],

                    "away_odds":
                        row["away_odds"],

                    "result":
                        row["result"],

                    "home_probability":
                        round(
                            100 / row["home_odds"],
                            2,
                        ),

                    "draw_probability":
                        round(
                            100 / row["draw_odds"],
                            2,
                        ),

                    "away_probability":
                        round(
                            100 / row["away_odds"],
                            2,
                        ),

                    "source": DATA_BASE,
                }

                try:
                    saved += int(
                        save_match(data) or 0
                    )
                except Exception:
                    continue

            save_collection_day(
                target_date,
                "success",
                len(rows),
                saved,
                "",
            )

            return {
                "success": True,
                "found": len(rows),
                "saved": saved,
                "error": None,
                "attempt": attempt,
            }

        except Exception as error:
            last_error = str(error)

            if attempt < retries:
                time.sleep(retry_delay)

    # 재시도 전부 실패 → 날짜 건너뛰기
    save_collection_day(
        target_date,
        "skipped",
        0,
        0,
        last_error,
    )

    return {
        "success": False,
        "found": 0,
        "saved": 0,
        "error": last_error,
        "skipped": True,
        "attempt": retries,
    }


def diagnose(target_date, cid=""):
    try:
        js = download_day(
            target_date,
            cid,
        )

        rows = extract_matches(js)

        return {
            "status": 200,
            "size": len(js),
            "has_result": True,
            "has_compare":
                "비교" in js,
            "found": len(rows),
            "html": js[:10000],
        }

    except Exception as error:
        return {
            "status": 0,
            "size": 0,
            "has_result": False,
            "has_compare": False,
            "found": 0,
            "html": f"ERROR: {error}",
        }
