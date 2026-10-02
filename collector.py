import json
import re
import requests

from datetime import date

import database


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
    "Referer": "https://1x2.7mkr.com/"
}


SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# =========================================================
# UTIL
# =========================================================

def _date_string(target_date):

    if isinstance(target_date, date):
        return target_date.strftime("%Y-%m-%d")

    return str(target_date)


def _request(url, params=None):

    response = SESSION.get(
        url,
        params=params,
        timeout=30
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
    cid=""
):

    dt = _date_string(target_date)

    params = {
        "dt": dt
    }

    if cid:
        params["cid"] = cid

    return _request(
        BASE_URL,
        params=params
    )


def download_day(
    target_date,
    cid=""
):

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

    text = text.lstrip("\ufeff")

    # HTML 응답이 실수로 들어온 경우
    if "<html" in text.lower():

        scripts = re.findall(
            r"<script[^>]*>(.*?)</script>",
            text,
            flags=re.I | re.S
        )

        if scripts:
            text = "\n".join(scripts)

    # block comment
    text = re.sub(
        r"/\*.*?\*/",
        "",
        text,
        flags=re.S
    )

    # line comment
    text = re.sub(
        r"^\s*//.*?$",
        "",
        text,
        flags=re.MULTILINE
    )

    return text.strip()


# =========================================================
# JSON EXTRACTION
# =========================================================

def _extract_json_objects(text):

    objects = []

    decoder = json.JSONDecoder()

    positions = [
        m.start()
        for m in re.finditer(
            r"[\[{]",
            text
        )
    ]

    for start in positions:

        try:

            obj, _ = decoder.raw_decode(
                text[start:]
            )

            objects.append(obj)

        except Exception:

            continue

    return objects


def _js_to_json_candidate(text):

    candidate = text.strip()

    # JS object key -> JSON key
    candidate = re.sub(
        r"([{,]\s*)([A-Za-z_$][\w$]*)\s*:",
        r'\1"\2":',
        candidate
    )

    # single quote -> double quote
    candidate = re.sub(
        r"'([^'\\]*(?:\\.[^'\\]*)*)'",
        lambda m:
            json.dumps(m.group(1)),
        candidate
    )

    candidate = re.sub(
        r",\s*([}\]])",
        r"\1",
        candidate
    )

    return candidate


# =========================================================
# FLATTEN
# =========================================================

def _flatten(obj):

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

    if isinstance(value, bool):
        return None

    try:

        text = str(value).strip()

        text = text.replace(",", "")

        # 배당에 붙은 특수문자 제거
        text = text.replace("배", "")

        return float(text)

    except Exception:

        return None


# =========================================================
# SCORE
# =========================================================

def _find_score(item):

    keys = [
        "score",
        "result",
        "ft",
        "fulltime",
        "final",
        "sc",
        "res"
    ]

    for key in keys:

        value = item.get(key)

        if isinstance(value, str):

            match = re.search(
                r"(\d+)\s*[-:]\s*(\d+)",
                value
            )

            if match:

                return (
                    int(match.group(1)),
                    int(match.group(2))
                )


    home_score = None
    away_score = None


    for key in [
        "home_score",
        "homescore",
        "homeScore",
        "hscore",
        "hs",
        "hg"
    ]:

        if key in item:

            home_score = _number(
                item[key]
            )

            break


    for key in [
        "away_score",
        "awayscore",
        "awayScore",
        "ascore",
        "as",
        "ag"
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
            int(away_score)
        )


    return None


# =========================================================
# ODDS
# =========================================================

def _valid_odd(value):

    value = _number(value)

    return (
        value is not None
        and 1.0 < value <= 100.0
    )


