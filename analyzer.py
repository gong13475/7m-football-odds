from database import get_same_odds


def implied_probability(odds):
    if odds is None or odds <= 0:
        return 0.0

    return round(
        100.0 / odds,
        2
    )


def analyze_same_odds(
    home_odds,
    draw_odds,
    away_odds
):
    rows = get_same_odds(
        home_odds,
        draw_odds,
        away_odds
    )

    total = len(rows)

    if total == 0:
        return {
            "total": 0,
            "home": 0.0,
            "draw": 0.0,
            "away": 0.0
        }

    home = sum(
        1 for row in rows
        if row[0] == "H"
    )

    draw = sum(
        1 for row in rows
        if row[0] == "D"
    )

    away = sum(
        1 for row in rows
        if row[0] == "A"
    )

    return {
        "total": total,
        "home": round(
            home / total * 100,
            2
        ),
        "draw": round(
            draw / total * 100,
            2
        ),
        "away": round(
            away / total * 100,
            2
        )
    }
