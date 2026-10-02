from collections import Counter

from database import (
    get_same_odds,
    get_result_counts,
    get_company_counts,
)


def implied_probabilities(
    home_odds,
    draw_odds,
    away_odds
):
    raw = [
        1 / home_odds,
        1 / draw_odds,
        1 / away_odds
    ]

    total = sum(raw)

    return {
        "home": round(raw[0] / total * 100, 2),
        "draw": round(raw[1] / total * 100, 2),
        "away": round(raw[2] / total * 100, 2),
        "margin": round((total - 1) * 100, 2)
    }


def simple_odds_probability(
    home_odds,
    draw_odds,
    away_odds
):
    return {
        "home": round(100 / home_odds, 2),
        "draw": round(100 / draw_odds, 2),
        "away": round(100 / away_odds, 2)
    }


def same_odds_analysis(
    home_odds,
    draw_odds,
    away_odds
):
    rows = get_same_odds(
        home_odds,
        draw_odds,
        away_odds
    )

    counts = Counter(
        row[0]
        for row in rows
    )

    total = len(rows)

    if total == 0:
        return {
            "total": 0,
            "home": 0,
            "draw": 0,
            "away": 0,
            "home_pct": 0,
            "draw_pct": 0,
            "away_pct": 0
        }

    return {
        "total": total,

        "home": counts.get("H", 0),
        "draw": counts.get("D", 0),
        "away": counts.get("A", 0),

        "home_pct": round(
            counts.get("H", 0) / total * 100,
            2
        ),

        "draw_pct": round(
            counts.get("D", 0) / total * 100,
            2
        ),

        "away_pct": round(
            counts.get("A", 0) / total * 100,
            2
        )
    }


def overall_analysis():
    counts = get_result_counts()

    total = sum(counts.values())

    if total == 0:
        return {
            "total": 0,
            "home": 0,
            "draw": 0,
            "away": 0,
            "home_pct": 0,
            "draw_pct": 0,
            "away_pct": 0
        }

    return {
        "total": total,

        "home": counts["H"],
        "draw": counts["D"],
        "away": counts["A"],

        "home_pct": round(
            counts["H"] / total * 100,
            2
        ),

        "draw_pct": round(
            counts["D"] / total * 100,
            2
        ),

        "away_pct": round(
            counts["A"] / total * 100,
            2
        )
    }


def company_analysis():
    return get_company_counts()