def _find_odds(item):

    groups = [

        (
            [
                "home_odds",
                "homeodds",
                "homeOdds",
                "final_home",
                "finalHome",
                "odds1",
                "odd1",
                "hodd",
                "h"
            ],
            [
                "draw_odds",
                "drawodds",
                "drawOdds",
                "final_draw",
                "finalDraw",
                "odds2",
                "odd2",
                "dodd",
                "d"
            ],
            [
                "away_odds",
                "awayodds",
                "awayOdds",
                "final_away",
                "finalAway",
                "odds3",
                "odd3",
                "aodd",
                "a"
            ]
        )
    ]


    for home_keys, draw_keys, away_keys in groups:

        values = []

        for keys in (
            home_keys,
            draw_keys,
            away_keys
        ):

            found = None

            for key in keys:

                if key in item:

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


    # 배열형
    for key, value in item.items():

        if not isinstance(
            value,
            (list, tuple)
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


    # 문자열 안에 3개 배당이 들어있는 경우
    for value in item.values():

        if not isinstance(value, str):
            continue

        nums = re.findall(
            r"\b\d+(?:\.\d{1,4})?\b",
            value
        )

        valid = []

        for x in nums:

            if _valid_odd(x):

                valid.append(
                    float(x)
                )

        if len(valid) >= 3:

            return tuple(valid[:3])


    return None


# =========================================================
# TEAM
# =========================================================

def _find_team(
    item,
    home=True
):

    if home:

        keys = [
            "home_team",
            "hometeam",
            "homeTeam",
            "team1",
            "team_1",
            "hteam",
            "homeName",
            "home_name"
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
            "away_name"
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
# MATCH EXTRACTION
# =========================================================

def extract_matches(js):

    text = _clean_js(js)

    objects = _extract_json_objects(text)

    results = []

    seen = set()


    for obj in objects:

        for item in _flatten(obj):

            if not isinstance(item, dict):
                continue


            score = _find_score(item)

            odds = _find_odds(item)


            if score is None:
                continue

            if odds is None:
                continue


            home_score, away_score = score

            home_odds, draw_odds, away_odds = odds


            if home_score > away_score:
                result = "H"

            elif home_score < away_score:
                result = "A"

            else:
                result = "D"


            home_team = _find_team(
                item,
                True
            )

            away_team = _find_team(
                item,
                False
            )


            key = (
                home_team,
                away_team,
                home_score,
                away_score,
                round(home_odds, 4),
                round(draw_odds, 4),
                round(away_odds, 4)
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
                        100 / home_odds,
                        4
                    ),

                "draw_probability":
                    round(
                        100 / draw_odds,
                        4
                    ),

                "away_probability":
                    round(
                        100 / away_odds,
                        4
                    )
            })


    return results


# =========================================================
# SAVE DAY
# =========================================================

def collect_day(
    target_date,
    cid=""
):

    try:

        js = download_day(
            target_date,
            cid
        )

        rows = extract_matches(js)

        saved = 0


        for row in rows:

            match_key = "|".join([

                _date_string(target_date),

                row["home_team"],

                row["away_team"],

                str(row["home_score"]),

                str(row["away_score"]),

                f"{row['home_odds']:.4f}",

                f"{row['draw_odds']:.4f}",

                f"{row['away_odds']:.4f}",

                row["result"]
            ])


            value = database.save_match({

                "match_key":
                    match_key,

                "match_date":
                    _date_string(
                        target_date
                    ),

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
                    "7M"
            })


            saved += int(value or 0)


        database.save_collection_day(
            target_date,
            "success",
            len(rows),
            saved
        )


        return {
            "success": True,
            "found": len(rows),
            "saved": saved,
            "error": None
        }


    except Exception as error:

        database.save_collection_day(
            target_date,
            "failed",
            0,
            0,
            str(error)
        )

        raise


# =========================================================
# DIAGNOSIS
# =========================================================

def diagnose(
    target_date,
    cid=""
):

    try:

        html = download_result_page(
            target_date,
            cid
        )

        js = download_day(
            target_date,
            cid
        )

        rows = extract_matches(js)


        return {

            "status": 200,

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
                js[:30000]
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
                str(error)
            }
