# ============================================================
# analysis.py
# 7M 동일 최종배당 분석
# ============================================================

import database


# ============================================================
# 숫자 처리
# ============================================================

def to_float(value):

    try:
        if value is None:
            return None

        return float(value)

    except Exception:
        return None


# ============================================================
# 배당 → 기본 예상확률
# ============================================================

def implied_probability(odds):

    odds = to_float(odds)

    if odds is None or odds <= 0:
        return 0.0

    return 100.0 / odds


# ============================================================
# 3개 배당 정규화
# ============================================================

def normalize_odds(
    home_odds,
    draw_odds,
    away_odds
):

    h = to_float(home_odds)
    d = to_float(draw_odds)
    a = to_float(away_odds)

    return h, d, a


# ============================================================
# 오버라운드 포함 예상확률
# ============================================================

def market_probability(
    home_odds,
    draw_odds,
    away_odds
):

    h, d, a = normalize_odds(
        home_odds,
        draw_odds,
        away_odds
    )

    if not h or not d or not a:
        return {
            "home": 0.0,
            "draw": 0.0,
            "away": 0.0,
            "margin": 0.0
        }

    ih = 1.0 / h
    idraw = 1.0 / d
    ia = 1.0 / a

    total = ih + idraw + ia

    if total <= 0:
        return {
            "home": 0.0,
            "draw": 0.0,
            "away": 0.0,
            "margin": 0.0
        }

    return {
        "home": round(
            ih / total * 100,
            2
        ),

        "draw": round(
            idraw / total * 100,
            2
        ),

        "away": round(
            ia / total * 100,
            2
        ),

        "margin": round(
            (total - 1.0) * 100,
            2
        )
    }


# ============================================================
# 동일배당 과거경기 분석
# ============================================================

def analyze_same_odds(
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.01
):

    h, d, a = normalize_odds(
        home_odds,
        draw_odds,
        away_odds
    )

    if not h or not d or not a:
        return {
            "total": 0,
            "승": 0,
            "무": 0,
            "패": 0,
            "승률": 0.0,
            "무율": 0.0,
            "패율": 0.0,
            "rows": []
        }

    data = database.get_result_statistics(
        h,
        d,
        a,
        tolerance
    )

    market = market_probability(
        h,
        d,
        a
    )

    total = data["total"]

    win = data["승"]
    draw = data["무"]
    lose = data["패"]

    win_pct = data["승률"]
    draw_pct = data["무율"]
    lose_pct = data["패율"]

    # --------------------------------------------------------
    # 배당 예상확률
    # --------------------------------------------------------

    expected_win = market["home"]
    expected_draw = market["draw"]
    expected_lose = market["away"]

    # --------------------------------------------------------
    # 실제확률 - 예상확률
    # --------------------------------------------------------

    shortage_win = round(
        win_pct - expected_win,
        2
    )

    shortage_draw = round(
        draw_pct - expected_draw,
        2
    )

    shortage_lose = round(
        lose_pct - expected_lose,
        2
    )

    return {

        # 기본
        "home_odds": h,
        "draw_odds": d,
        "away_odds": a,

        # 표본
        "total": total,

        # 실제 건수
        "승": win,
        "무": draw,
        "패": lose,

        # 실제 확률
        "승률": win_pct,
        "무율": draw_pct,
        "패율": lose_pct,

        # 예상확률
        "예상승률": expected_win,
        "예상무율": expected_draw,
        "예상패율": expected_lose,

        # 차이
        "승차이": shortage_win,
        "무차이": shortage_draw,
        "패차이": shortage_lose,

        # 시장 마진
        "마진": market["margin"],

        # 과거 경기
        "rows": data["rows"]
    }


# ============================================================
# 배당별 추천 결과
# ============================================================

def get_best_result(
    analysis
):

    if not analysis:
        return None

    total = analysis.get(
        "total",
        0
    )

    if total <= 0:
        return None

    values = {

        "승": analysis.get(
            "승률",
            0
        ),

        "무": analysis.get(
            "무율",
            0
        ),

        "패": analysis.get(
            "패율",
            0
        )
    }

    return max(
        values,
        key=values.get
    )


# ============================================================
# 예상확률 대비 가장 부족한 결과
# ============================================================

def get_shortage_result(
    analysis
):

    if not analysis:
        return None

    values = {

        "승": analysis.get(
            "승차이",
            0
        ),

        "무": analysis.get(
            "무차이",
            0
        ),

        "패": analysis.get(
            "패차이",
            0
        )
    }

    return max(
        values,
        key=values.get
    )


# ============================================================
# 배당 분석 전체 결과
# ============================================================

