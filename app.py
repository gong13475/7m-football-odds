# ============================================================
# app.py
# ⚽ 7M 축구 최종배당 수집 · 분석기
# 7M 데이터 전용 / 1X2 최종배당 / 동일배당 과거결과 분석
# ============================================================

import streamlit as st
from datetime import date, datetime

import database
import analysis
import sevenm_crawler


# ============================================================
# 페이지 설정
# ============================================================

st.set_page_config(
    page_title="7M 축구 최종배당 수집 · 분석기",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================
# DB 초기화
# ============================================================

try:
    database.init_database()
except Exception as e:
    st.error("DATABASE 초기화 오류")
    st.code(str(e))
    st.stop()


# ============================================================
# 세션 상태
# ============================================================

if "logs" not in st.session_state:
    st.session_state.logs = []

if "collecting" not in st.session_state:
    st.session_state.collecting = False

if "collection_result" not in st.session_state:
    st.session_state.collection_result = []

if "diagnostic" not in st.session_state:
    st.session_state.diagnostic = None


# ============================================================
# 로그
# ============================================================

def add_log(message):

    timestamp = datetime.now().strftime(
        "%H:%M:%S"
    )

    st.session_state.logs.append(
        f"[{timestamp}] {message}"
    )

    # 너무 많은 로그 방지
    if len(st.session_state.logs) > 1000:
        st.session_state.logs = (
            st.session_state.logs[-1000:]
        )


# ============================================================
# 제목
# ============================================================

st.title(
    "⚽ 7M 축구 최종배당 수집 · 분석기"
)

st.caption(
    "7M 데이터 전용 / 1X2 최종배당 / 동일배당 과거결과 분석"
)


# ============================================================
# DB 상태
# ============================================================

try:

    status = database.get_database_status()

    total_matches = status.get(
        "matches",
        0
    )

    total_odds = status.get(
        "odds",
        0
    )

    bookmakers = status.get(
        "bookmakers",
        0
    )

except Exception:

    total_matches = 0
    total_odds = 0
    bookmakers = 0


# ============================================================
# 상단 상태
# ============================================================

c1, c2, c3, c4 = st.columns(4)

with c1:

    st.metric(
        "DB 전체 경기",
        f"{total_matches:,}"
    )

with c2:

    st.metric(
        "저장 최종배당",
        f"{total_odds:,}"
    )

with c3:

    st.metric(
        "업체",
        "7M"
    )

with c4:

    status_text = (
        "수집중"
        if st.session_state.collecting
        else "대기"
    )

    st.metric(
        "현재 상태",
        status_text
    )


st.divider()


# ============================================================
# 날짜 설정
# ============================================================

st.subheader("📅 수집 날짜")

date_col1, date_col2 = st.columns(2)

with date_col1:

    start_date = st.date_input(
        "시작 날짜",
        value=date.today(),
        key="start_date"
    )

with date_col2:

    end_date = st.date_input(
        "종료 날짜",
        value=date.today(),
        key="end_date"
    )


# ============================================================
# 날짜 검사
# ============================================================

if start_date > end_date:

    st.error(
        "종료 날짜는 시작 날짜보다 빠를 수 없습니다."
    )


# ============================================================
# 7M 업체
# ============================================================

st.subheader("🏢 7M 업체")

st.info(
    "CID를 비워두면 7M 페이지의 기본 index.js 후보를 "
    "자동으로 탐색합니다."
)

cid = st.text_input(
    "회사 필터 CID",
    value="",
    placeholder="예: CID / 비워두면 자동 탐색"
)


# ============================================================
# 수집 설정
# ============================================================

st.subheader("⚙️ 수집 설정")

setting1, setting2 = st.columns(2)

with setting1:

    retry_count = st.number_input(
        "실패 재시도 횟수",
        min_value=0,
        max_value=10,
        value=3,
        step=1
    )

with setting2:

    retry_delay = st.number_input(
        "재시도 간격(초)",
        min_value=0.1,
        max_value=10.0,
        value=1.0,
        step=0.5
    )


# ============================================================
# 버튼
# ============================================================

st.subheader("⚙️ 수집 제어")

button1, button2, button3 = st.columns(3)

with button1:

    start_button = st.button(
        "▶️ 수집 시작",
        type="primary",
        use_container_width=True
    )

with button2:

    clear_log_button = st.button(
        "🗑️ 로그 지우기",
        use_container_width=True
    )

with button3:

    show_log = st.toggle(
        "📜 로그 표시",
        value=False
    )


# ============================================================
# 로그 삭제
# ============================================================

if clear_log_button:

    st.session_state.logs = []

    st.success(
        "로그를 지웠습니다."
    )


# ============================================================
# 수집 시작
# ============================================================

if start_button:

    if start_date > end_date:

        st.error(
            "날짜 설정을 확인하세요."
        )

        st.stop()

    st.session_state.collecting = True

    st.session_state.collection_result = []

    st.session_state.logs = []

    add_log(
        f"수집 시작: "
        f"{start_date} ~ {end_date}"
    )

    add_log(
        f"CID: "
        f"{cid if cid.strip() else '자동 탐색'}"
    )

    try:

        result = sevenm_crawler.collect(

            start_date=start_date.strftime(
                "%Y-%m-%d"
            ),

            end_date=end_date.strftime(
                "%Y-%m-%d"
            ),

            cid=cid.strip(),

            retry_count=int(
                retry_count
            ),

            retry_delay=float(
                retry_delay
            ),

            log_callback=add_log
        )

        st.session_state.collection_result = (
            result
        )

        # ----------------------------------------------------
        # DB 저장
        # ----------------------------------------------------

        saved_matches = 0
        saved_odds = 0
        failed = 0

        for item in result:

            try:

                match_id = item.get(
                    "match_id"
                )

                if not match_id:
                    failed += 1
                    continue

                database.save_match(

                    match_id=match_id,

                    match_date=item.get(
                        "match_date"
                    ),

                    home_team=item.get(
                        "home_team",
                        ""
                    ),

                    away_team=item.get(
                        "away_team",
                        ""
                    ),

                    home_score=item.get(
                        "home_score"
                    ),

                    away_score=item.get(
                        "away_score"
                    ),

                    result=item.get(
                        "result"
                    )
                )

                saved_matches += 1

                if database.save_odds(

                    match_id=match_id,

                    home_odds=item.get(
                        "home_odds"
                    ),

                    draw_odds=item.get(
                        "draw_odds"
                    ),

                    away_odds=item.get(
                        "away_odds"
                    ),

                    cid=item.get(
                        "cid",
                        cid.strip()
                    ),

                    bookmaker="7M"
                ):

                    saved_odds += 1

            except Exception as e:

                failed += 1

                add_log(
                    f"DB 저장 실패: {e}"
                )

        add_log(
            f"DB 경기 저장: "
            f"{saved_matches}"
        )

        add_log(
            f"최종배당 저장: "
            f"{saved_odds}"
        )

        add_log(
            f"실패: "
            f"{failed}"
        )

        # ----------------------------------------------------
        # 수집 로그
        # ----------------------------------------------------

        try:

            database.save_collection_log(

                start_date=start_date.strftime(
                    "%Y-%m-%d"
                ),

                end_date=end_date.strftime(
                    "%Y-%m-%d"
                ),

                cid=cid.strip(),

                total_matches=len(
                    result
                ),

                saved_matches=saved_matches,

                saved_odds=saved_odds,

                failed=failed,

                started_at=datetime.now().isoformat(
                    timespec="seconds"
                ),

                finished_at=datetime.now().isoformat(
                    timespec="seconds"
                ),

                status="완료"
            )

        except Exception as e:

            add_log(
                f"수집 로그 저장 실패: {e}"
            )

        st.session_state.collecting = False

        st.success(
            f"수집 완료 — "
            f"경기 {saved_matches}개 / "
            f"최종배당 {saved_odds}개"
        )

        st.rerun()

    except Exception as e:

        st.session_state.collecting = False

        add_log(
            f"수집 오류: {e}"
        )

        st.error(
            "수집 중 오류가 발생했습니다."
        )

        st.code(
            str(e)
        )


# ============================================================
# 현재 상태
# ============================================================

if st.session_state.collecting:

    st.warning(
        "🔄 7M 데이터를 수집하고 있습니다."
    )

else:

    st.info(
        "현재 상태: 대기"
    )


# ============================================================
# 로그
# ============================================================

st.subheader("📜 로그")

if show_log:

    if st.session_state.logs:

        st.code(
            "\n".join(
                st.session_state.logs
            ),
            language="text"
        )

    else:

        st.info(
            "로그가 없습니다."
        )

else:

    st.info(
        "로그 숨김 상태입니다."
    )


st.divider()


# ============================================================
# 7M 연결 진단
# ============================================================

st.subheader("🔎 7M 연결 진단")

diagnostic_date = st.date_input(
    "진단 날짜",
    value=date.today(),
    key="diagnostic_date"
)

diagnose_button = st.button(
    "🔎 7M 연결 진단 실행",
    use_container_width=True
)


if diagnose_button:

    add_log(
        f"7M 연결 진단 시작: "
        f"{diagnostic_date}"
    )

    try:

        diagnostic = sevenm_crawler.diagnose(

            date_string=diagnostic_date.strftime(
                "%Y-%m-%d"
            ),

            cid=cid.strip(),

            log_callback=add_log
        )

        st.session_state.diagnostic = (
            diagnostic
        )

    except Exception as e:

        st.session_state.diagnostic = None

        st.error(
            "진단 오류"
        )

        st.code(
            str(e)
        )


# ============================================================
# 진단 결과
# ============================================================

if st.session_state.diagnostic:

    diagnostic = (
        st.session_state.diagnostic
    )

    d1, d2, d3, d4 = st.columns(4)

    with d1:

        st.metric(
            "HTTP",
            diagnostic.get(
                "http",
                0
            )
        )

    with d2:

        st.metric(
            "HTML",
            f"{diagnostic.get('html_bytes', 0):,}"
        )

    with d3:

        st.metric(
            "JS",
            f"{diagnostic.get('js_bytes', 0):,}"
        )

    with d4:

        st.metric(
            "발견 후보",
            diagnostic.get(
                "match_candidates",
                0
            )
        )

    e1, e2, e3 = st.columns(3)

    with e1:

        st.metric(
            "iframe",
            diagnostic.get(
                "iframes",
                0
            )
        )

    with e2:

        st.metric(
            "script",
            diagnostic.get(
                "scripts",
                0
            )
        )

    with e3:

        st.metric(
            "API 후보",
            diagnostic.get(
                "apis",
                0
            )
        )

    if diagnostic.get(
        "match_candidates",
        0
    ) == 0:

        st.warning(
            "HTTP 200 응답은 성공했지만 "
            "7M 경기 행을 찾지 못했습니다. "
            "iframe / scripts / API 구조를 확인하세요."
        )

    else:

        st.success(
            "7M 경기 후보를 발견했습니다."
        )


st.divider()


# ============================================================
# 전체 DB 분석
# ============================================================

st.subheader(
    "📊 전체 DB 승무패 통계"
)

try:

    overall = analysis.overall_analysis()

except Exception:

    overall = {
        "total": 0,
        "win": 0,
        "draw": 0,
        "lose": 0,
        "win_pct": 0,
        "draw_pct": 0,
        "lose_pct": 0
    }


a1, a2, a3, a4 = st.columns(4)

with a1:

    st.metric(
        "전체 경기",
        f"{overall.get('total', 0):,}"
    )

with a2:

    st.metric(
        "승",
        f"{overall.get('win', 0):,} "
        f"({overall.get('win_pct', 0):.2f}%)"
    )

with a3:

    st.metric(
        "무",
        f"{overall.get('draw', 0):,} "
        f"({overall.get('draw_pct', 0):.2f}%)"
    )

with a4:

    st.metric(
        "패",
        f"{overall.get('lose', 0):,} "
        f"({overall.get('lose_pct', 0):.2f}%)"
    )


st.divider()


# ============================================================
# 동일배당 분석
# ============================================================

st.subheader(
    "🎯 동일 최종배당 과거결과 분석"
)

od1, od2, od3 = st.columns(3)

with od1:

    input_home = st.number_input(
        "홈 배당",
        min_value=1.01,
        max_value=100.0,
        value=2.00,
        step=0.01,
        format="%.2f"
    )

with od2:

    input_draw = st.number_input(
        "무 배당",
        min_value=1.01,
        max_value=100.0,
        value=3.20,
        step=0.01,
        format="%.2f"
    )

with od3:

    input_away = st.number_input(
        "원정 배당",
        min_value=1.01,
        max_value=100.0,
        value=3.50,
        step=0.01,
        format="%.2f"
    )


tolerance = st.number_input(
    "동일배당 허용 오차",
    min_value=0.00,
    max_value=0.10,
    value=0.01,
    step=0.01,
    format="%.2f"
)


analyze_button = st.button(
    "🔎 동일배당 분석",
    type="primary",
    use_container_width=True
)


if analyze_button:

    result = analysis.full_analysis(

        home_odds=input_home,

        draw_odds=input_draw,

        away_odds=input_away,

        tolerance=tolerance
    )

    st.session_state.same_odds_analysis = (
        result
    )


# ============================================================
# 동일배당 결과
# ============================================================

if "same_odds_analysis" in st.session_state:

    result = (
        st.session_state.same_odds_analysis
    )

    st.markdown(
        f"### 배당 "
        f"{result.get('home_odds', 0):.2f} / "
        f"{result.get('draw_odds', 0):.2f} / "
        f"{result.get('away_odds', 0):.2f}"
    )

    r1, r2, r3, r4 = st.columns(4)

    with r1:

        st.metric(
            "표본 경기",
            f"{result.get('total', 0):,}"
        )

    with r2:

        st.metric(
            "승",
            f"{result.get('승', 0)}경기",
            f"{result.get('승률', 0):.2f}%"
        )

    with r3:

        st.metric(
            "무",
            f"{result.get('무', 0)}경기",
            f"{result.get('무율', 0):.2f}%"
        )

    with r4:

        st.metric(
            "패",
            f"{result.get('패', 0)}경기",
            f"{result.get('패율', 0):.2f}%"
        )

    st.markdown("#### 📈 배당 예상확률")

    p1, p2, p3 = st.columns(3)

    with p1:

        st.metric(
            "예상 승",
            f"{result.get('예상승률', 0):.2f}%"
        )

    with p2:

        st.metric(
            "예상 무",
            f"{result.get('예상무율', 0):.2f}%"
        )

    with p3:

        st.metric(
            "예상 패",
            f"{result.get('예상패율', 0):.2f}%"
        )

    st.markdown(
        "#### 📊 확률대비 부족확률"
    )

    s1, s2, s3 = st.columns(3)

    with s1:

        st.metric(
            "승 차이",
            f"{result.get('승차이', 0):+.2f}%p"
        )

    with s2:

        st.metric(
            "무 차이",
            f"{result.get('무차이', 0):+.2f}%p"
        )

    with s3:

        st.metric(
            "패 차이",
            f"{result.get('패차이', 0):+.2f}%p"
        )

    if result.get("추천"):

        st.success(
            f"과거 동일배당 최다 결과: "
            f"**{result.get('추천')}**"
        )

    if result.get("부족결과"):

        st.info(
            f"예상확률 대비 가장 높은 결과: "
            f"**{result.get('부족결과')}**"
        )

    st.caption(
        f"시장 마진: "
        f"{result.get('마진', 0):.2f}%"
    )


st.divider()


# ============================================================
# 저장 경기 조회
# ============================================================

st.subheader(
    "📋 저장된 7M 경기"
)

limit = st.number_input(
    "표시 경기 수",
    min_value=10,
    max_value=1000,
    value=100,
    step=10
)

try:

    rows = database.get_matches(
        limit=int(limit)
    )

except Exception as e:

    rows = []

    st.error(
        "경기 조회 오류"
    )

    st.code(
        str(e)
    )


if rows:

    display_rows = []

    for row in rows:

        result_text = (
            row.get("result")
            or "-"
        )

        score = "-"

        if (
            row.get("home_score")
            is not None
            and
            row.get("away_score")
            is not None
        ):

            score = (
                f"{row['home_score']}"
                f" : "
                f"{row['away_score']}"
            )

        display_rows.append({

            "날짜":
                row.get(
                    "match_date"
                ) or "-",

            "홈팀":
                row.get(
                    "home_team"
                ) or "-",

            "원정팀":
                row.get(
                    "away_team"
                ) or "-",

            "최종스코어":
                score,

            "실제결과":
                result_text,

            "홈배당":
                (
                    f"{row['home_odds']:.2f}"
                    if row.get(
                        "home_odds"
                    ) is not None
                    else "-"
                ),

            "무배당":
                (
                    f"{row['draw_odds']:.2f}"
                    if row.get(
                        "draw_odds"
                    ) is not None
                    else "-"
                ),

            "원정배당":
                (
                    f"{row['away_odds']:.2f}"
                    if row.get(
                        "away_odds"
                    ) is not None
                    else "-"
                ),

            "업체":
                "7M"
        })

    st.dataframe(
        display_rows,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "저장된 경기가 없습니다."
    )


# ============================================================
# 하단
# ============================================================

st.divider()

st.caption(
    "⚽ 7M 축구 최종배당 수집 · 분석기 | "
    "7M 전용 데이터 / 1X2 최종배당 / "
    "동일배당 과거결과 분석"
           )
