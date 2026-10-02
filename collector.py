# collector.py
# -*- coding: utf-8 -*-

import re
import json
import time
import sqlite3
import threading

from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlencode


# ============================================================
# CONFIG
# ============================================================

DB_PATH = Path("odds.db")

_db_lock = threading.RLock()


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": (
        "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Connection": "keep-alive",
}


# 현재 확인되는 7M 계열 주소를 우선순위로 둔다.
BASE_URLS = [
    "https://kr.7msport.com/",
    "https://kr.7msport.com/default_kr.aspx",
    "https://live.7mkr2.com/",
    "https://live7.7mkr.com/index.shtml",
]


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=60,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=60000")

    return conn


def init_db():

    with _db_lock:

        conn = get_connection()

        try:

            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS matches (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    match_key TEXT NOT NULL UNIQUE,

                    match_date TEXT NOT NULL,

                    league TEXT DEFAULT '',

                    home_team TEXT DEFAULT '',
                    away_team TEXT DEFAULT '',

                    home_score INTEGER,
                    away_score INTEGER,

                    result TEXT NOT NULL,

                    home_odds REAL NOT NULL,
                    draw_odds REAL NOT NULL,
                    away_odds REAL NOT NULL,

                    home_probability REAL NOT NULL,
                    draw_probability REAL NOT NULL,
                    away_probability REAL NOT NULL,

                    source TEXT DEFAULT '',

                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS
                idx_matches_date
                ON matches(match_date);

                CREATE INDEX IF NOT EXISTS
                idx_matches_odds
                ON matches(
                    home_odds,
                    draw_odds,
                    away_odds
                );

                CREATE INDEX IF NOT EXISTS
                idx_matches_result
                ON matches(result);


                CREATE TABLE IF NOT EXISTS collection_days (

                    match_date TEXT PRIMARY KEY,

                    status TEXT NOT NULL,

                    found INTEGER DEFAULT 0,

                    saved INTEGER DEFAULT 0,

                    error TEXT DEFAULT '',

                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );


                CREATE TABLE IF NOT EXISTS collection_state (

                    id INTEGER PRIMARY KEY CHECK(id = 1),

                    start_date TEXT,

                    end_date TEXT,

                    last_completed_date TEXT,

                    running INTEGER DEFAULT 0,

                    stopped INTEGER DEFAULT 0,

                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );


                CREATE TABLE IF NOT EXISTS collection_logs (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                    level TEXT DEFAULT 'INFO',

                    message TEXT NOT NULL
                );
                """
            )

            conn.commit()

        finally:

            conn.close()


# ============================================================
# LOG
# ============================================================

def add_log(message, level="INFO"):

    with _db_lock:

        conn = get_connection()

        try:

            conn.execute(
                """
                INSERT INTO collection_logs (
                    level,
                    message
                )
                VALUES (?, ?)
                """,
                (
                    str(level),
                    str(message)
                )
            )

            conn.commit()

        finally:

            conn.close()


def get_logs(limit=500):

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT
                created_at,
                level,
                message
            FROM collection_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),)
        ).fetchall()

        rows = list(reversed(rows))

        return "\n".join(
            f"[{row['created_at']}] "
            f"[{row['level']}] "
            f"{row['message']}"
            for row in rows
        )

    finally:

        conn.close()


# ============================================================
# HTTP
# ============================================================

def fetch_response(url, timeout=30):

    request = Request(
        url,
        headers=DEFAULT_HEADERS
    )

    response = urlopen(
        request,
        timeout=timeout
    )

    raw = response.read()

    charset = response.headers.get_content_charset()

    if charset:

        try:
            text = raw.decode(
                charset,
                errors="ignore"
            )
        except Exception:
            text = raw.decode(
                "utf-8",
                errors="ignore"
            )

    else:

        text = raw.decode(
            "utf-8",
            errors="ignore"
        )

    return {
        "status": getattr(
            response,
            "status",
            200
        ),
        "url": getattr(
            response,
            "url",
            url
        ),
        "text": text,
        "headers": response.headers
    }


def fetch_url(url, timeout=30):

    return fetch_response(
        url,
        timeout
    )["text"]


# ============================================================
# DATE
# ============================================================

def normalize_date(value):

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()

    if not text:
        return None

    text = text.replace(
        ".",
        "-"
    )

    text = text.replace(
        "/",
        "-"
    )

    # YYYY-MM-DD
    match = re.search(
        r"(20\d{2})-(\d{1,2})-(\d{1,2})",
        text
    )

    if match:

        try:

            return date(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3))
            )

        except ValueError:
            pass

    # YYYYMMDD
    match = re.search(
        r"\b(20\d{2})(\d{2})(\d{2})\b",
        text
    )

    if match:

        try:

            return date(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3))
            )

        except ValueError:
            pass

    return None


def parse_match_datetime(value):

    if not value:
        return None

    text = str(value).strip()

    # 2026,10,01,13,00,00
    nums = re.findall(
        r"\d+",
        text
    )

    if len(nums) >= 6:

        try:

            y = int(nums[0])
            m = int(nums[1])
            d = int(nums[2])
            hh = int(nums[3])
            mm = int(nums[4])
            ss = int(nums[5])

            if 2000 <= y <= 2100:

                return datetime(
                    y,
                    m,
                    d,
                    hh,
                    mm,
                    ss
                )

        except ValueError:
            pass

    # ISO
    try:

        return datetime.fromisoformat(
            text.replace(
                "Z",
                ""
            )
        )

    except Exception:
        pass

    return None


# ============================================================
# RESULT
# ============================================================

def get_result(
    home_score,
    away_score
):

    try:

        h = int(home_score)
        a = int(away_score)

    except (
        TypeError,
        ValueError
    ):

        return "D"

    if h > a:
        return "H"

    if h < a:
        return "A"

    return "D"


# ============================================================
# ODDS
# ============================================================

def valid_odds(value):

    try:

        n = float(value)

        return (
            n > 1.0
            and n < 1000.0
        )

    except (
        TypeError,
        ValueError
    ):

        return False


def parse_odds(value):

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # HTML entity / 공백 제거
    text = re.sub(
        r"&nbsp;",
        "",
        text,
        flags=re.I
    )

    text = text.replace(
        ",",
        "."
    )

    match = re.search(
        r"\d+(?:\.\d+)?",
        text
    )

    if not match:
        return None

    try:

        value = float(
            match.group(0)
        )

    except ValueError:
        return None

    if not valid_odds(value):
        return None

    return value


# ============================================================
# JS SCRIPT EXTRACTION
# ============================================================

def extract_scripts(html):

    if not html:
        return []

    scripts = re.findall(
        r"<script\b[^>]*>([\s\S]*?)</script>",
        html,
        flags=re.I
    )

    results = []

    for script in scripts:

        script = script.strip()

        if script:
            results.append(script)

    return results


def extract_external_scripts(
    html,
    base_url
):

    if not html:
        return []

    results = []

    matches = re.findall(
        r'<script[^>]+src=["\']([^"\']+)["\']',
        html,
        flags=re.I
    )

    for src in matches:

        url = urljoin(
            base_url,
            src
        )

        results.append(url)

    return list(
        dict.fromkeys(results)
    )


def fetch_external_scripts(
    html,
    base_url,
    limit=15
):

    results = []

    urls = extract_external_scripts(
        html,
        base_url
    )

    for url in urls[:limit]:

        try:

            text = fetch_url(
                url,
                timeout=20
            )

            results.append({
                "url": url,
                "text": text
            })

        except Exception as exc:

            add_log(
                f"JS 요청 실패: {url} / {exc}",
                "WARNING"
            )

    return results


# ============================================================
# JS DATA SEARCH
# ============================================================

def find_date_patterns(text):

    if not text:
        return []

    patterns = [

        r"20\d{2}[,\-/]\d{1,2}[,\-/]\d{1,2}",

        r"20\d{2}\d{2}\d{2}",

        r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}",

    ]

    found = []

    for pattern in patterns:

        found.extend(
            re.findall(
                pattern,
                text
            )
        )

    return list(
        dict.fromkeys(found)
    )


def find_dt_blocks(text):

    """
    기존 dt 방식 + 흔히 사용되는
    data / match / list 배열 변수까지 찾는다.
    """

    if not text:
        return []

    patterns = [

        r"\bvar\s+dt\s*=\s*(\[[\s\S]*?\])\s*;",

        r"\blet\s+dt\s*=\s*(\[[\s\S]*?\])\s*;",

        r"\bconst\s+dt\s*=\s*(\[[\s\S]*?\])\s*;",

        r"\bdt\s*=\s*(\[[\s\S]*?\])\s*;",

        r"\bvar\s+data\s*=\s*(\[[\s\S]*?\])\s*;",

        r"\bvar\s+matchList\s*=\s*(\[[\s\S]*?\])\s*;",

        r"\bvar\s+matchData\s*=\s*(\[[\s\S]*?\])\s*;",

        r"\bvar\s+games\s*=\s*(\[[\s\S]*?\])\s*;",

    ]

    blocks = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.I
        )

        blocks.extend(
            matches
        )

    return blocks


# ============================================================
# JS ARRAY STRING SPLITTER
# ============================================================

def split_js_array_strings(
    array_text
):

    if not array_text:
        return []

    text = array_text.strip()

    if text.startswith("["):
        text = text[1:]

    if text.endswith("]"):
        text = text[:-1]

    results = []

    current = []

    quote = None
    escaped = False

    depth = 0

    for char in text:

        if escaped:

            current.append(char)
            escaped = False
            continue

        if quote:

            if char == "\\":
                escaped = True
                continue

            if char == quote:
                quote = None
                continue

            current.append(char)
            continue

        if char in (
            '"',
            "'"
        ):

            quote = char
            continue

        if char in (
            "[",
            "{"
        ):

            depth += 1

        elif char in (
            "]",
            "}"
        ):

            depth = max(
                0,
                depth - 1
            )

        if char == "," and depth == 0:

            value = "".join(
                current
            ).strip()

            if value:
                results.append(value)

            current = []

            continue

        current.append(char)

    value = "".join(
        current
    ).strip()

    if value:
        results.append(value)

    return results


# ============================================================
# ORIGINAL 7M DT PARSER
# ============================================================

def extract_dt_block(html):

    blocks = find_dt_blocks(
        html
    )

    if blocks:
        return blocks[0]

    return None


def parse_dt_row(raw):

    if not raw:
        return None

    raw = str(raw).strip()

    # JSON object일 경우 별도 처리
    if raw.startswith("{"):

        try:

            obj = json.loads(raw)

            return parse_object_row(
                obj
            )

        except Exception:
            pass

    parts = raw.split("|")

    if len(parts) < 14:
        return None

    try:

        match_id = parts[0].strip()

        dt_value = parts[1].strip()

        cid = parts[2].strip()

        league = parts[3].strip()

        home_id = parts[4].strip()

        away_id = parts[5].strip()

        home_team = parts[6].strip()

        away_team = parts[7].strip()

        home_score = parts[8].strip()

        away_score = parts[9].strip()

        half_score = parts[10].strip()

    except Exception:

        return None

    match_datetime = parse_match_datetime(
        dt_value
    )

    if not match_datetime:
        return None

    first_home = parse_odds(
        parts[11]
    )

    first_draw = parse_odds(
        parts[12]
    )

    first_away = parse_odds(
        parts[13]
    )

    final_home = (
        parse_odds(parts[14])
        if len(parts) > 14
        else None
    )

    final_draw = (
        parse_odds(parts[15])
        if len(parts) > 15
        else None
    )

    final_away = (
        parse_odds(parts[16])
        if len(parts) > 16
        else None
    )

    home_odds = (
        final_home
        if final_home is not None
        else first_home
    )

    draw_odds = (
        final_draw
        if final_draw is not None
        else first_draw
    )

    away_odds = (
        final_away
        if final_away is not None
        else first_away
    )

    if not (
        valid_odds(home_odds)
        and valid_odds(draw_odds)
        and valid_odds(away_odds)
    ):
        return None

    try:

        hs = int(
            home_score
        )

        aws = int(
            away_score
        )

    except (
        TypeError,
        ValueError
    ):

        return None

    return make_row(
        match_id=match_id,
        match_datetime=match_datetime,
        league=league,
        cid=cid,
        home_id=home_id,
        away_id=away_id,
        home_team=home_team,
        away_team=away_team,
        home_score=hs,
        away_score=aws,
        half_score=half_score,
        home_odds=home_odds,
        draw_odds=draw_odds,
        away_odds=away_odds
    )


# ============================================================
# OBJECT PARSER
# ============================================================

def get_obj(
    obj,
    *names
):

    if not isinstance(
        obj,
        dict
    ):
        return None

    lower = {
        str(k).lower(): v
        for k, v in obj.items()
    }

    for name in names:

        key = str(name).lower()

        if key in lower:
            return lower[key]

    return None


def parse_object_row(obj):

    if not isinstance(
        obj,
        dict
    ):
        return None

    match_id = get_obj(
        obj,
        "match_id",
        "matchid",
        "id",
        "gid",
        "gameid"
    )

    dt_value = get_obj(
        obj,
        "match_datetime",
        "matchdate",
        "date",
        "datetime",
        "time",
        "matchtime"
    )

    home_team = get_obj(
        obj,
        "home_team",
        "hometeam",
        "home",
        "homeName"
    )

    away_team = get_obj(
        obj,
        "away_team",
        "awayteam",
        "away",
        "awayName"
    )

    if not home_team or not away_team:
        return None

    match_datetime = parse_match_datetime(
        dt_value
    )

    if not match_datetime:

        target = normalize_date(
            dt_value
        )

        if target:

            match_datetime = datetime.combine(
                target,
                datetime.min.time()
            )

    if not match_datetime:
        return None

    home_score = get_obj(
        obj,
        "home_score",
        "homescore",
        "scorehome",
        "homeScore"
    )

    away_score = get_obj(
        obj,
        "away_score",
        "awayscore",
        "scoreaway",
        "awayScore"
    )

    try:

        home_score = int(
            home_score
        )

        away_score = int(
            away_score
        )

    except (
        TypeError,
        ValueError
    ):

        return None

    home_odds = get_obj(
        obj,
        "home_odds",
        "homeodds",
        "odds1",
        "win",
        "winodds",
        "homeOdds"
    )

    draw_odds = get_obj(
        obj,
        "draw_odds",
        "drawodds",
        "oddsx",
        "draw",
        "drawOdds"
    )

    away_odds = get_obj(
        obj,
        "away_odds",
        "awayodds",
        "odds2",
        "lose",
        "loseodds",
        "awayOdds"
    )

    home_odds = parse_odds(
        home_odds
    )

    draw_odds = parse_odds(
        draw_odds
    )

    away_odds = parse_odds(
        away_odds
    )

    if not (
        home_odds
        and draw_odds
        and away_odds
    ):
        return None

    return make_row(
        match_id=(
            match_id
            or f"{home_team}|{away_team}|"
            f"{match_datetime}"
        ),
        match_datetime=match_datetime,
        league=str(
            get_obj(
                obj,
                "league",
                "leagueName",
                "competition"
            )
            or ""
        ),
        cid=str(
            get_obj(
                obj,
                "cid",
                "company",
                "companyid"
            )
            or ""
        ),
        home_id=str(
            get_obj(
                obj,
                "home_id",
                "homeid"
            )
            or ""
        ),
        away_id=str(
            get_obj(
                obj,
                "away_id",
                "awayid"
            )
            or ""
        ),
        home_team=str(
            home_team
        ),
        away_team=str(
            away_team
        ),
        home_score=home_score,
        away_score=away_score,
        half_score="",
        home_odds=home_odds,
        draw_odds=draw_odds,
        away_odds=away_odds
    )


# ============================================================
# MAKE ROW
# ============================================================

def make_row(
    match_id,
    match_datetime,
    league,
    cid,
    home_id,
    away_id,
    home_team,
    away_team,
    home_score,
    away_score,
    half_score,
    home_odds,
    draw_odds,
    away_odds
):

    result = get_result(
        home_score,
        away_score
    )

    return {

        "match_id":
            str(match_id),

        "match_key":
            str(match_id),

        "match_datetime":
            match_datetime,

        "match_date":
            match_datetime.date().isoformat(),

        "league":
            str(league or ""),

        "cid":
            str(cid or ""),

        "home_id":
            str(home_id or ""),

        "away_id":
            str(away_id or ""),

        "home_team":
            str(home_team or ""),

        "away_team":
            str(away_team or ""),

        "home_score":
            int(home_score),

        "away_score":
            int(away_score),

        "half_score":
            str(half_score or ""),

        "result":
            result,

        "home_odds":
            float(home_odds),

        "draw_odds":
            float(draw_odds),

        "away_odds":
            float(away_odds),

        "home_probability":
            1.0 / float(home_odds),

        "draw_probability":
            1.0 / float(draw_odds),

        "away_probability":
            1.0 / float(away_odds),

        "source":
            "7M"
    }


# ============================================================
# GENERIC JSON PARSER
# ============================================================

def parse_json_candidates(
    text
):

    results = []

    if not text:
        return results

    # 전체 JSON 시도
    candidates = []

    stripped = text.strip()

    if stripped.startswith("["):
        candidates.append(
            stripped
        )

    if stripped.startswith("{"):
        candidates.append(
            stripped
        )

    # JS 내부 JSON 배열 후보
    candidates.extend(
        re.findall(
            r"(\[[\s\S]{50,}?\])",
            text
        )[:30]
    )

    for candidate in candidates:

        try:

            data = json.loads(
                candidate
            )

        except Exception:
            continue

        stack = [data]

        while stack:

            item = stack.pop()

            if isinstance(
                item,
                dict
            ):

                row = parse_object_row(
                    item
                )

                if row:
                    results.append(
                        row
                    )

                for value in item.values():

                    if isinstance(
                        value,
                        (
                            dict,
                            list
                        )
                    ):

                        stack.append(
                            value
                        )

            elif isinstance(
                item,
                list
            ):

                for value in item:

                    if isinstance(
                        value,
                        (
                            dict,
                            list
                        )
                    ):

                        stack.append(
                            value
                        )

    return results


# ============================================================
# HTML PARSER
# ============================================================

def parse_dt_from_html(
    html
):

    if not html:
        return []

    all_rows = []

    # --------------------------------------------------------
    # 1. dt 배열
    # --------------------------------------------------------

    blocks = find_dt_blocks(
        html
    )

    for block in blocks:

        raw_rows = split_js_array_strings(
            block
        )

        for raw in raw_rows:

            try:

                row = parse_dt_row(
                    raw
                )

                if row:
                    all_rows.append(
                        row
                    )

            except Exception as exc:

                add_log(
                    f"dt 행 파싱 오류: {exc}",
                    "WARNING"
                )

    # --------------------------------------------------------
    # 2. JSON 객체 구조
    # --------------------------------------------------------

    all_rows.extend(
        parse_json_candidates(
            html
        )
    )

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

    unique = {}

    for row in all_rows:

        key = (
            row.get("match_key")
            or "|".join([
                row.get("match_date", ""),
                row.get("home_team", ""),
                row.get("away_team", "")
            ])
        )

        unique[key] = row

    return list(
        unique.values()
    )


# ============================================================
# DATE FILTER
# ============================================================

def filter_matches_by_date(
    rows,
    target_date
):

    target = normalize_date(
        target_date
    )

    if not target:
        return []

    results = []

    for row in rows:

        row_date = normalize_date(
            row.get("match_date")
        )

        if row_date == target:

            results.append(
                row
            )

    return results


# ============================================================
# SAVE
# ============================================================

def save_match(row):

    match_key = row.get(
        "match_key"
    )

    if not match_key:

        match_key = "|".join([
            str(row.get("match_date", "")),
            str(row.get("home_team", "")),
            str(row.get("away_team", "")),
            str(row.get("home_score", "")),
            str(row.get("away_score", "")),
            f"{float(row['home_odds']):.4f}",
            f"{float(row['draw_odds']):.4f}",
            f"{float(row['away_odds']):.4f}",
        ])

    with _db_lock:

        conn = get_connection()

        try:

            cur = conn.execute(
                """
                INSERT OR IGNORE INTO matches (

                    match_key,
                    match_date,
                    league,
                    home_team,
                    away_team,
                    home_score,
                    away_score,
                    result,
                    home_odds,
                    draw_odds,
                    away_odds,
                    home_probability,
                    draw_probability,
                    away_probability,
                    source

                )

                VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
                """,
                (
                    match_key,
                    row.get(
                        "match_date",
                        ""
                    ),
                    row.get(
                        "league",
                        ""
                    ),
                    row.get(
                        "home_team",
                        ""
                    ),
                    row.get(
                        "away_team",
                        ""
                    ),
                    row.get(
                        "home_score"
                    ),
                    row.get(
                        "away_score"
                    ),
                    row.get(
                        "result",
                        "D"
                    ),
                    float(
                        row["home_odds"]
                    ),
                    float(
                        row["draw_odds"]
                    ),
                    float(
                        row["away_odds"]
                    ),
                    float(
                        row["home_probability"]
                    ),
                    float(
                        row["draw_probability"]
                    ),
                    float(
                        row["away_probability"]
                    ),
                    row.get(
                        "source",
                        "7M"
                    )
                )
            )

            conn.commit()

            return cur.rowcount

        finally:

            conn.close()


# ============================================================
# QUERY
# ============================================================

def get_match_count():

    conn = get_connection()

    try:

        return conn.execute(
            "SELECT COUNT(*) FROM matches"
        ).fetchone()[0]

    finally:

        conn.close()


def get_odds_count():

    return get_match_count()


def get_all_matches():

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT *
            FROM matches
            ORDER BY match_date DESC, id DESC
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


def get_all_odds():

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT
                match_key,
                match_date,
                home_team,
                away_team,
                home_odds AS final_home,
                draw_odds AS final_draw,
                away_odds AS final_away,
                result
            FROM matches
            ORDER BY match_date DESC, id DESC
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


def get_company_names():

    if get_match_count():
        return ["7M"]

    return []


def get_company_counts():

    count = get_match_count()

    if not count:
        return {}

    return {
        "7M": count
    }


def get_same_odds(
    home_odds,
    draw_odds,
    away_odds,
    tolerance=0.00001
):

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT *
            FROM matches

            WHERE ABS(home_odds - ?) < ?
              AND ABS(draw_odds - ?) < ?
              AND ABS(away_odds - ?) < ?

            ORDER BY match_date DESC, id DESC
            """,
            (
                float(home_odds),
                tolerance,
                float(draw_odds),
                tolerance,
                float(away_odds),
                tolerance
            )
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# COLLECTION DAY
# ============================================================

def save_collection_day(
    target_date,
    status,
    found=0,
    saved=0,
    error=""
):

    with _db_lock:

        conn = get_connection()

        try:

            conn.execute(
                """
                INSERT INTO collection_days (
                    match_date,
                    status,
                    found,
                    saved,
                    error,
                    updated_at
                )

                VALUES (
                    ?, ?, ?, ?, ?,
                    CURRENT_TIMESTAMP
                )

                ON CONFLICT(match_date)
                DO UPDATE SET

                    status=excluded.status,
                    found=excluded.found,
                    saved=excluded.saved,
                    error=excluded.error,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    target_date.isoformat()
                    if hasattr(
                        target_date,
                        "isoformat"
                    )
                    else str(target_date),
                    status,
                    int(found),
                    int(saved),
                    str(error or "")
                )
            )

            conn.commit()

        finally:

            conn.close()


# ============================================================
# COLLECTION STATE
# ============================================================

def save_collection_state(
    start_date=None,
    end_date=None,
    last_completed_date=None,
    running=False,
    stopped=False
):

    with _db_lock:

        conn = get_connection()

        try:

            conn.execute(
                """
                INSERT INTO collection_state (
                    id,
                    start_date,
                    end_date,
                    last_completed_date,
                    running,
                    stopped
                )

                VALUES (
                    1, ?, ?, ?, ?, ?
                )

                ON CONFLICT(id)
                DO UPDATE SET

                    start_date=
                        excluded.start_date,

                    end_date=
                        excluded.end_date,

                    last_completed_date=
                        excluded.last_completed_date,

                    running=
                        excluded.running,

                    stopped=
                        excluded.stopped,

                    updated_at=
                        CURRENT_TIMESTAMP
                """,
                (
                    str(start_date)
                    if start_date
                    else None,
                    str(end_date)
                    if end_date
                    else None,
                    str(last_completed_date)
                    if last_completed_date
                    else None,
                    int(bool(running)),
                    int(bool(stopped))
                )
            )

            conn.commit()

        finally:

            conn.close()


def get_collection_state():

    conn = get_connection()

    try:

        row = conn.execute(
            """
            SELECT *
            FROM collection_state
            WHERE id = 1
            """
        ).fetchone()

        if row:
            return dict(row)

        return {}

    finally:

        conn.close()


# ============================================================
# BUILD URL
# ============================================================

def build_url(
    target_date,
    cid=""
):

    target = normalize_date(
        target_date
    )

    if not target:
        raise ValueError(
            "잘못된 날짜"
        )

    date_text = target.strftime(
        "%Y-%m-%d"
    )

    # 우선 한국 7M 결과 페이지
    base = (
        "https://kr.7msport.com/"
        "default_kr.aspx"
    )

    params = {
        "classid": "2",
        "line": "no"
    }

    # CID가 있으면 추가
    if cid:

        params["cid"] = str(
            cid
        )

    return (
        base
        + "?"
        + urlencode(params)
    )


# ============================================================
# COLLECT DAY
# ============================================================

def collect_day(
    target_date,
    cid=""
):

    target = normalize_date(
        target_date
    )

    if not target:

        raise ValueError(
            "잘못된 수집 날짜"
        )

    url = build_url(
        target,
        cid
    )

    add_log(
        f"{target} 수집 요청: {url}"
    )

    # --------------------------------------------------------
    # 1. HTML
    # --------------------------------------------------------

    response = fetch_response(
        url,
        timeout=40
    )

    html = response["text"]

    add_log(
        f"{target}: HTTP "
        f"{response['status']} / "
        f"HTML {len(html):,}"
    )

    # --------------------------------------------------------
    # 2. HTML 자체 파싱
    # --------------------------------------------------------

    rows = parse_dt_from_html(
        html
    )

    # --------------------------------------------------------
    # 3. 외부 JS까지 검색
    # --------------------------------------------------------

    if not rows:

        scripts = fetch_external_scripts(
            html,
            response["url"],
            limit=20
        )

        add_log(
            f"{target}: 외부 JS "
            f"{len(scripts)}개 검사"
        )

        for script in scripts:

            text = script["text"]

            # dt
            script_rows = parse_dt_from_html(
                text
            )

            if script_rows:
                rows.extend(
                    script_rows
                )

            # JSON
            if not script_rows:

                rows.extend(
                    parse_json_candidates(
                        text
                    )
                )

            if rows:
                break

    # --------------------------------------------------------
    # 4. 날짜 필터
    # --------------------------------------------------------

    rows = filter_matches_by_date(
        rows,
        target
    )

    # --------------------------------------------------------
    # 5. 중복 제거
    # --------------------------------------------------------

    unique = {}

    for row in rows:

        key = row.get(
            "match_key"
        )

        if key:
            unique[key] = row

    rows = list(
        unique.values()
    )

    found = len(rows)

    saved = 0

    # --------------------------------------------------------
    # 6. 저장
    # --------------------------------------------------------

    for row in rows:

        try:

            saved += save_match(
                row
            )

        except Exception as exc:

            add_log(
                f"{target}: 경기 저장 실패 "
                f"{row.get('match_id')}: {exc}",
                "ERROR"
            )

    save_collection_day(
        target,
        "DONE",
        found,
        saved,
        ""
    )

    add_log(
        f"{target}: 발견 {found}건 / "
        f"신규 저장 {saved}건"
    )

    return {
        "found": found,
        "saved": saved,
        "rows": rows
    }


# ============================================================
# URL COLLECTION
# ============================================================

def collect_url(
    url,
    target_date=None
):

    add_log(
        f"7M 요청: {url}"
    )

    response = fetch_response(
        url
    )

    html = response["text"]

    add_log(
        f"HTTP {response['status']} / "
        f"HTML {len(html):,}"
    )

    rows = parse_dt_from_html(
        html
    )

    if not rows:

        scripts = fetch_external_scripts(
            html,
            response["url"],
            limit=20
        )

        for script in scripts:

            rows.extend(
                parse_dt_from_html(
                    script["text"]
                )
            )

            if not rows:

                rows.extend(
                    parse_json_candidates(
                        script["text"]
                    )
                )

            if rows:
                break

    if target_date is not None:

        rows = filter_matches_by_date(
            rows,
            target_date
        )

    unique = {}

    for row in rows:

        unique[
            row["match_key"]
        ] = row

    rows = list(
        unique.values()
    )

    saved = 0

    for row in rows:

        saved += save_match(
            row
        )

    return {
        "found": len(rows),
        "saved": saved,
        "rows": rows
    }


# ============================================================
# RANGE
# ============================================================

def date_range(
    start_date,
    end_date
):

    current = normalize_date(
        start_date
    )

    end = normalize_date(
        end_date
    )

    if not current or not end:
        return

    while current <= end:

        yield current

        current += timedelta(
            days=1
        )


def collect_range(
    start_date,
    end_date,
    url=None,
    retry_count=2,
    retry_delay=1.0,
    stop_event=None
):

    start = normalize_date(
        start_date
    )

    end = normalize_date(
        end_date
    )

    if not start or not end:

        raise ValueError(
            "잘못된 날짜"
        )

    if start > end:

        raise ValueError(
            "시작 날짜가 종료 날짜보다 늦습니다."
        )

    total_found = 0
    total_saved = 0

    save_collection_state(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        last_completed_date=None,
        running=True,
        stopped=False
    )

    stopped = False

    try:

        for target in date_range(
            start,
            end
        ):

            if stop_event:

                if stop_event.is_set():

                    stopped = True

                    add_log(
                        "수집 중지 요청",
                        "WARNING"
                    )

                    break

            save_collection_day(
                target,
                "RUNNING",
                0,
                0,
                ""
            )

            success = False
            last_error = ""

            for attempt in range(
                retry_count + 1
            ):

                if stop_event:

                    if stop_event.is_set():

                        stopped = True
                        break

                try:

                    if url:

                        result = collect_url(
                            url,
                            target
                        )

                    else:

                        result = collect_day(
                            target
                        )

                    total_found += int(
                        result.get(
                            "found",
                            0
                        )
                    )

                    total_saved += int(
                        result.get(
                            "saved",
                            0
                        )
                    )

                    save_collection_state(
                        start_date=start.isoformat(),
                        end_date=end.isoformat(),
                        last_completed_date=(
                            target.isoformat()
                        ),
                        running=True,
                        stopped=False
                    )

                    success = True

                    break

                except Exception as exc:

                    last_error = str(
                        exc
                    )

                    add_log(
                        f"{target}: "
                        f"실패 "
                        f"{attempt + 1}/"
                        f"{retry_count + 1}: "
                        f"{exc}",
                        "ERROR"
                    )

                    if attempt < retry_count:

                        time.sleep(
                            float(
                                retry_delay
                            )
                        )

            if stopped:
                break

            if not success:

                save_collection_day(
                    target,
                    "ERROR",
                    0,
                    0,
                    last_error
                )

                continue

        return {
            "found": total_found,
            "saved": total_saved
        }

    finally:

        state = get_collection_state()

        save_collection_state(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            last_completed_date=state.get(
                "last_completed_date"
            ),
            running=False,
            stopped=stopped
        )


# ============================================================
# DIAGNOSTIC
# ============================================================

def diagnose_html(
    html,
    base_url=""
):

    if not html:

        return {
            "html_length": 0,
            "dt_found": False,
            "dt_length": 0,
            "candidate_count": 0,
            "sample": [],
            "js_size": 0,
            "js_count": 0,
            "external_js_count": 0,
            "date_candidates": [],
            "error": ""
        }

    dt_blocks = find_dt_blocks(
        html
    )

    rows = parse_dt_from_html(
        html
    )

    inline_scripts = extract_scripts(
        html
    )

    external_urls = extract_external_scripts(
        html,
        base_url
    )

    js_size = sum(
        len(x)
        for x in inline_scripts
    )

    return {

        "html_length":
            len(html),

        "dt_found":
            bool(dt_blocks),

        "dt_length":
            (
                len(dt_blocks[0])
                if dt_blocks
                else 0
            ),

        "candidate_count":
            len(rows),

        "sample":
            rows[:5],

        "js_size":
            js_size,

        "js_count":
            len(inline_scripts),

        "external_js_count":
            len(external_urls),

        "external_js":
            external_urls[:20],

        "date_candidates":
            find_date_patterns(
                html
            )[:30],

        "error":
            ""
    }


def diagnose(
    target_date,
    cid=""
):

    """
    app.py에서 직접 호출하는 진단 함수.

    반환 키는 기존 app.py와 호환:
        status
        html_size
        size
        found
        html
        js
        error
    """

    try:

        target = normalize_date(
            target_date
        )

        url = build_url(
            target,
            cid
        )

        response = fetch_response(
            url,
            timeout=40
        )

        html = response["text"]

        # ----------------------------------------------------
        # inline JS
        # ----------------------------------------------------

        inline_scripts = extract_scripts(
            html
        )

        # ----------------------------------------------------
        # 외부 JS
        # ----------------------------------------------------

        external_scripts = fetch_external_scripts(
            html,
            response["url"],
            limit=20
        )

        all_js = list(
            inline_scripts
        )

        for item in external_scripts:

            all_js.append(
                item["text"]
            )

        # ----------------------------------------------------
        # 전체 후보 파싱
        # ----------------------------------------------------

        rows = parse_dt_from_html(
            html
        )

        for js in all_js:

            rows.extend(
                parse_dt_from_html(
                    js
                )
            )

            rows.extend(
                parse_json_candidates(
                    js
                )
            )

        # ----------------------------------------------------
        # 중복 제거
        # ----------------------------------------------------

        unique = {}

        for row in rows:

            if row.get("match_key"):

                unique[
                    row["match_key"]
                ] = row

        rows = list(
            unique.values()
        )

        # ----------------------------------------------------
        # 날짜 후보
        # ----------------------------------------------------

        date_filtered = filter_matches_by_date(
            rows,
            target
        )

        # ----------------------------------------------------
        # JS 출력
        # ----------------------------------------------------

        js_text = "\n\n".join(
            all_js
        )

        # 너무 큰 출력 방지
        if len(js_text) > 200000:

            js_text = js_text[:200000]

        return {

            "status":
                response["status"],

            "html_size":
                len(html),

            "size":
                len(js_text),

            "found":
                len(date_filtered),

            "html":
                html,

            "js":
                js_text,

            "url":
                response["url"],

            "external_js":
                [
                    x["url"]
                    for x in external_scripts
                ],

            "sample":
                date_filtered[:5],

            "error":
                ""
        }

    except HTTPError as exc:

        return {

            "status":
                getattr(
                    exc,
                    "code",
                    0
                ),

            "html_size":
                0,

            "size":
                0,

            "found":
                0,

            "html":
                "",

            "js":
                "",

            "error":
                f"HTTP 오류: {exc.code}"
        }

    except URLError as exc:

        return {

            "status":
                0,

            "html_size":
                0,

            "size":
                0,

            "found":
                0,

            "html":
                "",

            "js":
                "",

            "error":
                f"네트워크 오류: {exc}"
        }

    except Exception as exc:

        return {

            "status":
                0,

            "html_size":
                0,

            "size":
                0,

            "found":
                0,

            "html":
                "",

            "js":
                "",

            "error":
                f"{type(exc).__name__}: {exc}"
        }


# ============================================================
# COMPATIBILITY
# ============================================================

def diagnose_url(url):

    try:

        response = fetch_response(
            url
        )

        return diagnose_html(
            response["text"],
            response["url"]
        )

    except Exception as exc:

        return {
            "html_length": 0,
            "dt_found": False,
            "dt_length": 0,
            "candidate_count": 0,
            "sample": [],
            "js_size": 0,
            "js_count": 0,
            "external_js_count": 0,
            "error": str(exc)
        }


def collect_html(
    html,
    target_date=None
):

    rows = parse_dt_from_html(
        html
    )

    if target_date is not None:

        rows = filter_matches_by_date(
            rows,
            target_date
        )

    saved = 0

    for row in rows:

        try:

            saved += save_match(
                row
            )

        except Exception as exc:

            add_log(
                f"저장 실패: {exc}",
                "ERROR"
            )

    return {
        "found": len(rows),
        "saved": saved,
        "rows": rows
    }


# ============================================================
# INITIALIZE
# ============================================================

init_db()
