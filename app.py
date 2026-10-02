import re
import streamlit as st

from datetime import date

import database
import collector
import analyzer

from worker import CollectorWorker


st.set_page_config(
    page_title="7M 축구 최종배당 분석기",
    page_icon="⚽",
    layout="wide"
)


database.init_db()


# =========================================================
# SESSION
# =========================================================

if "worker" not in st.session_state:
    st.session_state.worker = None

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None


# =========================================================
# TITLE
# =========================================================

st.title("⚽ 7M 축구 최종배당 수집 · 분석기")

st.caption(
    "7M 데이터 전용 / 1X2 최종배당 / 동일배당 과거결과 분석"
)


# =========================================================
# DB STATUS
# =========================================================

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "DB 전체 경기",
    f"{database.get_match_count():,}"
)

c2.metric(
    "저장 최종배당",
    f"{database.get_odds_count():,}"
)

c3.metric(
    "업체",
    "7M"
)

worker = st.session_state.worker

c4.metric(
    "현재 상태",
    "수집 중" if worker and worker.running else "대기"
)


st.divider()


# =========================================================
# COLLECTION DATE
# =========================================================

st.header("📅 수집 날짜")

c1, c2 = st.columns(2)

with c1:
    start_date = st.date_input(
        "시작 날짜",
        value=date.today()
    )

with c2:
    end_date = st.date_input(
        "종료 날짜",
        value=date.today()
    )


if end_date < start_date:
    st.error("종료 날짜는 시작 날짜보다 빠를 수 없습니다.")


# =========================================================
# CID
# =========================================================

st.header("🏢 7M 업체")

st.info(
    "현재 수집기는 7M의 1X2 최종배당 데이터를 대상으로 합니다. "
    "CID를 비워두면 index.js를 요청합니다."
)

cid = st.text_input(
    "회사 필터 CID",
    value="",
    placeholder="예: CID / 비워두면 전체"
)


# =========================================================
# SETTINGS
# =========================================================

st.header("⚙️ 수집 설정")

c1, c2, c3 = st.columns(3)

with c1:
    retry_count = st.number_input(
        "실패 재시도 횟수",
        min_value=1,
        max_value=10,
        value=3,
        step=1
    )

with c2:
    request_delay = st.number_input(
        "재시도 간격(초)",
        min_value=0.0,
        max_value=30.0,
        value=1.0,
        step=0.5
    )

with c3:
    hide_logs = st.checkbox(
        "로그 숨김",
        value=True
    )


# =========================================================
# WORKER
# =========================================================

worker = st.session_state.worker


if worker and worker.running:

    st.error("🔴 현재 수집 중")

    if st.button(
        "⏹ 수집 중지",
        use_container_width=True
    ):

        worker.stop()

        st.warning("중지 요청을 전달했습니다.")

        st.rerun()

else:

    if st.button(
        "▶ 수집 시작",
        type="primary",
        use_container_width=True
    ):

        if end_date < start_date:

            st.error("날짜 범위를 확인하세요.")

        else:

            worker = CollectorWorker(
                start_date=start_date,
                end_date=end_date,
                cid=cid.strip(),
                retries=int(retry_count),
                delay=float(request_delay)
            )

            st.session_state.worker = worker

            worker.start()

            st.success(
                "백그라운드 수집을 시작했습니다."
            )

            st.rerun()


# =========================================================
# PROGRESS
# =========================================================

worker = st.session_state.worker


if worker:

    st.divider()

    st.header("📡 수집 진행상황")

    status = worker.status()

    st.progress(
        status["progress"]
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "진행 날짜",
        f"{status['completed_days']:,}/"
        f"{status['total_days']:,}"
    )

    c2.metric(
        "발견",
        f"{status['found_rows']:,}"
    )

    c3.metric(
        "신규 저장",
        f"{status['saved_rows']:,}"
    )

    c4.metric(
        "실패일",
        f"{status['failed_days']:,}"
    )

    if status["last_completed_date"]:

        st.info(
            "마지막 완료 날짜: "
            f"**{status['last_completed_date']}**"
        )

    if status["running"]:

        st.warning(
            status["message"]
        )

    elif status["stopped"]:

        st.warning(
            "🛑 수집이 중지되었습니다."
        )

    elif status["finished"]:

        if status["error"]:
            st.error(status["error"])
        else:
            st.success("🟢 수집 완료")


