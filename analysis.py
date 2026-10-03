# ============================================================
# analysis.py
# ⚽ 7M 축구 최종배당 분석
#
# 기능
# ------------------------------------------------------------
# 1. 전체 승 / 무 / 패 통계
# 2. 확률 계산
# 3. 배당 → 예상확률 계산
# 4. 확률 대비 실제 결과 분석
# 5. 동일배당 분석
# 6. 배당 구간 분석
# 7. 업체별 분석
# 8. 홈 / 무 / 원정 적중률
# 9. 배당별 실제 결과
# 10. 부족확률 계산
# 11. 앱에서 바로 사용할 수 있는 함수 제공
# ============================================================

from collections import defaultdict
import math

import database


# ============================================================
# 기본값
# ============================================================

RESULTS = [
    "승",
    "무",
    "패",
]


# ============================================================
# 안전한 숫자 변환
# ============================================================

def to_float(value):

    try:

        if value is None:
            return None

        return float(
            str(value)
            .replace(",", "")
            .strip()
        )

    except Exception:

        return None


# ============================================================
# 퍼센트
# ============================================================

def percentage(
    value,
    total
):

    try:

        if total <= 0:
            return 0.0

        return (
            float(value)
            / float(total)
            * 100
        )

    except Exception:

        return 0.0


# ============================================================
# 배당 → 예상확률
#
# 단순 확률:
# 1 / 배당
#
# 실제 분석에서는 3개 배당의 합을 이용하여
# 마진을 제거한 정규화 확률을 사용
# ============================================================

def odds_to_probability(
    home_odds,
    draw_odds,
    away_odds
):

    h = to_float(
        home_odds
    )

    d = to_float(
        draw_odds
    )

    a = to_float(
        away_odds
    )

    if not h or not d or not a:
        return None

    if h <= 1 or d <= 1 or a <= 1:
        return None

    try:

        hp = 1 / h
        dp = 1 / d
        ap = 1 / a

        total = (
            hp + dp + ap
        )

        if total <= 0:
            return None

        return {
            "home": hp / total * 100,
            "draw": dp / total * 100,
            "away": ap / total * 100,
        }

    except Exception:

        return None


# ============================================================
# 단순 예상확률
# ============================================================

def simple_probability(
    odds
):

    value = to_float(
        odds
    )

    if not value or value <= 1:
        return 0.0

    return (
        1 / value * 100
    )


# ============================================================
# 배당 문자열
# ============================================================

def odds_key(
    value
):

    value = to_float(
        value
    )

    if value is None:
        return ""

    return f"{value:.2f}"


# ============================================================
# 결과 정규화
# ============================================================

def normalize_result(
    result
):

    if result is None:
        return ""

    text = str(
        result
    ).strip()

    mapping = {

        "W": "승",
        "WIN": "승",
        "H": "승",

        "D": "무",
        "DRAW": "무",
        "X": "무",

        "L": "패",
        "LOSE": "패",
        "LOSS": "패",
        "A": "패",
    }

    upper = text.upper()

    if upper in mapping:
        return mapping[
            upper
        ]

    if text in RESULTS:
        return text

    return text


# ============================================================
# 데이터 불러오기
# ============================================================

def load_data(
    bookmaker=None,
    limit=100000
):

    return database.get_analysis_data(
        bookmaker=bookmaker,
        limit=limit
    )


# ============================================================
# 전체 승무패 통계
# ============================================================

def result_statistics(
    data=None,
    bookmaker=None
):

    if data is None:

        data = load_data(
            bookmaker=bookmaker
        )

    counts = {
        "승": 0,
        "무": 0,
        "패": 0,
    }

    for row in data:

        result = normalize_result(
            row.get("result")
        )

        if result in counts:

            counts[result] += 1

    total = sum(
        counts.values()
    )

    return {

        "total": total,

        "승": counts["승"],

        "무": counts["무"],

        "패": counts["패"],

        "승률": percentage(
            counts["승"],
            total
        ),

        "무승부율": percentage(
            counts["무"],
            total
        ),

        "패율": percentage(
            counts["패"],
            total
        ),

    }


