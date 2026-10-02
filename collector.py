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
    "Accept-Language": "ko-KR,ko;q=0.9"
}

REQUEST_DELAY = 1.5


def probability(odds):
    if odds <= 0:
        return 0.0

    return round(100 / odds, 2)


def result_code(score):
    m = re.search(
        r"(\d+)\s*-\s*(\d+)",
        score or ""
    )

    if not m:
        return None

    home = int(m.group(1))
    away = int(m.group(2))

    if home > away:
        return "H"

    if home == away:
        return "D"

    return "A"


def extract_odds(text):
    values = re.findall(
        r"(?<![\d.])\d+(?:\.\d+)?",
        text
    )
