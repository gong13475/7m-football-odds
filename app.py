import io
import threading
from datetime import date

import pandas as pd
import streamlit as st

from database import (
    init_db,
    get_count,
    get_result_counts,
    get_company_counts,
    get_all_matches,
    save_manual_match,
)

from analyzer import (
    implied_probabilities,
    same_odds_analysis,
    overall_analysis,
)

from collector import diagnose

from worker import CollectorWorker


# --------------------------------------------------
# 초기화
# --------------------------------------------------

init_db()

st.set_page_config(
    page_title="7M 축구 최종배당 수집기",
    page_icon="⚽",
    layout="centered"
)


# --------------------------------------------------
# 세션
# --------------------------------------------------

if "worker" not in st.session_state:
    st.session_state.worker = None

if "logs" not in st.session_state:
    st.session_state.logs = []

if "diagnose" not in st.session_state:
    st.session_state.diagnose = None


# --------------------------------------------------
# 제목
# --------------------------------------------------

st.title(
    "⚽ 7M 축구 최종배당 수집기"
)

st.caption(
    "최종배당 수집 · 동일배당 분석 · "
    "확률 분석 · 수동입력 · CSV 저장"
)


# --------------------------------------------------
# 수집기간
# --------------------------------------------------

st.subheader("수집 기간")

col1, col2 = st.columns(2)

with col1:

    start_date = st.date_input(
        "시작일",
        value=date.today()
    )

with col2:

    end_date = st.date_input(
        "종료일",
        value=date.today()
    )


# --------------------------------------------------
# 업체
# --------------------------------------------------

st.subheader("배당업체")

company_map = {
    "전체": "",
    "10Bet": "10bet",
    "Bet365": "bet365",
    "Pinnacle": "pinnacle",
    "기타/CID 직접입력": "custom"
}

company_name = st.selectbox(
    "분석/수집 업체",
    list(company_map.keys())
)

if company_name == "기타/CID 직접입력":

    cid = st.text_input(
        "회사 CID",
        value=""
    )

else:

    cid = company_map[
        company_name
    ]

st.caption(
    "7M의 CID를 알고 있는 경우 직접 입력할 수 있습니다."
)


# --------------------------------------------------
# 설정
# --------------------------------------------------

st.subheader("수집 설정")

final_only = st.checkbox(
    "최종배당만 수집",
    value=True,
    disabled=True
)

same_odds_only = st.checkbox(
    "동일배당만 분석",
    value=True
)

hide_logs = st.checkbox(
    "로그 숨기기",
    value=True
)


# --------------------------------------------------
# 버튼
# --------------------------------------------------

st.divider()

c1, c2, c3 = st.columns(3)

with c1:

    start = st.button(
        "▶ 수집 시작",
        use_container_width=True
    )

with c2:

    stop = st.button(
        "⏹ 수집 중단",
        use_container_width=True
    )

with c3:

    refresh = st.button(
        "🔄 새로고침",
        use_container_width=True
    )


# --------------------------------------------------
# 시작
# --------------------------------------------------

if start:

    if end_date < start_date:

        st.error(
            "종료일이 시작일보다 빠릅니다."
        )

    else:

        worker = CollectorWorker(
            start_date,
            end_date,
            cid
        )

        st.session_state.worker = worker

        worker.start()

        st.success(
            "수집을 시작했습니다."
        )


# --------------------------------------------------
# 중단
# --------------------------------------------------

if stop:

    worker = (
        st.session_state.worker
    )

    if worker:

        worker.stop()

        st.warning(
            "수집 중단을 요청했습니다."
        )


# --------------------------------------------------
# 현재 작업
# --------------------------------------------------

worker = st.session_state.worker


if worker:

    if worker.running:

        st.subheader("🟢 수집 중")

    else:

        st.subheader(
            f"⚪ {worker.message}"
        )

    progress = st.progress(
        worker.progress()
    )

    m1, m2, m3 = st.columns(3)

    m1.metric(
        "발견",
        worker.found_rows
    )

    m2.metric(
        "신규 저장",
        worker.saved_rows
    )

    m3.metric(
        "실패일",
        worker.failed_days
    )

    if worker.last_date:

        st.info(
            f"마지막 정상 데이터 날짜: "
            f"{worker.last_date}"
        )


# --------------------------------------------------
# DB 현황
# --------------------------------------------------

st.divider()

st.subheader("📊 저장 데이터")

db_count = get_count()

st.metric(
    "DB 전체 경기",
    db_count
)


# --------------------------------------------------
# 전체 승무패
# --------------------------------------------------

st.subheader(
    "🏆 결과 승 / 무 / 패"
)