# ============================================================
# 간단한 결과 통계
# ============================================================

def get_result_statistics(
    data=None
):

    return result_statistics(
        data=data
    )


# ============================================================
# 업체 목록
# ============================================================

def get_bookmakers():

    rows = database.get_bookmakers()

    return [
        row["bookmaker"]
        for row in rows
    ]


# ============================================================
# 업체별 통계
# ============================================================

def bookmaker_statistics(
    data=None
):

    if data is None:

        data = load_data()

    groups = defaultdict(
        list
    )

    for row in data:

        bookmaker = (
            row.get(
                "bookmaker"
            )
            or "7M"
        )

        groups[
            bookmaker
        ].append(row)

    result = []

    for bookmaker, rows in groups.items():

        stats = result_statistics(
            data=rows
        )

        stats[
            "bookmaker"
        ] = bookmaker

        result.append(
            stats
        )

    result.sort(
        key=lambda x:
            x["total"],
        reverse=True
    )

    return result


# ============================================================
# 업체별 통계 별칭
# ============================================================

def get_bookmaker_statistics(
    data=None
):

    return bookmaker_statistics(
        data=data
    )


# ============================================================
# 배당별 동일 배당 분석
# ============================================================

def exact_odds_analysis(
    data=None,
    decimals=2
):

    if data is None:

        data = load_data()

    groups = defaultdict(
        list
    )

    for row in data:

        h = to_float(
            row.get(
                "home_odds"
            )
        )

        d = to_float(
            row.get(
                "draw_odds"
            )
        )

        a = to_float(
            row.get(
                "away_odds"
            )
        )

        result = normalize_result(
            row.get(
                "result"
            )
        )

        if (
            h is None
            or d is None
            or a is None
        ):
            continue

        if result not in RESULTS:
            continue

        key = (
            round(h, decimals),
            round(d, decimals),
            round(a, decimals),
        )

        groups[key].append(
            result
        )

    output = []

    for key, results in groups.items():

        total = len(
            results
        )

        counts = {
            "승": results.count("승"),
            "무": results.count("무"),
            "패": results.count("패"),
        }

        output.append({

            "home_odds": key[0],

            "draw_odds": key[1],

            "away_odds": key[2],

            "total": total,

            "승": counts["승"],

            "무": counts["무"],

            "패": counts["패"],

            "승률": percentage(
                counts["승"],
                total
            ),

            "무승부율": percentage(
                counts["무"],
                total
            ),

            "패율": percentage(
                counts["패"],
                total
            ),

        })

    output.sort(
        key=lambda x:
            x["total"],
        reverse=True
    )

    return output


# ============================================================
# 동일 무배당 분석
# ============================================================

def exact_draw_odds_analysis(
    data=None,
    decimals=2
):

    if data is None:

        data = load_data()

    groups = defaultdict(
        list
    )

    for row in data:

        draw = to_float(
            row.get(
                "draw_odds"
            )
        )

        result = normalize_result(
            row.get(
                "result"
            )
        )

        if draw is None:
            continue

        if result not in RESULTS:
            continue

        key = round(
            draw,
            decimals
        )

        groups[
            key
        ].append(result)

    output = []

    for draw, results in groups.items():

        total = len(
            results
        )

        win = results.count(
            "승"
        )

        draw_count = results.count(
            "무"
        )

        lose = results.count(
            "패"
        )

        output.append({

            "draw_odds": draw,

            "total": total,

            "승": win,

            "무": draw_count,

            "패": lose,

            "승률": percentage(
                win,
                total
            ),

            "무승부율": percentage(
                draw_count,
                total
            ),

            "패율": percentage(
                lose,
                total
            ),

        })

    output.sort(
        key=lambda x:
            x["total"],
        reverse=True
    )

    return output


