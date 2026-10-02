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


st.set_page_config(
    page_title="7M 축구 최종배당 수집기",
    page_icon="⚽",
    layout="centered"
)


init_db()


if "worker" not in st.session_state:
    st.session_state.worker = None


st.title(
    "⚽ 7M 축구 최종배당 수집기"
)


# -------------------------
# 기간
# -------------------------

st.subheader("수집 기간")

c1, c2 = st.columns(2)

with c1:

    start_date = st.date_input(
        "시작일",
        value=date(
            2010,
            1,
            1
        )
    )

with c2:

    end_date = st.date_input(
        "종료일",
        value=date.today()
    )


# -------------------------
# cid
# -------------------------

cid = st.text_input(
    "회사 필터 CID",
    value="",
    help="전체 회사를 사용하려면 비워두세요."
)


# -------------------------
# 업체 표시
# -------------------------

st.subheader("분석 대상 업체")

companies = st.multiselect(
    "업체",
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


# -------------------------
# 설정
# -------------------------

st.subheader("수집 설정")

st.checkbox(
    "최종배당만 수집",
    value=True,
    disabled=True
)

st.checkbox(
    "동일배당만 분석",
    value=True,
    disabled=True
)

hide_logs = st.checkbox(
    "로그 숨기기",
    value=True
)


st.divider()


# -------------------------
# Worker
# -------------------------

worker = (
    st.session_state.worker
)

running = (
    worker is not None
    and worker.running
)


c1, c2 = st.columns(2)

with c1:

    start = st.button(
        "▶ 수집 시작",
        use_container_width=True,
        disabled=running
    )

with c2:

    stop = st.button(
        "⏹ 수집 중지",
        use_container_width=True,
        disabled=not running
    )


if start:

    if start_date > end_date:

        st.error(
            "시작일이 종료일보다 늦습니다."
        )

    else:

        worker = CollectorWorker(
            start_date,
            end_date,
            cid
        )

        st.session_state.worker = worker

        worker.start()

        st.rerun()


if stop:

    if worker:

        worker.stop()

        st.rerun()


# -------------------------
# 상태
# -------------------------

worker = (
    st.session_state.worker
)


if worker:

    if worker.running:

        st.subheader(
            "🟢 수집 중"
        )

    else:

        st.subheader(
            "⚪ " + worker.message
        )

    st.progress(
        worker.progress()
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "발견",
        worker.found_rows
    )

    c2.metric(
        "신규 저장",
        worker.saved_rows
    )

    c3.metric(
        "실패일",
        worker.failed_days
    )

else:

    st.subheader(
        "⚪ 대기 중"
    )

    st.progress(0)

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "발견",
        0
    )

    c2.metric(
        "신규 저장",
        0
    )

    c3.metric(
        "실패일",
        0
    )


st.divider()


# -------------------------
# DB
# -------------------------

st.metric(
    "DB 전체 경기",
    get_count()
)


st.divider()


# -------------------------
# 동일배당
# -------------------------

st.subheader(
    "동일 최종배당 분석"
)

c1, c2, c3 = st.columns(3)

with c1:

    home_odds = st.number_input(
        "홈승",
        min_value=1.01,
        value=2.15,
        step=0.01
    )

with c2:

    draw_odds = st.number_input(
        "무승부",
        min_value=1.01,
        value=3.90,
        step=0.01
    )

with c3:

    away_odds = st.number_input(
        "원정승",
        min_value=1.01,
        value=2.90,
        step=0.01
    )


if st.button(
    "동일배당 분석",
    use_container_width=True
):

    stats = analyze_same_odds(
        home_odds,
        draw_odds,
        away_odds
    )

    if stats["total"] == 0:

        st.warning(
            "해당 배당의 과거 데이터가 없습니다."
        )

    else:

        st.success(
            f"총 {stats['total']}경기"
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "홈승",
            f"{stats['home']}%"
        )

        c2.metric(
            "무",
            f"{stats['draw']}%"
        )

        c3.metric(
            "원정승",
            f"{stats['away']}%"
        )


# -------------------------
# 배당상 확률
# -------------------------

st.subheader(
    "배당상 확률"
)

c1, c2, c3 = st.columns(3)

c1.metric(
    "홈승",
    f"{implied_probability(home_odds)}%"
)

c2.metric(
    "무",
    f"{implied_probability(draw_odds)}%"
)

c3.metric(
    "원정승",
    f"{implied_probability(away_odds)}%"
)


# -------------------------
# 로그
# -------------------------

if not hide_logs:

    st.divider()

    st.subheader("로그")

    if worker:

        st.code(
            worker.message
        )

    else:

        st.code(
            "수집 대기 중..."
        )


# -------------------------
# 수집 중 자동 갱신
# -------------------------

if worker and worker.running:

    time.sleep(1)

    st.rerun()
