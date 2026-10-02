from collections import Counter

import database


RESULT_LABELS = {
    "H": "승",
    "D": "무",
    "A": "패"
}


def implied_probability(odds):

    odds = float(odds)

    if odds <= 0:
        return 0.0

    return 100.0 / odds


def normalized_probabilities(
    home,
    draw,
    away
):

    values = [

        implied_probability(home),
        implied_probability(draw),
        implied_probability(away)

    ]

    total = sum(values)

    if total <= 0:

        return [
            0.0,
            0.0,
            0.0
        ]


    return [

        value / total * 100

        for value in values

    ]


def search_same_odds(
    home,
    draw,
    away
):

    return database.get_same_odds(
        home,
        draw,
        away
    )


def calculate_statistics(rows):

    total = len(rows)


    counts = Counter(
        row.get("result")
        for row in rows
    )


    if total == 0:

        return {

            "total": 0,

            "counts": {
                "H": 0,
                "D": 0,
                "A": 0
            },

            "actual": {
                "H": 0.0,
                "D": 0.0,
                "A": 0.0
            },

            "expected": {
                "H": 0.0,
                "D": 0.0,
                "A": 0.0
            },

            "difference": {
                "H": 0.0,
                "D": 0.0,
                "A": 0.0
            }
        }


    actual = {

        key:
            counts.get(key, 0)
            / total
            * 100

        for key in [
            "H",
            "D",
            "A"
        ]
    }


    expected_values = []


    for row in rows:

        probs = normalized_probabilities(

            row["home_odds"],
            row["draw_odds"],
            row["away_odds"]

        )

        expected_values.append(
            probs
        )


    expected = {

        "H":
            sum(
                x[0]
                for x in expected_values
            ) / total,

        "D":
            sum(
                x[1]
                for x in expected_values
            ) / total,

        "A":
            sum(
                x[2]
                for x in expected_values
            ) / total
    }


    difference = {

        key:
            actual[key]
            - expected[key]

        for key in [
            "H",
            "D",
            "A"
        ]
    }


    return {

        "total":
            total,

        "counts": {

            "H":
                counts.get("H", 0),

            "D":
                counts.get("D", 0),

            "A":
                counts.get("A", 0)
        },

        "actual":
            actual,

        "expected":
            expected,

        "difference":
            difference
    }


def calculate_company_analysis(
    results,
    company="7M"
):

    if not results:
        return None


    stats = calculate_statistics(
        results
    )


    return {

        "company":
            company,

        "total":
            stats["total"],

        "counts":
            stats["counts"],

        "actual":
            stats["actual"],

        "expected":
            stats["expected"],

        "difference":
            stats["difference"]
    }


def run_search(
    home,
    draw,
    away
):

    try:

        home = float(home)
        draw = float(draw)
        away = float(away)


        if (
            home <= 1.0
            or draw <= 1.0
            or away <= 1.0
        ):

            raise ValueError(
                "배당은 모두 1.01 이상이어야 합니다."
            )


        rows = search_same_odds(
            home,
            draw,
            away
        )


        stats = calculate_statistics(
            rows
        )


        return {

            "success":
                True,

            "message":
                "검색 완료",

            "results":
                rows,

            "statistics":
                stats
        }


    except Exception as error:

        return {

            "success":
                False,

            "message":
                str(error),

            "results":
                [],

            "statistics":
                {}
        }


def get_company_list():

    return ["7M"]


def result_label(result):

    return RESULT_LABELS.get(
        result,
        result
    )
