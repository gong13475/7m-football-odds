import streamlit as st
from datetime import date

st.set_page_config(
    page_title="7M 축구 배당 수집기",
    page_icon="⚽",
    layout="centered"
)

st.title("⚽ 7M 축구 최종배당 수집기")

st.subheader("수집 기간")

col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input(
        "시작일",
        value=date(2010, 1, 1)
    )

with col2:
    end_date = st.date_input(
        "종료일",
        value=date.today()
    )

st.subheader("배당업체")

companies = st.multiselect(
    "수집할 업체",
    [
        "10Bet",
        "Bet365",
        "Pinnacle",
        "기타 제공업체"
    ],
    default=["10Bet"]
)

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
    value=True
)

st.divider()

col1, col2 = st.columns(2)

with col1:
    start = st.button(
        "▶ 수집 시작",
        use_container_width=True
    )

with col2:
    stop = st.button(
        "⏹ 수집 중지",
        use_container_width=True
    )

if start:
    st.session_state["running"] = True

if stop:
    st.session_state["running"] = False

if "running" not in st.session_state:
    st.session_state["running"] = False

st.divider()

status = "🟢 수집 중" if st.session_state["running"] else "⚪ 대기 중"

st.subheader(status)

progress = st.progress(0)

c1, c2, c3 = st.columns(3)

c1.metric("수집", "0")
c2.metric("성공", "0")
c3.metric("실패", "0")

st.divider()

st.subheader("동일 최종배당 분석")

st.info(
    "실제 데이터가 연결되면 정확히 동일한 "
    "최종 승/무/패 배당만 집계합니다."
)

a1, a2, a3 = st.columns(3)

a1.metric("승", "0%")
a2.metric("무", "0%")
a3.metric("패", "0%")

st.subheader("배당상 확률")

p1, p2, p3 = st.columns(3)

p1.metric("승", "0%")
p2.metric("무", "0%")
p3.metric("패", "0%")

if not hide_logs:
    st.divider()
    st.subheader("로그")
    st.code("수집 대기 중...")
