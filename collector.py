import json
import re
import requests

from datetime import date, datetime, timedelta

import database


# =========================================================
# CONFIG
# =========================================================

BASE_URL = (
    "https://1x2.7mkr.com/"
    "result_kr.shtml"
)

DATA_BASE = (
    "https://px-1x2.7mdt.com/"
    "data/history/kr"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://1x2.7mkr.com/",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# =========================================================
# UTIL
# =========================================================

def _date_string(target_date):
    """
    날짜를 YYYY-MM-DD 문자열로 변환
    """

    if isinstance(target_date, datetime):
        return target_date.strftime("%Y-%m-%d")

    if isinstance(target_date, date):
        return target_date.strftime("%Y-%m-%d")

    return str(target_date).strip()


def _request(url, params=None):
    """
    HTTP GET
    """

    response = SESSION.get(
        url,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    response.encoding = (
        response.apparent_encoding
        or "utf-8"
    )

    return response.text


# =========================================================
# DOWNLOAD
# =========================================================

def download_result_page(
    target_date,
    cid="",
):
    """
    결과 페이지 다운로드
    """

    dt = _date_string(target_date)

    params = {
        "dt": dt,
    }

    if cid:
        params["cid"] = str(cid).strip()

    return _request(
        BASE_URL,
        params=params,
    )


def download_day(
    target_date,
    cid="",
):
    """
    7M history JS 다운로드

    기본:
        /YYYY-MM-DD/index.js

    cid 지정:
        /YYYY-MM-DD/{cid}.js
    """

    dt = _date_string(target_date)

    filename = (
        str(cid).strip()
        if cid
        else "index"
    )

    url = (
        f"{DATA_BASE}/"
        f"{dt}/"
        f"{filename}.js"
    )

    text = _request(url)

    if not text.strip():
        raise ValueError(
            "7M 서버가 빈 데이터를 반환했습니다."
        )

    return text


# =========================================================
# JS CLEANING
# =========================================================

def _clean_js(text):
    """
    JS 응답에서 HTML wrapper/comment 등을 제거
    """

    if text is None:
        return ""

    text = str(text)

    # BOM
    text = text.lstrip("\ufeff")

    # HTML 응답이 들어온 경우 script 내용 추출
    if "<html" in text.lower():

        scripts = re.findall(
            r"<script[^>]*>(.*?)</script>",
            text,
            flags=re.I | re.S,
        )

        if scripts:
            text = "\n".join(scripts)

    # block comment
    text = re.sub(
        r"/\*.*?\*/",
        "",
        text,
        flags=re.S,
    )

    # // comment
    text = re.sub(
        r"^\s*//.*?$",
        "",
        text,
        flags=re.MULTILINE,
    )

    return text.strip()


# =========================================================
# JSON EXTRACTION
# =========================================================

def _extract_json_objects(text):
    """
    JS 안에 포함된 JSON object/array 추출

    일반적인 JSONDecoder 방식으로
    가능한 object를 모두 탐색한다.
    """

    objects = []

    if not text:
        return objects

    decoder = json.JSONDecoder()

    for match in re.finditer(
        r"[\[{]",
        text,
    ):

        start = match.start()

        try:

            obj, _ = decoder.raw_decode(
                text[start:]
            )

            objects.append(obj)

        except Exception:
            continue

    return objects


def _js_to_json_candidate(text):
    """
    JSON이 아닌 간단한 JS object를
    JSON 형태로 변환하기 위한 보조 함수
    """

    candidate = text.strip()

    # JS key -> JSON key
    candidate = re.sub(
        r"([{,]\s*)([A-Za-z_$][\w$]*)\s*:",
        r'\1"\2":',
        candidate,
    )

    # single quote -> double quote
    candidate = re.sub(
        r"'([^'\\]*(?:\\.[^'\\]*)*)'",
        lambda m: json.dumps(
            m.group(1)
        ),
        candidate,
    )

    # trailing comma
    candidate = re.sub(
        r",\s*([}\]])",
        r"\1",
        candidate,
    )

    return candidate


# =========================================================
# FLATTEN
# =========================================================

def _flatten(obj):
    """
    중첩된 dict/list를 모두 순회
    """

    if isinstance(obj, dict):

        yield obj

        for value in obj.values():

            yield from _flatten(value)

    elif isinstance(obj, list):

        for value in obj:

            yield from _flatten(value)


# =========================================================
# NUMBER
# =========================================================

def _number(value):
    """
    숫자 변환
    """

    if isinstance(value, bool):
        return None

    if value is None:
        return None

    try:

        text = str(value).strip()

        text = text.replace(
            ",",
            "",
        )

        text = text.replace(
            "배",
            "",
        )

        return float(text)

    except Exception:
        return None


# =========================================================
# SCORE
# =========================================================

def _find_score(item):
    """
    경기 결과 스코어 탐색
    """

    # 문자열 score
    score_keys = [
        "score",
        "result",
        "ft",
        "fulltime",
        "fullTime",
        "final",
        "sc",
        "res",
    ]

    for key in score_keys:

        value = item.get(key)

        if not isinstance(value, str):
            continue

        match = re.search(
            r"(\d+)\s*[-:]\s*(\d+)",
            value,
        )

        if match:

            return (
                int(match.group(1)),
                int(match.group(2)),
            )

    # home score
    home_score = None

    for key in [
        "home_score",
        "homescore",
        "homeScore",
        "hscore",
        "hs",
        "hg",
        "homeGoals",
        "home_goals",
    ]:

        if key in item:

            home_score = _number(
                item[key]
            )

            break

    # away score
    away_score = None

    for key in [
        "away_score",
        "awayscore",
        "awayScore",
        "ascore",
        "ag",
        "awayGoals",
        "away_goals",
    ]:

        if key in item:

            away_score = _number(
                item[key]
            )

            break

    if (
        home_score is not None
        and away_score is not None
    ):

        return (
            int(home_score),
            int(away_score),
        )

    return None


# =========================================================
# ODDS
# =========================================================

def _valid_odd(value):
    """
    유효한 1X2 배당인지 확인
    """

    value = _number(value)

    return (
        value is not None
        and 1.0 < value <= 100.0
    )


def _find_odds(item):
    """
    홈/무/원정 배당 탐색
    """

    home_keys = [
        "home_odds",
        "homeodds",
        "homeOdds",
        "final_home",
        "finalHome",
        "odds1",
        "odd1",
        "hodd",
        "homeOdd",
        "home",
    ]

    draw_keys = [
        "draw_odds",
        "drawodds",
        "drawOdds",
        "final_draw",
        "finalDraw",
        "odds2",
        "odd2",
        "dodd",
        "drawOdd",
        "draw",
    ]

    away_keys = [
        "away_odds",
        "awayodds",
        "awayOdds",
        "final_away",
        "finalAway",
        "odds3",
        "odd3",
        "aodd",
        "awayOdd",
        "away",
    ]

    values = []

    for keys in (
        home_keys,
        draw_keys,
        away_keys,
    ):

        found = None

        for key in keys:

            if key not in item:
                continue

            if _valid_odd(
                item[key]
            ):

                found = _number(
                    item[key]
                )

                break

        values.append(found)

    if all(
        value is not None
        for value in values
    ):

        return tuple(values)

    # -----------------------------------------------------
    # 배열형 odds
    # -----------------------------------------------------

    for key, value in item.items():

        if not isinstance(
            value,
            (list, tuple),
        ):
            continue

        nums = []

        for x in value:

            if _valid_odd(x):

                nums.append(
                    _number(x)
                )

        if len(nums) >= 3:

            return tuple(
                nums[:3]
            )

    # -----------------------------------------------------
    # 문자열형 odds
    # -----------------------------------------------------

    for value in item.values():

        if not isinstance(
            value,
            str,
        ):
            continue

        nums = re.findall(
            r"\b\d+(?:\.\d{1,4})?\b",
            value,
        )

        valid = []

        for x in nums:

            if _valid_odd(x):

                valid.append(
                    float(x)
                )

        if len(valid) >= 3:

            return tuple(
                valid[:3]
            )

    return None


# =========================================================
# TEAM
# =========================================================

def _find_team(
    item,
    home=True,
):
    """
    홈/원정 팀명 탐색
    """

    if home:

        keys = [
            "home_team",
            "hometeam",
            "homeTeam",
            "team1",
            "team_1",
            "hteam",
            "homeName",
            "home_name",
            "homeTeamName",
        ]

    else:

        keys = [
            "away_team",
            "awayteam",
            "awayTeam",
            "team2",
            "team_2",
            "ateam",
            "awayName",
            "away_name",
            "awayTeamName",
        ]

    for key in keys:

        value = item.get(key)

        if (
            isinstance(value, str)
            and value.strip()
        ):

            return value.strip()

    return ""


# =========================================================
# RESULT
# =========================================================

def _get_result(
    home_score,
    away_score,
):
    """
    H / D / A
    """

    if home_score > away_score:
        return "H"

    if home_score < away_score:
        return "A"

    return "D"


# =========================================================
# MATCH EXTRACTION
# =========================================================

def extract_matches(js):
    """
    JS에서 경기 데이터를 추출
    """

    text = _clean_js(js)

    if not text:
        return []

    objects = _extract_json_objects(
        text
    )

    results = []

    seen = set()

    for obj in objects:

        for item in _flatten(obj):

            if not isinstance(
                item,
                dict,
            ):
                continue

            score = _find_score(item)

            if score is None:
                continue

            odds = _find_odds(item)

            if odds is None:
                continue

            home_score, away_score = score

            (
                home_odds,
                draw_odds,
                away_odds,
            ) = odds

            result = _get_result(
                home_score,
                away_score,
            )

            home_team = _find_team(
                item,
                True,
            )

            away_team = _find_team(
                item,
                False,
            )

            # 팀명이 없는 데이터도 저장은 가능하지만
            # 완전히 의미 없는 object를 줄이기 위해
            # 양쪽 모두 없는 경우만 제외
            if (
                not home_team
                and not away_team
            ):
                continue

            key = (
                home_team,
                away_team,
                home_score,
                away_score,
                round(home_odds, 4),
                round(draw_odds, 4),
                round(away_odds, 4),
            )

            if key in seen:
                continue

            seen.add(key)

            results.append({

                "home_team":
                    home_team,

                "away_team":
                    away_team,

                "home_score":
                    home_score,

                "away_score":
                    away_score,

                "home_odds":
                    home_odds,

                "draw_odds":
                    draw_odds,

                "away_odds":
                    away_odds,

                "result":
                    result,

                "home_probability":
                    round(
                        100.0 / home_odds,
                        4,
                    ),

                "draw_probability":
                    round(
                        100.0 / draw_odds,
                        4,
                    ),

                "away_probability":
                    round(
                        100.0 / away_odds,
                        4,
                    ),
            })

    return results


# =========================================================
# MATCH KEY
# =========================================================

def _make_match_key(
    target_date,
    row,
):
    """
    DB 중복 방지용 key
    """

    return "|".join([

        _date_string(
            target_date
        ),

        str(
            row.get(
                "home_team",
                "",
            )
        ),

        str(
            row.get(
                "away_team",
                "",
            )
        ),

        str(
            row.get(
                "home_score",
                "",
            )
        ),

        str(
            row.get(
                "away_score",
                "",
            )
        ),

        f"{float(row['home_odds']):.4f}",

        f"{float(row['draw_odds']):.4f}",

        f"{float(row['away_odds']):.4f}",

        str(
            row.get(
                "result",
                "",
            )
        ),
    ])


# =========================================================
# SAVE DAY
# =========================================================

def collect_day(
    target_date,
    cid="",
):
    """
    하루 데이터를 다운로드하여 DB 저장
    """

    target_date = _date_string(
        target_date
    )

    try:

        js = download_day(
            target_date,
            cid,
        )

        rows = extract_matches(
            js
        )

        saved = 0

        for row in rows:

            match_key = _make_match_key(
                target_date,
                row,
            )

            value = database.save_match({

                "match_key":
                    match_key,

                "match_date":
                    target_date,

                "league":
                    "",

                "home_team":
                    row["home_team"],

                "away_team":
                    row["away_team"],

                "home_score":
                    row["home_score"],

                "away_score":
                    row["away_score"],

                "result":
                    row["result"],

                "home_odds":
                    row["home_odds"],

                "draw_odds":
                    row["draw_odds"],

                "away_odds":
                    row["away_odds"],

                "home_probability":
                    row["home_probability"],

                "draw_probability":
                    row["draw_probability"],

                "away_probability":
                    row["away_probability"],

                "source":
                    "7M",
            })

            saved += int(
                value or 0
            )

        database.save_collection_day(
            target_date,
            "success",
            len(rows),
            saved,
        )

        database.add_log(
            (
                f"수집 완료: "
                f"{target_date} / "
                f"found={len(rows)} / "
                f"saved={saved}"
            ),
            "INFO",
        )

        return {
            "success": True,
            "found": len(rows),
            "saved": saved,
            "error": None,
        }

    except Exception as error:

        database.save_collection_day(
            target_date,
            "failed",
            0,
            0,
            str(error),
        )

        database.add_log(
            (
                f"수집 실패: "
                f"{target_date} / "
                f"{error}"
            ),
            "ERROR",
        )

        raise


# =========================================================
# COLLECT RANGE
# =========================================================

def collect_range(
    start_date,
    end_date,
    cid="",
    stop_check=None,
):
    """
    시작일부터 종료일까지 순차 수집

    stop_check:
        호출 시 True이면 중지
    """

    if isinstance(
        start_date,
        str,
    ):

        start_date = datetime.strptime(
            start_date,
            "%Y-%m-%d",
        ).date()

    if isinstance(
        end_date,
        str,
    ):

        end_date = datetime.strptime(
            end_date,
            "%Y-%m-%d",
        ).date()

    if start_date > end_date:

        raise ValueError(
            "start_date가 end_date보다 늦습니다."
        )

    total_found = 0
    total_saved = 0

    current = start_date

    database.save_collection_state(
        start_date=start_date,
        end_date=end_date,
        last_completed_date=None,
        running=True,
        stopped=False,
    )

    try:

        while current <= end_date:

            if (
                stop_check
                and stop_check()
            ):

                database.save_collection_state(
                    start_date=start_date,
                    end_date=end_date,
                    last_completed_date=(
                        current - timedelta(days=1)
                    ),
                    running=False,
                    stopped=True,
                )

                database.add_log(
                    "수집 작업이 중지되었습니다.",
                    "INFO",
                )

                return {
                    "success": False,
                    "stopped": True,
                    "found": total_found,
                    "saved": total_saved,
                }

            result = collect_day(
                current,
                cid,
            )

            total_found += result[
                "found"
            ]

            total_saved += result[
                "saved"
            ]

            database.save_collection_state(
                start_date=start_date,
                end_date=end_date,
                last_completed_date=current,
                running=True,
                stopped=False,
            )

            current += timedelta(
                days=1
            )

        database.save_collection_state(
            start_date=start_date,
            end_date=end_date,
            last_completed_date=end_date,
            running=False,
            stopped=False,
        )

        database.add_log(
            (
                f"기간 수집 완료: "
                f"{_date_string(start_date)} ~ "
                f"{_date_string(end_date)} / "
                f"found={total_found} / "
                f"saved={total_saved}"
            ),
            "INFO",
        )

        return {
            "success": True,
            "stopped": False,
            "found": total_found,
            "saved": total_saved,
        }

    except Exception:

        database.save_collection_state(
            start_date=start_date,
            end_date=end_date,
            last_completed_date=(
                current - timedelta(days=1)
            ),
            running=False,
            stopped=False,
        )

        raise


# =========================================================
# DIAGNOSIS
# =========================================================

def diagnose(
    target_date,
    cid="",
):
    """
    다운로드 및 parser 상태 확인
    """

    try:

        html = download_result_page(
            target_date,
            cid,
        )

        js = download_day(
            target_date,
            cid,
        )

        rows = extract_matches(
            js
        )

        return {

            "status":
                200,

            "size":
                len(js),

            "html_size":
                len(html),

            "found":
                len(rows),

            "has_result":
                "result" in html.lower(),

            "has_compare":
                "비교" in html,

            "html":
                html[:10000],

            "js":
                js[:30000],
        }

    except Exception as error:

        return {

            "status":
                0,

            "size":
                0,

            "html_size":
                0,

            "found":
                0,

            "has_result":
                False,

            "has_compare":
                False,

            "html":
                "",

            "js":
                "",

            "error":
                str(error),
        }


# =========================================================
# QUICK TEST
# =========================================================

if __name__ == "__main__":

    database.init_db()

    today = date.today()

    result = collect_day(
        today
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
)
