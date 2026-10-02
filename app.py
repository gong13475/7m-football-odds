import re
import streamlit as st

from datetime import date, timedelta

import database
import collector
import analyzer

from worker import CollectorWorker


# =========================================================
# 설정
# =========================================================

st.set_page_config(
    page_title="7M 축구 최종배당 분석기",
    page_icon="⚽",
    layout="wide"
)


database.init_db()


# =========================================================
# 세션
# =========================================================

if "worker" not in st.session_state:

    st.session_state.worker = None


if "analysis_result" not in st.session_state:

    st.session_state.analysis_result = None


if "show_logs" not in st.session_state:

    st.session_state.show_logs = False


# =========================================================
# 제목
# =========================================================

st.title(
    "⚽ 7M 축구 최종배당 수집 · 분석기"
)

st.caption(
    "7M 데이터 전용 / 최종배당 / 동일배당 분석"
)


# =========================================================
# DB 현황
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

c4.metric(
    "현재 상태",
    (
        "수집 중"
        if (
            st.session_state.worker
            and st.session_state.worker.running
        )
        else "대기"
    )
)


st.divider()


# =========================================================
# 날짜
# =========================================================

st.header(
    "📅 수집 날짜"
)

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

    st.error(
        "종료 날짜는 시작 날짜보다 빠를 수 없습니다."
    )


# =========================================================
# 업체
# =========================================================

st.header(
    "🏢 7M 업체"
)

st.info(
    "현재 수집기는 7M의 1X2 최종배당 데이터만 사용합니다."
)

cid = st.text_input(
    "회사 필터 CID",
    value="",
    placeholder="비워두면 전체(index.js)"
)


# =========================================================
# 수집 설정
# =========================================================

st.header(
    "⚙️ 수집 설정"
)

c1, c2, c3 = st.columns(3)

with c1:

    retry_count = st.number_input(
        "실패 재시도 횟수",
        min_value=1,
        max_value=10,
        value=3
    )

with c2:

    request_delay = st.number_input(
        "요청 간격(초)",
        min_value=0.1,
        max_value=10.0,
        value=0.5,
        step=0.1
    )

with c3:

    hide_logs = st.checkbox(
        "로그 숨김",
        value=True
    )


# =========================================================
# Worker
# =========================================================

worker = st.session_state.worker


if worker and worker.running:

    st.error(
        "🔴 현재 수집 중"
    )

    if st.button(
        "⏹ 수집 중지",
        use_container_width=True
    ):

        worker.stop()

        st.warning(
            "중지 요청을 전달했습니다."
        )

        st.rerun()


else:

    if st.button(
        "▶ 수집 시작",
        type="primary",
        use_container_width=True
    ):

        if end_date < start_date:

            st.error(
                "날짜 범위를 확인하세요."
            )

        else:

            worker = CollectorWorker(
                start_date,
                end_date,
                cid=cid.strip(),
                retries=int(
                    retry_count
                ),
                delay=float(
                    request_delay
                )
            )

            st.session_state.worker = (
                worker
            )

            worker.start()

            st.success(
                "백그라운드 수집을 시작했습니다."
            )

            st.rerun()


# =========================================================
# 진행상황
# =========================================================

worker = st.session_state.worker


if worker:

    st.divider()

    st.header(
        "📡 수집 진행상황"
    )

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

            st.error(
                status["error"]
            )

        else:

            st.success(
                "🟢 수집 완료"
            )


# =========================================================
# 로그
# =========================================================

st.divider()

st.header(
    "📜 로그"
)


if not hide_logs:

    st.code(
        database.get_logs(),
        language="text"
    )

else:

    st.info(
        "로그 숨김 상태입니다."
    )


# =========================================================
# 진단
# =========================================================

st.divider()

st.header(
    "🔎 7M 연결 진단"
)

diagnose_date = st.date_input(
    "진단 날짜",
    value=start_date,
    key="diagnose_date"
)


if st.button(
    "7M 페이지 / JS 진단",
    use_container_width=True
):

    with st.spinner(
        "7M 서버 응답 확인 중..."
    ):

        result = collector.diagnose(
            diagnose_date,
            cid.strip()
        )


    c1, c2, c3 = st.columns(3)

    c1.metric(
        "HTTP 상태",
        result.get(
            "status",
            0
        )
    )

    c2.metric(
        "JS 데이터",
        result.get(
            "size",
            0
        )
    )

    c3.metric(
        "발견 후보",
        result.get(
            "found",
            0
        )
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
                result.get(
                    "html",
                    ""
                )
            )


        with st.expander(
            "7M History JS 보기"
        ):

            st.code(
                result.get(
                    "js",
                    ""
                )
            )


# =========================================================
# 동일 최종배당 분석
# =========================================================

st.divider()

st.header(
    "🎯 동일 최종배당 분석"
)

