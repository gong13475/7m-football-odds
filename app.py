# ============================================================
# app.py
# ⚽ 7M 축구 최종배당 수집 · 분석기
#
# 기능
# ------------------------------------------------------------
# 1. 7M 경기 ID 범위 수집
# 2. 수집 시작 / 중지
# 3. 백그라운드 수집
# 4. 진행률 표시
# 5. 성공 / 실패 / 배당 개수 표시
# 6. 로그 보기 버튼
# 7. DB 경기 수
# 8. DB 배당 수
# 9. 업체 수
# 10. 승 / 무 / 패 통계
# 11. 업체별 통계
# 12. 동일배당 분석
# 13. 동일 무배당 분석
# 14. 예상확률 대비 실제확률
# 15. 부족확률
# 16. 경기 데이터 조회
# ============================================================

import time
import streamlit as st

import database
import analysis
import sevenm_crawler


# ============================================================
# 페이지 설정
# ============================================================

st.set_page_config(
    page_title="⚽ 7M 최종배당 분석",
    page_icon="⚽",
    layout="wide",
)


# ============================================================
# DB 초기화
# ============================================================

try:

    database.init_database()

except Exception as e:

    st.error(
        "DATABASE 초기화 오류"
    )

    st.code(
        str(e)
    )

    st.stop()


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 30px;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .sub-title {
        color: #777;
        margin-bottom: 20px;
    }

    .status-box {
        padding: 12px;
        border-radius: 10px;
        background: #f5f7fa;
        border: 1px solid #ddd;
        margin-bottom: 10px;
    }

    .small-text {
        font-size: 13px;
        color: #777;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 제목
# ============================================================

st.markdown(
    '<div class="main-title">'
    '⚽ 7M 축구 최종배당 수집 · 분석기'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="sub-title">'
    '7M 데이터 전용 · 1X2 최종배당 · 동일배당 과거결과 분석'
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# DB 상태
# ============================================================

db_status = (
    database.get_database_status()
)


# ============================================================
# 상단 DB 현황
# ============================================================

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "DB 전체 경기",
        f"{db_status['matches']:,}"
    )

with col2:

    st.metric(
        "저장 최종배당",
        f"{db_status['odds']:,}"
    )

with col3:

    st.metric(
        "업체",
        f"{db_status['bookmakers']:,}"
    )

with col4:

    st.metric(
        "현재 상태",
        sevenm_crawler.get_status_text()
    )


st.divider()


# ============================================================
# 경기 자동수집
# ============================================================

st.header(
    "📥 경기 자동수집"
)


# ------------------------------------------------------------
# ID 입력
# ------------------------------------------------------------

col1, col2 = st.columns(2)

with col1:

    start_id = st.number_input(
        "시작 경기 ID",
        min_value=1,
        value=2000000,
        step=1,
        format="%d",
        key="sevenm_start_id",
    )


with col2:

    end_id = st.number_input(
        "종료 경기 ID",
        min_value=1,
        value=2000100,
        step=1,
        format="%d",
        key="sevenm_end_id",
    )


# ============================================================
# 옵션
# ============================================================

col1, col2, col3 = st.columns(3)


with col1:

    delay = st.number_input(
        "경기당 요청 간격(초)",
        min_value=0.1,
        max_value=10.0,
        value=0.5,
        step=0.1,
        key="sevenm_delay",
    )


with col2:

    total_requested = (
        abs(
            int(end_id)
            - int(start_id)
        )
        + 1
    )

    st.metric(
        "수집 대상 경기",
        f"{total_requested:,}"
    )


with col3:

    st.write("")

    st.write("")

    st.caption(
        "※ 시작 버튼을 눌러야 수집됩니다."
    )


# ============================================================
# 시작 / 중지
# ============================================================

col1, col2 = st.columns(2)


with col1:

    start_button = st.button(
        "🚀 수집 시작",
        type="primary",
        use_container_width=True,
        disabled=sevenm_crawler.is_running(),
    )


with col2:

    stop_button = st.button(
        "⛔ 수집 중지",
        use_container_width=True,
        disabled=not sevenm_crawler.is_running(),
    )


# ============================================================
# 수집 시작
# ============================================================

if start_button:

    if int(start_id) <= 0:
        st.error(
            "시작 ID를 확인하세요."
        )

    elif int(end_id) <= 0:
        st.error(
            "종료 ID를 확인하세요."
        )

    else:

        if int(end_id) < int(start_id):

            real_start = int(end_id)
            real_end = int(start_id)

        else:

            real_start = int(start_id)
            real_end = int(end_id)

        started = (
            sevenm_crawler
            .start_background_collection(
                start_id=real_start,
                end_id=real_end,
                selected_companies=["7M"],
                delay=float(delay),
            )
        )

        if started:

            st.success(
                f"수집 시작: "
                f"{real_start:,} ~ "
                f"{real_end:,}"
            )

            time.sleep(0.5)

            st.rerun()

        else:

            st.warning(
                "이미 수집 작업이 실행 중입니다."
            )


# ============================================================
# 수집 중지
# ============================================================

if stop_button:

    sevenm_crawler.stop_collection()

    st.warning(
        "수집 중지 요청을 보냈습니다."
    )

    time.sleep(0.5)

    st.rerun()


# ============================================================
# 현재 작업 상태
# ============================================================

status = (
    sevenm_crawler.get_status()
)

progress = (
    sevenm_crawler.get_progress()
)


# ============================================================
# 진행률
# ============================================================

if status["running"]:

    st.subheader(
        "🔄 수집 진행상태"
    )

    st.progress(
        min(
            progress["percent"]
            / 100,
            1.0
        )
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "진행",
            f"{progress['current']:,} / "
            f"{progress['total']:,}"
        )

    with c2:

        st.metric(
            "성공",
            f"{progress['success']:,}"
        )

    with c3:

        st.metric(
            "실패",
            f"{progress['failed']:,}"
        )

    with c4:

        st.metric(
            "최종배당",
            f"{progress['odds']:,}"
        )

    st.info(
        f"현재 ID: "
        f"{progress['last_completed_id']:,}"
    )


elif status["finished"]:

    st.subheader(
        "🏁 최근 수집 결과"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "상태",
            status["result"]
        )

    with c2:

        st.metric(
            "성공",
            f"{status['success']:,}"
        )

    with c3:

        st.metric(
            "실패",
            f"{status['failed']:,}"
        )

    with c4:

        st.metric(
            "최종배당",
            f"{status['odds']:,}"
        )


# ============================================================
# 로그 보기
# ============================================================

st.divider()

st.subheader(
    "📋 수집 로그"
)


show_logs = st.button(
    "📖 로그 보기 / 새로고침",
    use_container_width=True,
)


if show_logs:

    logs = (
        sevenm_crawler.get_logs()
    )

    if logs:

        st.code(
            "\n".join(logs),
            language="text",
        )

    else:

        st.info(
            "표시할 로그가 없습니다."
        )


# ============================================================
# 자동 진행 갱신
# ============================================================

if status["running"]:

    time.sleep(1)

    st.rerun()


# ============================================================
# 분석
# ============================================================

st.divider()

st.header(
    "📊 DB 분석"
)


# ============================================================
# 최신 DB 상태
# ============================================================

db_status = (
    database.get_database_status()
)

c1, c2, c3 = st.columns(3)

with c1:

    st.metric(
        "전체 경기",
        f"{db_status['matches']:,}"
    )

with c2:

    st.metric(
        "최종배당",
        f"{db_status['odds']:,}"
    )

with c3:

    st.metric(
        "배당업체",
        f"{db_status['bookmakers']:,}"
    )


# ============================================================
# 승무패 통계
# ============================================================

st.subheader(
    "⚽ 전체 승무패 통계"
)

summary = (
    analysis.get_summary()
)


c1, c2, c3, c4 = st.columns(4)

with c1:

    st.metric(
        "전체 경기",
        f"{summary['전체경기']:,}"
    )

with c2:

    st.metric(
        "승",
        f"{summary['승']:,}",
        f"{summary['승률']:.2f}%"
    )

with c3:

    st.metric(
        "무",
        f"{summary['무']:,}",
        f"{summary['무승부율']:.2f}%"
    )

with c4:

    st.metric(
        "패",
        f"{summary['패']:,}",
        f"{summary['패율']:.2f}%"
    )


# ============================================================
# 업체 선택
# ============================================================

st.subheader(
    "🏢 업체별 분석"
)

bookmakers = (
    analysis.get_bookmakers()
)

bookmaker_options = [
    "전체"
] + bookmakers


selected_bookmaker = st.selectbox(
    "배당업체",
    bookmaker_options,
    key="analysis_bookmaker",
)


if selected_bookmaker == "전체":

    bookmaker_filter = None

else:

    bookmaker_filter = (
        selected_bookmaker
    )


# ============================================================
# 업체별 통계
# ============================================================

bookmaker_stats = (
    analysis.bookmaker_statistics()
)


if bookmaker_stats:

    try:

        st.dataframe(
            bookmaker_stats,
            use_container_width=True,
            hide_index=True,
        )

    except Exception:

        st.write(
            bookmaker_stats
        )

else:

    st.info(
        "업체별 분석 데이터가 없습니다."
    )


# ============================================================
# 확률 대비 분석
# ============================================================

st.subheader(
    "📈 예상확률 대비 실제결과"
)


probability_data = (
    analysis.load_data(
        bookmaker=bookmaker_filter
    )
)


probability_result = (
    analysis.probability_comparison(
        data=probability_data
    )
)


probability_total = (
    probability_result["total"]
)


st.caption(
    f"확률 계산 가능한 경기 "
    f"{probability_total:,}경기"
)


if probability_result["data"]:

    try:

        st.dataframe(
            probability_result["data"],
            use_container_width=True,
            hide_index=True,
        )

    except Exception:

        st.write(
            probability_result["data"]
        )


# ============================================================
# 동일배당 분석
# ============================================================

st.subheader(
    "🎯 동일배당 과거결과"
)


exact_data = (
    analysis.exact_odds_analysis(
        data=probability_data
    )
)


if exact_data:

    try:

        st.dataframe(
            exact_data,
            use_container_width=True,
            hide_index=True,
        )

    except Exception:

        st.write(
            exact_data
        )

else:

    st.info(
        "동일한 배당 조합의 데이터가 없습니다."
    )


# ============================================================
# 동일 무배당
# ============================================================

st.subheader(
    "🎯 동일 무배당 분석"
)


draw_data = (
    analysis.exact_draw_odds_analysis(
        data=probability_data
    )
)


if draw_data:

    try:

        st.dataframe(
            draw_data,
            use_container_width=True,
            hide_index=True,
        )

    except Exception:

        st.write(
            draw_data
        )

else:

    st.info(
        "무배당 분석 데이터가 없습니다."
    )


# ============================================================
# 배당 구간 분석
# ============================================================

st.subheader(
    "📊 배당 구간별 적중률"
)


bucket_data = (
    analysis.odds_range_analysis(
        data=probability_data,
        step=0.10,
    )
)


if bucket_data:

    try:

        st.dataframe(
            bucket_data,
            use_container_width=True,
            hide_index=True,
        )

    except Exception:

        st.write(
            bucket_data
        )

else:

    st.info(
        "배당 구간 분석 데이터가 없습니다."
    )


# ============================================================
# 최근 경기
# ============================================================

st.subheader(
    "📝 최근 경기 데이터"
)


recent_data = (
    analysis.get_recent_analysis(
        limit=100
    )
)


if recent_data:

    display_data = []

    for row in recent_data:

        probability = (
            row.get(
                "예상확률"
            )
        )

        display_data.append({

            "경기ID":
                row.get(
                    "schedule_id"
                ),

            "날짜":
                row.get(
                    "match_date"
                ),

            "홈팀":
                row.get(
                    "home_team"
                ),

            "원정팀":
                row.get(
                    "away_team"
                ),

            "홈점수":
                row.get(
                    "home_score"
                ),

            "원정점수":
                row.get(
                    "away_score"
                ),

            "결과":
                row.get(
                    "result"
                ),

            "업체":
                row.get(
                    "bookmaker"
                ),

            "홈배당":
                row.get(
                    "home_odds"
                ),

            "무배당":
                row.get(
                    "draw_odds"
                ),

            "원정배당":
                row.get(
                    "away_odds"
                ),

            "예상승률":
                (
                    probability["승"]
                    if probability
                    else None
                ),

            "예상무승부율":
                (
                    probability["무"]
                    if probability
                    else None
                ),

            "예상패율":
                (
                    probability["패"]
                    if probability
                    else None
                ),

        })

    try:

        st.dataframe(
            display_data,
            use_container_width=True,
            hide_index=True,
        )

    except Exception:

        st.write(
            display_data
        )

else:

    st.info(
        "저장된 경기 데이터가 없습니다."
    )


# ============================================================
# 푸터
# ============================================================

st.divider()

st.caption(
    "⚽ 7M 축구 최종배당 수집 · 분석기 | "
    "SQLite DB"
    )