overall = overall_analysis()

r1, r2, r3, r4 = st.columns(4)

r1.metric(
    "전체",
    overall["total"]
)

r2.metric(
    "승",
    f'{overall["home"]}건 '
    f'({overall["home_pct"]}%)'
)

r3.metric(
    "무",
    f'{overall["draw"]}건 '
    f'({overall["draw_pct"]}%)'
)

r4.metric(
    "패",
    f'{overall["away"]}건 '
    f'({overall["away_pct"]}%)'
)


# --------------------------------------------------
# 업체별
# --------------------------------------------------

st.subheader(
    "🏢 저장 데이터 업체별"
)

company_rows = get_company_counts()

if company_rows:

    company_df = pd.DataFrame(
        company_rows,
        columns=[
            "업체",
            "저장 건수"
        ]
    )

    st.dataframe(
        company_df,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "저장된 데이터가 없습니다."
    )


# --------------------------------------------------
# 동일배당 분석
# --------------------------------------------------

st.divider()

st.subheader(
    "🎯 동일 최종배당 분석"
)

a1, a2, a3 = st.columns(3)

with a1:

    home_odds = st.number_input(
        "홈 배당",
        min_value=1.01,
        max_value=100.0,
        value=2.00,
        step=0.01
    )

with a2:

    draw_odds = st.number_input(
        "무 배당",
        min_value=1.01,
        max_value=100.0,
        value=3.50,
        step=0.01
    )

with a3:

    away_odds = st.number_input(
        "원정 배당",
        min_value=1.01,
        max_value=100.0,
        value=3.00,
        step=0.01
    )


same = same_odds_analysis(
    home_odds,
    draw_odds,
    away_odds
)


st.write(
    f"동일배당 경기: **{same['total']}건**"
)


s1, s2, s3 = st.columns(3)

s1.metric(
    "승",
    f"{same['home']}건 "
    f"({same['home_pct']}%)"
)

s2.metric(
    "무",
    f"{same['draw']}건 "
    f"({same['draw_pct']}%)"
)

s3.metric(
    "패",
    f"{same['away']}건 "
    f"({same['away_pct']}%)"
)


# --------------------------------------------------
# 배당 암시확률
# --------------------------------------------------

st.subheader(
    "📈 배당상 확률 / 부족확률"
)

prob = implied_probabilities(
    home_odds,
    draw_odds,
    away_odds
)

p1, p2, p3 = st.columns(3)

p1.metric(
    "승",
    f'{prob["home"]}%'
)

p2.metric(
    "무",
    f'{prob["draw"]}%'
)

p3.metric(
    "패",
    f'{prob["away"]}%'
)

st.caption(
    f"북메이커 마진 추정: "
    f'{prob["margin"]}%'
)


if same["total"] > 0:

    st.subheader(
        "🔎 실제 결과확률 대비 부족/초과"
    )

    d1, d2, d3 = st.columns(3)

    d1.metric(
        "승",
        f'{same["home_pct"] - prob["home"]:+.2f}%p'
    )

    d2.metric(
        "무",
        f'{same["draw_pct"] - prob["draw"]:+.2f}%p'
    )

    d3.metric(
        "패",
        f'{same["away_pct"] - prob["away"]:+.2f}%p'
    )


# --------------------------------------------------
# 수동 최종배당 입력
# --------------------------------------------------

st.divider()

st.subheader(
    "✍️ 수동 최종배당 입력"
)

with st.form(
    "manual_match_form"
):

    md = st.date_input(
        "경기 날짜",
        value=date.today()
    )

    league = st.text_input(
        "리그"
    )

    home_team = st.text_input(
        "홈팀"
    )

    away_team = st.text_input(
        "원정팀"
    )

    manual_company = st.text_input(
        "배당업체",
        value=(
            company_name
            if company_name != "전체"
            else ""
        )
    )

    mc1, mc2, mc3 = st.columns(3)

    with mc1:

        mo = st.number_input(
            "홈 최종배당",
            min_value=1.01,
            value=2.00,
            step=0.01
        )

    with mc2:

        md_odds = st.number_input(
            "무 최종배당",
            min_value=1.01,
            value=3.50,
            step=0.01
        )

    with mc3:

        ma = st.number_input(
            "원정 최종배당",
            min_value=1.01,
            value=3.00,
            step=0.01
        )

    result_label = st.selectbox(
        "결과",
        ["승", "무", "패"]
    )

    result_map = {
        "승": "H",
        "무": "D",
        "패": "A"
    }

    manual_submit = st.form_submit_button(
        "💾 최종배당 저장",
        use_container_width=True
    )

    if manual_submit:

        data = {
            "match_date":
                md.isoformat(),

            "league":
                league,

            "home_team":
                home_team,

            "away_team":
                away_team,

            "company":
                manual_company,

            "home_odds":
                mo,

            "draw_odds":
                md_odds,

            "away_odds":
                ma,

            "result":
                result_map[result_label],

            "home_probability":
                round(100 / mo, 2),

            "draw_probability":
                round(100 / md_odds, 2),

            "away_probability":
                round(100 / ma, 2),

            "source":
                "manual"
        }

        saved = save_manual_match(
            data
        )

        if saved:

            st.success(
                "최종배당을 저장했습니다."
            )

        else:

            st.info(
                "동일한 데이터가 이미 존재합니다."
            )


