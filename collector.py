import re
import time
import requests
from bs4 import BeautifulSoup

from database import save_match
from retry_manager import retry


BASE_URL = "https://1x2.7mkr.com/result_kr.shtml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8"
}


def download_day(target_date, cid=""):

    params = {
        "dt": target_date.strftime("%Y-%m-%d")
    }

    if cid:
        params["cid"] = cid

    response = requests.get(
        BASE_URL,
        params=params,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    response.encoding = response.apparent_encoding or "utf-8"

    time.sleep(1)

    return response.text


def clean(text):

    return re.sub(
        r"\s+",
        " ",
        str(text)
    ).strip()


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

    if home < away:
        return "A"

    return "D"


def probability(odds):

    try:

        odds = float(odds)

        if odds <= 0:
            return 0.0

        return round(
            100 / odds,
            2
        )

    except Exception:

        return 0.0


def extract_odds(text):

    numbers = re.findall(
        r"(?<![\d.])\d+(?:\.\d+)?",
        text
    )

    if len(numbers) < 3:
        return None

    try:

        values = [
            float(x)
            for x in numbers[:3]
        ]

        if all(
            value > 1
            for value in values
        ):
            return tuple(values)

    except Exception:
        pass

    return None


def parse_page(html, target_date):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    text = soup.get_text(
        "\n"
    )

    lines = [
        clean(line)
        for line in text.splitlines()
        if clean(line)
    ]

    results = []

    for i, line in enumerate(lines):

        score_match = re.search(
            r"(\d+)\s*-\s*(\d+)",
            line
        )

        if not score_match:
            continue

        score = score_match.group(0)

        result = result_code(score)

        if not result:
            continue

        start = max(
            0,
            i - 20
        )

        end = min(
            len(lines),
            i + 20
        )

        block = lines[
            start:end
        ]

        odds = None

        for item in block:

            candidate = extract_odds(
                item
            )

            if candidate:

                odds = candidate
                break

        if not odds:
            continue

        home_odds = odds[0]
        draw_odds = odds[1]
        away_odds = odds[2]

        results.append({

            "match_date":
                target_date.isoformat(),

            "league":
                "",

            "home_odds":
                home_odds,

            "draw_odds":
                draw_odds,

            "away_odds":
                away_odds,

            "result":
                result,

            "home_probability":
                probability(
                    home_odds
                ),

            "draw_probability":
                probability(
                    draw_odds
                ),

            "away_probability":
                probability(
                    away_odds
                ),

            "source":
                BASE_URL
        })

    return results


def collect_day(target_date, cid=""):

    try:

        html = download_day(
            target_date,
            cid
        )

        rows = parse_page(
            html,
            target_date
        )

        saved = 0

        for row in rows:

            try:

                result = save_match(
                    row
                )

                if result:
                    saved += int(result)

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


def diagnose(target_date, cid=""):

    try:

        html = download_day(
            target_date,
            cid
        )

        return {

            "status": 200,

            "size": len(html),

            "has_result":
                "result_kr" in html,

            "has_compare":
                "비교" in html,

            "html":
                html[:10000]
        }

    except Exception as error:

        return {

            "status": 0,

            "size": 0,

            "has_result": False,

            "has_compare": False,

            "html":
                f"ERROR: {error}"
        }