# =========================================================
# LOG
# =========================================================

st.divider()

st.header("📜 로그")

if not hide_logs:

    logs = database.get_logs()

    if logs:
        st.code(logs, language="text")
    else:
        st.info("로그가 없습니다.")

else:

    st.info("로그 숨김 상태입니다.")


# =========================================================
# DIAGNOSTIC
# =========================================================

st.divider()

st.header("🔎 7M 연결 진단")

diagnose_date = st.date_input(
    "진단 날짜",
    value=start_date,
    key="diagnose_date"
)


if st.button(
    "7M 페이지 / History JS 진단",
    use_container_width=True
):

    with st.spinner(
        "7M 서버 응답 확인 중..."
    ):

        result = collector.diagnose(
            diagnose_date,
            cid.strip()
        )


    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "HTTP",
        result.get("status", 0)
    )

    c2.metric(
        "HTML",
        f"{result.get('html_size', 0):,}"
    )

    c3.metric(
        "JS",
        f"{result.get('size', 0):,}"
    )

    c4.metric(
        "발견 후보",
        f"{result.get('found', 0):,}"
    )


    if result.get("error"):

        st.error(
            result["error"]
        )

    else:

        st.success(
            "7M 서버 응답을 받았습니다."
        )

        with st.expander(
            "서버 HTML 보기"
        ):

            st.code(
                result.get("html", ""),
                language="html"
            )


        with st.expander(
            "7M History JS 보기"
        ):

            st.code(
                result.get("js", ""),
                language="javascript"
            )


# =========================================================
# SAME ODDS ANALYSIS
# =========================================================

st.divider()

st.header("🎯 동일 최종배당 분석")

st.info(
    "입력한 배당은 DB에 저장하지 않습니다. "
    "DB에 이미 저장된 7M 경기 중 동일한 1X2 최종배당을 검색합니다."
)


c1, c2, c3 = st.columns(3)

with c1:

    home_odds = st.number_input(
        "최종 승 배당",
        min_value=1.01,
        value=1.50,
        step=0.01,
        format="%.2f"
    )

with c2:

    draw_odds = st.number_input(
        "최종 무 배당",
        min_value=1.01,
        value=3.50,
        step=0.01,
        format="%.2f"
    )

with c3:

    away_odds = st.number_input(
        "최종 패 배당",
        min_value=1.01,
        value=5.00,
        step=0.01,
        format="%.2f"
    )


# =========================================================
# VOICE RESULT
# =========================================================

st.subheader("🎙️ 음성 입력 결과")

st.caption(
    "브라우저 음성인식 결과 또는 직접 입력한 "
    "숫자 3개를 사용할 수 있습니다."
)

voice_text = st.text_input(
    "음성 인식 결과",
    placeholder="예: 1.50 3.50 5.00"
)


if voice_text:

    numbers = re.findall(
        r"\d+(?:\.\d+)?",
        voice_text
    )

    if len(numbers) >= 3:

        voice_values = [
            float(numbers[0]),
            float(numbers[1]),
            float(numbers[2])
        ]

        st.success(
            "인식된 배당: "
            + " / ".join(
                f"{x:.2f}"
                for x in voice_values
            )
        )

        if st.button(
            "🎙️ 인식 배당으로 검색",
            use_container_width=True
        ):

            st.session_state.analysis_result = (
                analyzer.run_search(
                    *voice_values
                )
            )

            st.rerun()


# =========================================================
# SEARCH
# =========================================================

if st.button(
    "🔎 동일 배당 검색 및 분석",
    type="primary",
    use_container_width=True
):

    st.session_state.analysis_result = (
        analyzer.run_search(
            home_odds,
            draw_odds,
            away_odds
        )
    )


# =========================================================
# ANALYSIS RESULT
# =========================================================

