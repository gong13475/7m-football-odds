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

    "User-Agent":
        (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/131.0 Safari/537.36"
        ),

    "Accept":
        "*/*",

    "Accept-Language":
        "ko-KR,ko;q=0.9",

    "Referer":
        "https://1x2.7mkr.com/"
}


SESSION = requests.Session()

SESSION.headers.update(
    HEADERS
)


def _date_string(target_date):

    if isinstance(
        target_date,
        date
    ):

        return target_date.strftime(
            "%Y-%m-%d"
        )

    return str(
        target_date
    )


def download_result_page(
    target_date,
    cid=""
):

    dt = _date_string(
        target_date
    )

    params = {
        "dt": dt
    }

    if cid:

        params["cid"] = cid


    response = SESSION.get(
        BASE_URL,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    response.encoding = (
        response.apparent_encoding
        or "utf-8"
    )

    return response.text


def download_day(
    target_date,
    cid=""
):

    dt = _date_string(
        target_date
    )

    filename = (
        str(cid)
        if cid
        else "index"
    )

    url = (
        f"{DATA_BASE}/"
        f"{dt}/"
        f"{filename}.js"
    )

    response = SESSION.get(
        url,
        timeout=30,
        headers=HEADERS
    )

    response.raise_for_status()

    response.encoding = (
        response.apparent_encoding
        or "utf-8"
    )

    text = response.text

    if not text.strip():

        raise ValueError(
            "7M 서버가 빈 데이터를 반환했습니다."
        )

    return text


def _clean_js(text):

    text = re.sub(
        r"^\s*//.*?$",
        "",
        text,
        flags=re.MULTILINE
    )

    return text.strip()


def _extract_json_objects(text):

    objects = []

    decoder = json.JSONDecoder()

    for match in re.finditer(
        r"[\[{]",
        text
    ):

        start = match.start()

        try:

            obj, end = decoder.raw_decode(
                text[start:]
            )

            objects.append(obj)

        except Exception:

            continue

    return objects


def _flatten(obj):

    if isinstance(
        obj,
        dict
    ):

        yield obj

        for value in obj.values():

            yield from _flatten(
                value
            )

    elif isinstance(
        obj,
        list
    ):

        for value in obj:

            yield from _flatten(
                value
            )


def _number(value):

    try:

        return float(
            str(value)
            .strip()
            .replace(",", "")
        )

    except Exception:

        return None


def _find_score(item):

    score_keys = [

        "score",
        "result",
        "ft",
        "fulltime",
        "final",
        "sc",

    ]


    for key in score_keys:

        value = item.get(
            key
        )

        if not isinstance(
            value,
            str
        ):

            continue


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
        "hscore",
        "hs"
    ]:

        if key in item:

            home_score = _number(
                item[key]
            )

            break


    for key in [
        "away_score",
        "awayscore",
        "ascore",
        "as"
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


def _find_odds(item):

    candidates = []


    keys = [
        "home",
        "draw",
        "away",
        "win",
        "lose",
        "h",
        "d",
        "a",
        "odds1",
        "odds2",
        "odds3",
        "homeodds",
        "drawodds",
        "awayodds",
        "final_home",
        "final_draw",
        "final_away"
    ]


    for key in keys:

        if key in item:

            value = _number(
                item[key]
            )

            if (
                value is not None
                and 1.0 < value <= 100
            ):

                candidates.append(
                    value
                )


    if len(candidates) >= 3:

        return tuple(
            candidates[:3]
        )


    # 배열형 배당
    for key, value in item.items():

        if not isinstance(
            value,
            (list, tuple)
        ):

            continue

        nums = []

        for x in value:

            n = _number(x)

            if (
                n is not None
                and 1.0 < n <= 100
            ):

                nums.append(n)


        if len(nums) >= 3:

            return tuple(
                nums[:3]
            )


    return None


def _find_team(
    item,
    home=True
):

    if home:

        keys = [
            "home_team",
            "hometeam",
            "home",
            "team1",
            "team_1",
            "hteam"
        ]

    else:

        keys = [
            "away_team",
            "awayteam",
            "away",
            "team2",
            "team_2",
            "ateam"
        ]


    for key in keys:

        value = item.get(
            key
        )

        if (
            isinstance(
                value,
                str
            )
            and value.strip()
        ):

            return value.strip()


    return ""


def extract_matches(js):

    """
    7M JS 구조가 JSON 형태로 노출되는 경우를
    우선 안전하게 탐색한다.

    구조가 다른 경우에는 발견 0건으로 처리하여
    잘못된 배당을 임의로 저장하지 않는다.
    """

    text = _clean_js(
        js
    )

    objects = _extract_json_objects(
        text
    )

    results = []

    seen = set()


    for obj in objects:

        for item in _flatten(obj):

            if not isinstance(
                item,
                dict
            ):

                continue


            score = _find_score(
                item
            )

            odds = _find_odds(
                item
            )


            if (
                score is None
                or odds is None
            ):

                continue


            home_score, away_score = (
                score
            )


            home_odds, draw_odds, away_odds = (
                odds
            )


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


            hp = round(
                100 / home_odds,
                4
            )

            dp = round(
                100 / draw_odds,
                4
            )

            ap = round(
                100 / away_odds,
                4
            )


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
                    hp,

                "draw_probability":
                    dp,

                "away_probability":
                    ap
            })


    return results


def collect_day(
    target_date,
    cid=""
):

    try:

        js = download_day(
            target_date,
            cid
        )

        rows = extract_matches(
            js
        )

        saved = 0


        for row in rows:

            match_key = "|".join([

                _date_string(
                    target_date
                ),

                row.get(
                    "home_team",
                    ""
                ),

                row.get(
                    "away_team",
                    ""
                ),

                str(
                    row[
                        "home_score"
                    ]
                ),

                str(
                    row[
                        "away_score"
                    ]
                ),

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
                    row[
                        "home_team"
                    ],

                "away_team":
                    row[
                        "away_team"
                    ],

                "home_score":
                    row[
                        "home_score"
                    ],

                "away_score":
                    row[
                        "away_score"
                    ],

                "result":
                    row[
                        "result"
                    ],

                "home_odds":
                    row[
                        "home_odds"
                    ],

                "draw_odds":
                    row[
                        "draw_odds"
                    ],

                "away_odds":
                    row[
                        "away_odds"
                    ],

                "home_probability":
                    row[
                        "home_probability"
                    ],

                "draw_probability":
                    row[
                        "draw_probability"
                    ],

                "away_probability":
                    row[
                        "away_probability"
                    ],

                "source":
                    "7M"
            })


            saved += int(
                value or 0
            )


        database.save_collection_day(
            target_date,
            "success",
            len(rows),
            saved
        )


        return {

            "success":
                True,

            "found":
                len(rows),

            "saved":
                saved,

            "error":
                None
        }


    except Exception as error:

        database.save_collection_day(
            target_date,
            "failed",
            0,
            0,
            str(error)
        )


        return {

            "success":
                False,

            "found":
                0,

            "saved":
                0,

            "error":
                str(error)
        }


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

            "has_result":
                "result" in html.lower(),

            "has_compare":
                "비교" in html,

            "found":
                len(rows),

            "html":
                html[:5000],

            "js":
                js[:20000]
        }


    except Exception as error:

        return {

            "status":
                0,

            "size":
                0,

            "html_size":
                0,

            "has_result":
                False,

            "has_compare":
                False,

            "found":
                0,

            "html":
                "",

            "js":
                "",

            "error":
                str(error)
        }
