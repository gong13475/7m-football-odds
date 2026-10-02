import time
import streamlit as st

from datetime import date

from database import (
    init_db,
    get_count
)

from analyzer import (
    analyze_same_odds,
    implied_probability
)

from worker import CollectorWorker

from collector import diagnose


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="7M 축구 최종배당 수집기",
    page_icon="⚽",
    layout="centered"
)

init_db()


# =========================================================
# Session State
# =========================================================

if "worker" not in st.session_state:
    st.session_state.worker = None


# =========================================================
# 제목
# =========================================================

st.title("⚽ 7M 축구 최종배당 수집기")


# =========================================================
# 수집 기간
# =========================================================

st.subheader("수집 기간")

col1, col2 = st.columns(2)

with col1:

    start_date = st.date_input(
        "시작일",
        value=date(2026, 10, 2)
    )

with col2:

    end_date = st.date_input(
        "종료일",
        value=date(2026, 10, 2)
    )


# =========================================================
# CID
# =========================================================

cid = st.text_input(
    "회사 필터 CID",
    value="",
    help="전체 데이터를 사용하려면 비워두세요."
)


# =========================================================
# 업체
# =========================================================

st.subheader("배당업체")

companies = st.multiselect(
    "분석 업체",
    [
        "10Bet",
        "Bet365",
        "Pinnacle",
        "Betfair",
        "bwin",
        "William Hill",
        "Ladbrokes",
        "전체"
    ],
    default=["전체"]
)


# =========================================================
# 설정
# =========================================================

st.subheader("수집 설정")

final_only = st.checkbox(
    "최종배당만 수집",
    value=True,
    disabled=True
)

same_odds_only = st.checkbox(
    "동일배당만 분석",
    value=True,
    disabled=True
)

hide_logs = st.checkbox(
    "로그 숨기기",
    value=False
)


st.divider()


# =========================================================
# Worker 상태
# =========================================================

worker = st.session_state.worker

running = (
    worker is not None
    and worker.running
)


# =========================================================
# 시작 / 중지
# =========================================================

col1, col2 = st.columns(2)

with col1:

    start = st.button(
        "▶ 수집 시작",
        use_container_width=True,
        disabled=running
    )

with col2:

    stop = st.button(
        "⏹ 수집 중지",
        use_container_width=True,
        disabled=not running
    )


# =========================================================
# 수집 시작
# =========================================================

if start:

    if start_date > end_date:

        st.error(
            "시작일이 종료일보다 늦습니다."
        )

    else:

        new_worker = CollectorWorker(
            start_date=start_date,
            end_date=end_date,
            cid=cid
        )

        st.session_state.worker = new_worker

        new_worker.start()

        st.rerun()


# =========================================================
# 수집 중지
# =========================================================

if stop:

    if worker is not None:

        worker.stop()

        st.rerun()


# =========================================================
# 현재 Worker 다시 읽기
# =========================================================

worker = st.session_state.worker


# =========================================================
# 상태 표시
# =========================================================

st.divider()

if worker is None:

    st.subheader("⚪ 대기 중")

    progress_value = 0

    found = 0
    saved = 0
    failed = 0

    message = "수집 대기 중..."

else:

    if worker.running:

        st.subheader("🟢 수집 중")

    else:

        st.subheader(
            "⚪ " + worker.message
        )

    progress_value = worker.progress()

    found = worker.found_rows
    saved = worker.saved_rows
    failed = worker.failed_days

    message = worker.message


st.progress(
    progress_value
)


# =========================================================
# 통계
# =========================================================

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "발견",
        found
    )

with col2:

    st.metric(
        "신규 저장",
        saved
    )

with col3:

    st.metric(
        "실패일",
        failed
    )


# =========================================================
# DB 전체
# =========================================================

st.divider()

st.metric(
    "DB 전체 경기",
    get_count()
)


# =========================================================
# 로그
# =========================================================

if not hide_logs:

    st.subheader("로그")

    st.code(
        message
    )


# =========================================================
# 연결 진단
# =========================================================

st.divider()

st.subheader("🔎 7M 페이지 연결 진단")

st.caption(
    "수집 결과가 0건일 경우 먼저 실제 서버 응답을 확인합니다."
)


diagnostic_date = st.date_input(
    "진단 날짜",
    value=date(2026, 10, 2),
    key="diagnostic_date"
)


if st.button(
    "🔍 7M 페이지 진단",
    use_container_width=True
):

    with st.spinner(
        "7M 페이지 확인 중..."
    ):

        try:

            result = diagnose(
                diagnostic_date,
                cid
            )

            st.success(
                "페이지 요청 완료"
            )

            col1, col2 = st.columns(2)

            with col1:

                st.metric(
                    "HTTP 상태",
                    result.get(
                        "status",
                        "-"
                    )
                )

            with col2:

                st.metric(
                    "받은 데이터",
                    result.get(
                        "size",
                        0
                    )
                )

            st.write(
                "결과 페이지 문자열:",
                result.get(
                    "has_result",
                    False
                )
            )

            st.write(
                "비교 문자열:",
                result.get(
                    "has_compare",
                    False
                )
            )

            html = result.get(
                "html",
                ""
            )

            if html:

                with st.expander(
                    "서버에서 받은 HTML 보기"
                ):

                    st.code(
                        html,
                        language="html"
                    )

        except Exception as error:

            st.error(
                f"진단 오류: {error}"
            )


# =========================================================
# 동일 배당 분석
# =========================================================

st.divider()

st.subheader(
    "동일 최종배당 분석"
)


col1, col2, col3 = st.columns(3)


with col1:

    home_odds = st.number_input(
        "홈승",
        min_value=1.01,
        value=2.15,
        step=0.01
    )


with col2:

    draw_odds = st.number_input(
        "무승부",
        min_value=1.01,
        value=3.90,
        step=0.01
    )


with col3:

    away_odds = st.number_input(
        "원정승",
        min_value=1.01,
        value=2.90,
        step=0.01
    )


if st.button(
    "📊 동일배당 분석",
    use_container_width=True
):

    try:

        stats = analyze_same_odds(
            home_odds,
            draw_odds,
            away_odds
        )

        if stats["total"] == 0:

            st.warning(
                "해당 최종배당의 저장된 과거 경기가 없습니다."
            )

        else:

            st.success(
                f"총 {stats['total']}경기"
            )

            col1, col2, col3 = st.columns(3)

            with col1:

                st.metric(
                    "홈승",
                    f"{stats['home']}%"
                )

            with col2:

                st.metric(
                    "무승부",
                    f"{stats['draw']}%"
                )

            with col3:

                st.metric(
                    "원정승",
                    f"{stats['away']}%"
                )

    except Exception as error:

        st.error(
            f"분석 오류: {error}"
        )


# =========================================================
# 배당상 확률
# =========================================================

st.subheader(
    "배당상 확률"
)


col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "홈승",
        f"{implied_probability(home_odds)}%"
    )


with col2:

    st.metric(
        "무승부",
        f"{implied_probability(draw_odds)}%"
    )


with col3:

    st.metric(
        "원정승",
        f"{implied_probability(away_odds)}%"
    )


# =========================================================
# 자동 새로고침
# =========================================================

if worker is not None and worker.running:

    time.sleep(1)

    st.rerun()