# ============================================================
# 배당 구간
# ============================================================

def odds_bucket(
    odds,
    step=0.10
):

    value = to_float(
        odds
    )

    if value is None:
        return None

    if value <= 1:
        return None

    try:

        bucket = (
            math.floor(
                value / step
            )
            * step
        )

        return round(
            bucket,
            2
        )

    except Exception:

        return None


# ============================================================
# 배당 구간 분석
# ============================================================

def odds_range_analysis(
    data=None,
    step=0.10
):

    if data is None:

        data = load_data()

    groups = defaultdict(
        list
    )

    for row in data:

        result = normalize_result(
            row.get(
                "result"
            )
        )

        if result not in RESULTS:
            continue

        for side, key in [
            ("승", "home_odds"),
            ("무", "draw_odds"),
            ("패", "away_odds"),
        ]:

            odds = to_float(
                row.get(
                    key
                )
            )

            bucket = odds_bucket(
                odds,
                step
            )

            if bucket is None:
                continue

            groups[
                (side, bucket)
            ].append(
                result
            )

    output = []

    for (
        side,
        bucket
    ), results in groups.items():

        total = len(
            results
        )

        target = side

        hit = results.count(
            target
        )

        output.append({

            "구분": side,

            "배당구간": (
                f"{bucket:.2f} ~ "
                f"{bucket + step:.2f}"
            ),

            "배당": bucket,

            "전체": total,

            "적중": hit,

            "적중률": percentage(
                hit,
                total
            ),

        })

    output.sort(
        key=lambda x: (
            x["구분"],
            x["배당"]
        )
    )

    return output


# ============================================================
# 예상확률 vs 실제확률
# ============================================================

def probability_comparison(
    data=None
):

    if data is None:

        data = load_data()

    total = 0

    actual = {
        "승": 0,
        "무": 0,
        "패": 0,
    }

    expected_sum = {
        "승": 0.0,
        "무": 0.0,
        "패": 0.0,
    }

    for row in data:

        result = normalize_result(
            row.get(
                "result"
            )
        )

        if result not in RESULTS:
            continue

        probability = (
            odds_to_probability(
                row.get(
                    "home_odds"
                ),
                row.get(
                    "draw_odds"
                ),
                row.get(
                    "away_odds"
                )
            )
        )

        if probability is None:
            continue

        total += 1

        actual[
            result
        ] += 1

        expected_sum[
            "승"
        ] += probability[
            "home"
        ]

        expected_sum[
            "무"
        ] += probability[
            "draw"
        ]

        expected_sum[
            "패"
        ] += probability[
            "away"
        ]

    output = []

    mapping = {
        "승": "승",
        "무": "무",
        "패": "패",
    }

    for result in RESULTS:

        actual_percent = percentage(
            actual[result],
            total
        )

        expected_percent = (
            expected_sum[
                mapping[result]
            ]
            / total
            if total > 0
            else 0
        )

        difference = (
            actual_percent
            - expected_percent
        )

        output.append({

            "결과": result,

            "경기수": actual[result],

            "실제확률": round(
                actual_percent,
                2
            ),

            "예상확률": round(
                expected_percent,
                2
            ),

            "확률차이": round(
                difference,
                2
            ),

            "부족확률": round(
                max(
                    expected_percent
                    - actual_percent,
                    0
                ),
                2
            ),

        })

    return {
        "total": total,
        "data": output,
    }


# ============================================================
# 확률 대비 부족확률
# ============================================================

def calculate_shortfall(
    actual_probability,
    expected_probability
):

    actual = to_float(
        actual_probability
    ) or 0

    expected = to_float(
        expected_probability
    ) or 0

    return round(
        max(
            expected - actual,
            0
        ),
        2
    )


# ============================================================
# 경기별 예상확률
# ============================================================

