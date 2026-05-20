# tmdb_fetcher.py — FIXED VERSION WITH NEXT_EPISODE_TO_AIR SUPPORT
import os
import re
import time
import requests
from datetime import datetime, date, timedelta

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"

SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

# ---------------------------------------------------------
# KEYWORD IDS + SLUGS
# ---------------------------------------------------------

BL_KEYWORDS = {
    "240305": "gay-romance",
    "289844": "boys-love-bl",
    "265777": "gay-relationship",
    "347855": "fudanshi",
}

GL_KEYWORDS = {
    "280003": "girls-love-gl",
    "9833": "lesbian-relationship",
    "315382": "lesbian-couple",
}

PRIORITY_COUNTRIES = ["TH", "JP", "KR", "CN", "TW", "PH", "VN", "HK", "MY"]

TODAY = date.today()
SIX_MONTHS_AGO = TODAY - timedelta(days=6 * 30)
TWO_YEARS_AHEAD = TODAY + timedelta(days=2 * 365)

# ---------------------------------------------------------
# BASIC GETTERS
# ---------------------------------------------------------

def tmdb_get(path, **params):
    params["api_key"] = TMDB_API_KEY
    for attempt in range(5):
        try:
            r = SESSION.get(f"{BASE_URL}{path}", params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except:
            if attempt == 4:
                return None
            time.sleep(0.5)
    return None

def fetch_html(url):
    for attempt in range(5):
        try:
            r = SESSION.get(url, timeout=30)
            r.raise_for_status()
            return r.text
        except:
            if attempt == 4:
                return None
            time.sleep(0.5)
    return None

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def parse_date(dstr):
    if not dstr:
        return None
    try:
        return datetime.strptime(dstr, "%Y-%m-%d").date()
    except:
        return None

def in_date_window(dstr):
    d = parse_date(dstr)
    if not d:
        return False
    return SIX_MONTHS_AGO <= d <= TWO_YEARS_AHEAD

def extract_keywords(details):
    kw_block = details.get("keywords") or {}
    if isinstance(kw_block, dict):
        if isinstance(kw_block.get("keywords"), list):
            return kw_block["keywords"]
        if isinstance(kw_block.get("results"), list):
            return kw_block["results"]
    if isinstance(kw_block, list):
        return kw_block
    return []

def extract_keyword_names(details):
    return {(k.get("name") or "").lower().strip() for k in extract_keywords(details)}

# ---------------------------------------------------------
# BL/GL CLASSIFICATION
# ---------------------------------------------------------

def classify_bl_gl(details, credits):
    kw_names = extract_keyword_names(details)

    BL_NAMES = {
        "gay romance",
        "boys' love (bl)",
        "gay relationship",
        "fudanshi",
    }

    GL_NAMES = {
        "girls' love (gl)",
        "lesbian relationship",
        "lesbian couple",
    }

    has_bl = any(k in kw_names for k in BL_NAMES)
    has_gl = any(k in kw_names for k in GL_NAMES)

    if not has_bl and not has_gl:
        return None

    if has_bl and has_gl:
        cast = credits.get("cast") or []
        male = [c for c in cast if c.get("gender") == 2][:2]
        female = [c for c in cast if c.get("gender") == 1][:2]
        if len(male) >= 2 and not female:
            return "bl"
        if len(female) >= 2 and not male:
            return "gl"
        return None

    return "bl" if has_bl else "gl"

# ---------------------------------------------------------
# SEASON ANALYSIS (FALLBACK)
# ---------------------------------------------------------

def analyze_season(tmdb_id, season_number):
    season = tmdb_get(f"/tv/{tmdb_id}/season/{season_number}")
    if not season or "episodes" not in season:
        return None

    episodes = sorted(season["episodes"], key=lambda e: e.get("episode_number", 0))
    if not episodes:
        return None

    next_ep_number = None
    next_ep_date = None
    last_ep_number = None
    last_ep_date = None

    for ep in episodes:
        d = parse_date(ep.get("air_date"))
        if not d:
            continue
        ep_num = ep.get("episode_number")

        if d > TODAY and next_ep_number is None:
            next_ep_number = ep_num
            next_ep_date = d.isoformat()
        if d <= TODAY:
            last_ep_number = ep_num
            last_ep_date = d.isoformat()

    status = "ongoing" if next_ep_number else "ended"

    return {
        "next_ep_number": next_ep_number,
        "next_ep_date": next_ep_date,
        "last_ep_number": last_ep_number,
        "last_ep_date": last_ep_date,
        "status": status,
    }

# ---------------------------------------------------------
# BUILD ITEM
# ---------------------------------------------------------

def build_item(entry_id, kind):
    tmdb_id = entry_id
    time.sleep(0.15)

    append = "keywords,credits" + (",seasons" if kind == "tv" else "")
    details = tmdb_get(f"/{kind}/{tmdb_id}", append_to_response=append)
    if not details:
        return None

    credits = details.get("credits") or {}

    overview = details.get("overview") or details.get("tagline") or ""

    # Country
    if kind == "tv":
        origin = details.get("origin_country") or []
        country = origin[0] if origin else None
    else:
        pc = details.get("production_countries") or []
        country = pc[0].get("iso_3166_1") if pc else None

    # Date window
    date_str = details.get("first_air_date") if kind == "tv" else details.get("release_date")
    if not in_date_window(date_str):
        return None

    # BL/GL classification
    category = classify_bl_gl(details, credits)
    if category not in ("bl", "gl"):
        return None

    # ---------------------------------------------------------
    # TV LOGIC — FIXED WITH next_episode_to_air
    # ---------------------------------------------------------
    if kind == "tv":
        next_ep = details.get("next_episode_to_air")

        if next_ep and next_ep.get("air_date"):
            next_ep_date = parse_date(next_ep["air_date"]).isoformat()
            next_ep_number = next
