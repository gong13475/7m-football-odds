from collections import Counter
from typing import Iterable, Dict, Any


def implied_probabilities(
    home_odds: float,
    draw_odds: float,
    away_odds: float
) -> Dict[str, float]:

    values = {
        "home": 1 / home_odds,
        "draw": 1 / draw_odds,
        "away": 1 / away_odds,
    }

    total = sum(values.values())

    return {
        key: (value / total) * 100
        for key, value in values.items()
    }


def analyze_same_odds(rows: Iterable):
    """
    rows 형식:
    (match_date, bookmaker, result)

    result:
        H = 홈승
        D = 무승부
        A = 원정승
    """

    rows = list(rows)

    total = len(rows)

    if total == 0:
        return {
            "sample_count": 0,
            "home_count": 0,
            "draw_count": 0,
            "away_count": 0,
            "home_percent": 0.0,
            "draw_percent": 0.0,
            "away_percent": 0.0,
        }

    counter = Counter(
        row[2]
        for row in rows
        if row[2] in ("H", "D", "A")
    )

    home = counter.get("H", 0)
    draw = counter.get("D", 0)
    away = counter.get("A", 0)

    valid_total = home + draw + away

    if valid_total == 0:
        return {
            "sample_count": 0,
            "home_count": 0,
            "draw_count": 0,
            "away_count": 0,
            "home_percent": 0.0,
            "draw_percent": 0.0,
            "away_percent": 0.0,
        }

    return {
        "sample_count": valid_total,

        "home_count": home,
        "draw_count": draw,
        "away_count": away,

        "home_percent": home / valid_total * 100,
        "draw_percent": draw / valid_total * 100,
        "away_percent": away / valid_total * 100,
    }


def build_analysis(
    rows: Iterable,
    home_odds: float,
    draw_odds: float,
    away_odds: float
) -> Dict[str, Any]:

    actual = analyze_same_odds(rows)

    implied = implied_probabilities(
        home_odds,
        draw_odds,
        away_odds
    )

    return {
        "odds": {
            "home": home_odds,
            "draw": draw_odds,
            "away": away_odds,
        },

        "sample_count": actual["sample_count"],

        "actual_probability": {
            "home": actual["home_percent"],
            "draw": actual["draw_percent"],
            "away": actual["away_percent"],
        },

        "implied_probability": implied,

        "counts": {
            "home": actual["home_count"],
            "draw": actual["draw_count"],
            "away": actual["away_count"],
        }
    }