def match_probability(
    row
):

    probability = (
        odds_to_probability(
            row.get(
                "home_odds"
            ),
            row.get(
                "draw_odds"
            ),
            row.get(
                "away_odds"
            )
        )
    )

    if probability is None:
        return None

    return {

        "승": round(
            probability["home"],
            2
        ),

        "무": round(
            probability["draw"],
            2
        ),

        "패": round(
            probability["away"],
            2
        ),

    }


# ============================================================
# 경기별 분석
# ============================================================

def analyze_match(
    row
):

    result = normalize_result(
        row.get(
            "result"
        )
    )

    probability = match_probability(
        row
    )

    output = dict(
        row
    )

    output[
        "예상확률"
    ] = probability

    if probability:

        output[
            "예상승률"
        ] = probability["승"]

        output[
            "예상무승부율"
        ] = probability["무"]

        output[
            "예상패율"
        ] = probability["패"]

        if result == "승":

            output[
                "실제결과확률"
            ] = probability["승"]

        elif result == "무":

            output[
                "실제결과확률"
            ] = probability["무"]

        elif result == "패":

            output[
                "실제결과확률"
            ] = probability["패"]

    return output


# ============================================================
# 전체 분석
# ============================================================

def get_full_analysis(
    bookmaker=None
):

    data = load_data(
        bookmaker=bookmaker
    )

    return {

        "total": len(data),

        "result": result_statistics(
            data=data
        ),

        "bookmakers": bookmaker_statistics(
            data=data
        ),

        "exact_odds": exact_odds_analysis(
            data=data
        ),

        "draw_odds": exact_draw_odds_analysis(
            data=data
        ),

        "odds_range": odds_range_analysis(
            data=data
        ),

        "probability": probability_comparison(
            data=data
        ),

    }


# ============================================================
# 승 / 무 / 패별 데이터
# ============================================================

def filter_result(
    data,
    result
):

    target = normalize_result(
        result
    )

    return [

        row
        for row in data
        if normalize_result(
            row.get(
                "result"
            )
        ) == target

    ]


# ============================================================
# 승 데이터
# ============================================================

def get_win_data(
    data=None
):

    if data is None:
        data = load_data()

    return filter_result(
        data,
        "승"
    )


# ============================================================
# 무 데이터
# ============================================================

def get_draw_data(
    data=None
):

    if data is None:
        data = load_data()

    return filter_result(
        data,
        "무"
    )


# ============================================================
# 패 데이터
# ============================================================

def get_lose_data(
    data=None
):

    if data is None:
        data = load_data()

    return filter_result(
        data,
        "패"
    )


# ============================================================
# 최근 데이터
# ============================================================

def get_recent_analysis(
    limit=100
):

    data = database.get_analysis_data(
        limit=limit
    )

    return [
        analyze_match(row)
        for row in data
    ]


# ============================================================
# 데이터프레임 호환용
#
# pandas가 설치되어 있으면 DataFrame 반환
# 없으면 list 반환
# ============================================================

def to_dataframe(
    data
):

    try:

        import pandas as pd

        return pd.DataFrame(
            data
        )

    except Exception:

        return data


# ============================================================
# 통계 요약
# ============================================================

def get_summary():

    stats = result_statistics()

    return {

        "전체경기":
            stats["total"],

        "승":
            stats["승"],

        "무":
            stats["무"],

        "패":
            stats["패"],

        "승률":
            round(
                stats["승률"],
                2
            ),

        "무승부율":
            round(
                stats["무승부율"],
                2
            ),

        "패율":
            round(
                stats["패율"],
                2
            ),

    }


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "⚽ 7M 분석 모듈"
    )

    print(
        "=" * 60
    )

    summary = get_summary()

    for key, value in summary.items():

        print(
            f"{key}: {value}"
        )

    print()

    probability = (
        probability_comparison()
    )

    print(
        "확률 분석 경기:",
        probability[
            "total"
        ]
    )

    print()

    print(
        "업체 목록:"
    )

    for bookmaker in get_bookmakers():

        print(
            "-",
            bookmaker
        )