def full_analysis(
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.01
):

    result = analyze_same_odds(
        home_odds,
        draw_odds,
        away_odds,
        tolerance
    )

    if result["total"] == 0:

        result["추천"] = None
        result["부족결과"] = None

        return result

    result["추천"] = get_best_result(
        result
    )

    result["부족결과"] = get_shortage_result(
        result
    )

    return result


# ============================================================
# 전체 DB 승무패 통계
# ============================================================

def overall_analysis():

    return database.get_overall_statistics()


# ============================================================
# 날짜별 분석
# ============================================================

def date_analysis(
    start_date=None,
    end_date=None
):

    return database.get_date_statistics(
        start_date=start_date,
        end_date=end_date
    )


# ============================================================
# 동일배당 경기 목록
# ============================================================

def same_odds_matches(
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.01
):

    h, d, a = normalize_odds(
        home_odds,
        draw_odds,
        away_odds
    )

    if not h or not d or not a:
        return []

    return database.get_same_odds(
        h,
        d,
        a,
        tolerance
    )


# ============================================================
# 결과 건수 문자열
# ============================================================

def result_count_text(
    analysis
):

    if not analysis:
        return "데이터 없음"

    return (
        f"승 {analysis.get('승', 0)}경기 "
        f"({analysis.get('승률', 0):.2f}%) / "
        f"무 {analysis.get('무', 0)}경기 "
        f"({analysis.get('무율', 0):.2f}%) / "
        f"패 {analysis.get('패', 0)}경기 "
        f"({analysis.get('패율', 0):.2f}%)"
    )


# ============================================================
# 배당 표시
# ============================================================

def odds_text(
    home_odds,
    draw_odds,
    away_odds
):

    h, d, a = normalize_odds(
        home_odds,
        draw_odds,
        away_odds
    )

    if not h or not d or not a:
        return "-"

    return (
        f"{h:.2f} / "
        f"{d:.2f} / "
        f"{a:.2f}"
    )


# ============================================================
# 예상확률 표시
# ============================================================

def expected_probability_text(
    analysis
):

    if not analysis:
        return "-"

    return (
        f"승 {analysis.get('예상승률', 0):.2f}% / "
        f"무 {analysis.get('예상무율', 0):.2f}% / "
        f"패 {analysis.get('예상패율', 0):.2f}%"
    )


# ============================================================
# 실제확률 표시
# ============================================================

def actual_probability_text(
    analysis
):

    if not analysis:
        return "-"

    return (
        f"승 {analysis.get('승률', 0):.2f}% / "
        f"무 {analysis.get('무율', 0):.2f}% / "
        f"패 {analysis.get('패율', 0):.2f}%"
    )


# ============================================================
# 확률 차이 표시
# ============================================================

def shortage_probability_text(
    analysis
):

    if not analysis:
        return "-"

    return (
        f"승 {analysis.get('승차이', 0):+.2f}%p / "
        f"무 {analysis.get('무차이', 0):+.2f}%p / "
        f"패 {analysis.get('패차이', 0):+.2f}%p"
    )


# ============================================================
# 데이터가 충분한지 판단
# ============================================================

def is_reliable(
    analysis,
    minimum_games=20
):

    if not analysis:
        return False

    return (
        analysis.get(
            "total",
            0
        ) >= minimum_games
    )


# ============================================================
# 신뢰도
# ============================================================

def reliability_text(
    analysis
):

    if not analysis:
        return "데이터 없음"

    total = analysis.get(
        "total",
        0
    )

    if total >= 100:
        return "매우 높음"

    if total >= 50:
        return "높음"

    if total >= 20:
        return "보통"

    if total >= 10:
        return "낮음"

    return "매우 낮음"


# ============================================================
# 배당 분석 요약
# ============================================================

def summary(
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.01
):

    analysis = full_analysis(
        home_odds,
        draw_odds,
        away_odds,
        tolerance
    )

    if analysis["total"] == 0:

        return {
            "배당": odds_text(
                home_odds,
                draw_odds,
                away_odds
            ),

            "표본": 0,

            "실제결과": "-",

            "예상확률": expected_probability_text(
                analysis
            ),

            "실제확률": actual_probability_text(
                analysis
            ),

            "확률차이": shortage_probability_text(
                analysis
            ),

            "추천": None,

            "신뢰도": "데이터 없음"
        }

    return {

        "배당": odds_text(
            home_odds,
            draw_odds,
            away_odds
        ),

        "표본": analysis["total"],

        "실제결과": result_count_text(
            analysis
        ),

        "예상확률": expected_probability_text(
            analysis
        ),

        "실제확률": actual_probability_text(
            analysis
        ),

        "확률차이": shortage_probability_text(
            analysis
        ),

        "추천": analysis.get(
            "추천"
        ),

        "부족결과": analysis.get(
            "부족결과"
        ),

        "신뢰도": reliability_text(
            analysis
        )
  }