# --------------------------------------------------
# 진단
# --------------------------------------------------

st.divider()

st.subheader(
    "🔎 7M 페이지 연결 진단"
)

st.caption(
    "수집 결과가 0건이면 먼저 실제 서버 응답을 확인합니다."
)

diagnose_date = st.date_input(
    "진단 날짜",
    value=date.today()
)

if st.button(
    "페이지 연결 진단",
    use_container_width=True
):

    with st.spinner(
        "7M 서버 응답 확인 중..."
    ):

        st.session_state.diagnose = diagnose(
            diagnose_date,
            cid
        )


diagnostic = (
    st.session_state.diagnose
)


if diagnostic:

    st.write(
        f"HTTP 상태: "
        f"**{diagnostic['status']}**"
    )

    st.write(
        f"받은 데이터: "
        f"**{diagnostic['size']} bytes**"
    )

    st.write(
        "결과 페이지 문자열: "
        f"**{diagnostic['has_result']}**"
    )

    st.write(
        "비교 문자열: "
        f"**{diagnostic['has_compare']}**"
    )

    st.write(
        f"발견 후보: "
        f"**{diagnostic['found']}건**"
    )

    with st.expander(
        "서버에서 받은 HTML/JS 보기"
    ):

        st.code(
            diagnostic["html"],
            language="html"
        )


# --------------------------------------------------
# 전체 데이터
# --------------------------------------------------

st.divider()

st.subheader(
    "📋 저장 데이터"
)

rows = get_all_matches()

if rows:

    columns = [
        "ID",
        "날짜",
        "리그",
        "홈팀",
        "원정팀",
        "업체",
        "홈배당",
        "무배당",
        "원정배당",
        "결과",
        "홈확률",
        "무확률",
        "원정확률",
        "출처",
        "저장시간"
    ]

    df = pd.DataFrame(
        rows,
        columns=columns
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    csv = df.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        "⬇️ CSV 다운로드",
        data=csv,
        file_name="7m_odds.csv",
        mime="text/csv",
        use_container_width=True
    )

else:

    st.info(
        "저장 데이터가 없습니다."
    )


# --------------------------------------------------
# 로그
# --------------------------------------------------

if not hide_logs:

    st.divider()

    st.subheader(
        "📜 로그"
    )

    if worker:

        st.code(
            worker.message
        )

    else:

        st.code(
            "수집 대기 중..."
        )


# --------------------------------------------------
# 음성 안내
# --------------------------------------------------

st.divider()

st.subheader(
    "🔊 배당 음성 안내"
)

st.caption(
    "브라우저 음성합성 기능을 사용합니다. "
    "휴대폰 브라우저의 음성 기능 지원 여부에 따라 달라질 수 있습니다."
)

speech_text = st.text_area(
    "읽어줄 내용",
    value=(
        f"전체 {overall['total']}건. "
        f"승 {overall['home']}건, "
        f"무 {overall['draw']}건, "
        f"패 {overall['away']}건입니다."
    )
)

speech_html = f"""
<script>
function speakText() {{
    const text = {speech_text!r};
    if ('speechSynthesis' in window) {{
        window.speechSynthesis.cancel();
        const utterance =
            new SpeechSynthesisUtterance(text);
        utterance.lang = 'ko-KR';
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
    }} else {{
        alert('이 브라우저는 음성합성을 지원하지 않습니다.');
    }}
}}
</script>

<button
    onclick="speakText()"
    style="
        width:100%;
        padding:12px;
        border-radius:8px;
        border:1px solid #aaa;
        background:#f5f5f5;
        cursor:pointer;
        font-size:16px;
    "
>
🔊 결과 음성으로 듣기
</button>
"""

st.components.v1.html(
    speech_html,
    height=70
)


# --------------------------------------------------
# 자동 새로고침
# --------------------------------------------------

if worker and worker.running:

    import time

    time.sleep(1)

    st.rerun()