st.info(
    "입력한 배당 자체는 DB에 저장하지 않습니다. "
    "DB에 이미 저장된 7M 최종배당과 동일한 경기만 검색합니다."
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
# 음성 입력
# =========================================================

st.subheader(
    "🎙️ 음성 입력"
)

st.caption(
    "브라우저에서 음성인식이 지원되는 경우 "
    "음성 입력을 사용할 수 있습니다."
)


voice_text = st.text_input(
    "음성 인식 결과를 배당 숫자로 입력",
    placeholder="예: 1.50 3.50 5.00"
)


if voice_text:

    numbers = re.findall(
        r"\d+(?:\.\d+)?",
        voice_text
    )

    if len(numbers) >= 3:

        st.success(
            "인식된 배당: "
            + " / ".join(
                numbers[:3]
            )
        )


# =========================================================
# 분석
# =========================================================

if st.button(
    "🔎 동일 배당 검색 및 분석",
    type="primary",
    use_container_width=True
):

    result = analyzer.run_search(
        home_odds,
        draw_odds,
        away_odds
    )

    st.session_state.analysis_result = (
        result
    )


# =========================================================
# 분석 결과
# =========================================================

result = st.session_state.analysis_result


if result:

    if not result["success"]:

        st.error(
            result["message"]
        )

    else:

        rows = result[
            "results"
        ]

        stats = result[
            "statistics"
        ]


        st.subheader(
            "📊 분석 결과"
        )


        total = stats[
            "total"
        ]


        h = stats[
            "counts"
        ]["H"]

        d = stats[
            "counts"
        ]["D"]

        a = stats[
            "counts"
        ]["A"]


        c1, c2, c3, c4 = st.columns(4)


        c1.metric(
            "전체",
            f"{total:,}"
        )

        c2.metric(
            "승",
            f"{h:,}",
            (
                f"{h / total * 100:.2f}%"
                if total
                else "0%"
            )
        )

        c3.metric(
            "무",
            f"{d:,}",
            (
                f"{d / total * 100:.2f}%"
                if total
                else "0%"
            )
        )

        c4.metric(
            "패",
            f"{a:,}",
            (
                f"{a / total * 100:.2f}%"
                if total
                else "0%"
            )
        )


        if total:

            st.subheader(
                "📈 배당상 확률 / 실제확률 / 부족확률"
            )


            table = []


            for key, label in [

                ("H", "승"),
                ("D", "무"),
                ("A", "패")

            ]:

                expected = stats[
                    "expected"
                ][key]

                actual = stats[
                    "actual"
                ][key]

                difference = stats[
                    "difference"
                ][key]


                table.append({

                    "결과":
                        label,

                    "배당상 확률":
                        f"{expected:.2f}%",

                    "실제 발생률":
                        f"{actual:.2f}%",

                    "부족확률":
                        f"{difference:+.2f}%",

                    "발생":
                        stats[
                            "counts"
                        ][key],

                    "전체":
                        total
                })


            st.dataframe(
                table,
                use_container_width=True,
                hide_index=True
            )


            best = max(
                [
                    "H",
                    "D",
                    "A"
                ],
                key=lambda key:
                    stats[
                        "difference"
                    ][key]
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


        # =================================================
        # 검색 경기
        # =================================================

        st.subheader(
            "📋 동일배당 경기"
        )


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
                        f"{row['home_score']}"
                        f" - "
                        f"{row['away_score']}",

                    "결과":
                        analyzer.result_label(
                            row["result"]
                        ),

                    "승":
                        row["home_odds"],

                    "무":
                        row["draw_odds"],

                    "패":
                        row["away_odds"]
                })


            st.dataframe(
                table,
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# 업체별 저장량
# =========================================================

st.divider()

st.header(
    "🏢 저장 데이터"
)


counts = database.get_company_counts()


if counts:

    st.dataframe(
        [
            {
                "업체":
                    company,

                "저장 건수":
                    count
            }

            for company, count
            in counts.items()
        ],
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "저장된 데이터가 없습니다."
    )


# =========================================================
# 전체 DB
# =========================================================

with st.expander(
    "🗃️ 저장된 전체 경기 보기"
):

    matches = (
        database.get_all_matches()
    )


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
                    f"{row['home_score']}"
                    f" - "
                    f"{row['away_score']}",

                "결과":
                    analyzer.result_label(
                        row["result"]
                    ),

                "승":
                    row["home_odds"],

                "무":
                    row["draw_odds"],

                "패":
                    row["away_odds"]
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
# 자동 갱신
# =========================================================

worker = st.session_state.worker


if worker and worker.running:

    st.markdown(
        """
        <script>
        setTimeout(
            function() {
                window.parent.location.reload();
            },
            3000
        );
        </script>
        """,
        unsafe_allow_html=True
        )