result = st.session_state.analysis_result


if result:

    if not result["success"]:

        st.error(
            result["message"]
        )

    else:

        rows = result["results"]
        stats = result["statistics"]

        st.subheader("📊 분석 결과")

        total = stats["total"]

        h = stats["counts"]["H"]
        d = stats["counts"]["D"]
        a = stats["counts"]["A"]


        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "전체",
            f"{total:,}"
        )

        c2.metric(
            "승",
            f"{h:,}",
            f"{h / total * 100:.2f}%"
            if total else "0%"
        )

        c3.metric(
            "무",
            f"{d:,}",
            f"{d / total * 100:.2f}%"
            if total else "0%"
        )

        c4.metric(
            "패",
            f"{a:,}",
            f"{a / total * 100:.2f}%"
            if total else "0%"
        )


        if total:

            st.subheader(
                "📈 배당상 확률 / 실제 발생률 / 부족확률"
            )

            table = []

            for key, label in [
                ("H", "승"),
                ("D", "무"),
                ("A", "패")
            ]:

                table.append({
                    "결과": label,
                    "배당상 확률":
                        f"{stats['expected'][key]:.2f}%",
                    "실제 발생률":
                        f"{stats['actual'][key]:.2f}%",
                    "부족확률":
                        f"{stats['difference'][key]:+.2f}%p",
                    "발생":
                        stats["counts"][key],
                    "전체":
                        total
                })


            st.dataframe(
                table,
                use_container_width=True,
                hide_index=True
            )


            best = max(
                ["H", "D", "A"],
                key=lambda key:
                    stats["difference"][key]
            )


            labels = {
                "H": "승",
                "D": "무",
                "A": "패"
            }


            st.success(
                "배당 대비 실제 발생률이 가장 높은 결과: "
                f"**{labels[best]} "
                f"{stats['difference'][best]:+.2f}%p**"
            )


        # =====================================================
        # MATCHES
        # =====================================================

        st.subheader("📋 동일배당 경기")

        if not rows:

            st.info(
                "동일한 최종배당 경기가 없습니다."
            )

        else:

            table = []

            for row in rows:

                table.append({

                    "날짜":
                        row["match_date"],

                    "홈":
                        row["home_team"],

                    "원정":
                        row["away_team"],

                    "스코어":
                        f"{row['home_score']} - "
                        f"{row['away_score']}",

                    "결과":
                        analyzer.result_label(
                            row["result"]
                        ),

                    "승":
                        f"{row['home_odds']:.2f}",

                    "무":
                        f"{row['draw_odds']:.2f}",

                    "패":
                        f"{row['away_odds']:.2f}"
                })


            st.dataframe(
                table,
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# COMPANY DATA
# =========================================================

st.divider()

st.header("🏢 저장 데이터")

counts = database.get_company_counts()

if counts:

    st.dataframe(
        [
            {
                "업체": company,
                "저장 건수": count
            }
            for company, count in counts.items()
        ],
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "저장된 데이터가 없습니다."
    )


# =========================================================
# ALL DATABASE
# =========================================================

with st.expander(
    "🗃️ 저장된 전체 경기 보기"
):

    matches = database.get_all_matches()

    if matches:

        table = []

        for row in matches:

            table.append({

                "날짜":
                    row["match_date"],

                "홈":
                    row["home_team"],

                "원정":
                    row["away_team"],

                "스코어":
                    f"{row['home_score']} - "
                    f"{row['away_score']}",

                "결과":
                    analyzer.result_label(
                        row["result"]
                    ),

                "승":
                    f"{row['home_odds']:.2f}",

                "무":
                    f"{row['draw_odds']:.2f}",

                "패":
                    f"{row['away_odds']:.2f}"
            })


        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "DB가 비어 있습니다."
        )


# =========================================================
# AUTO REFRESH
# =========================================================

worker = st.session_state.worker

if worker and worker.running:

    st.markdown(
        """
        <script>
        setTimeout(function() {
            window.parent.location.reload();
        }, 3000);
        </script>
        """,
        unsafe_allow_html=True
    )
