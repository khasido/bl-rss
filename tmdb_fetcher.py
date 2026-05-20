# tmdb_fetcher.py — DIAGNOSTIC HTML SCRAPER VERSION

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
# HARD‑CODED KEYWORD IDs + SLUGS (needed for HTML URLs)
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
        except Exception as e:
            if attempt == 4:
                print(f"❌ TMDB API ERROR on {path}: {e}")
                return None
            time.sleep(0.5)
    return None

def fetch_html(url):
    for attempt in range(5):
        try:
            r = SESSION.get(url, timeout=30)
            r.raise_for_status()
            return r.text
        except Exception as e:
            if attempt == 4:
                print(f"❌ HTML FETCH ERROR on {url}: {e}")
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
# SEASON ANALYSIS
# ---------------------------------------------------------

def analyze_season(tmdb_id, season_number):
    season = tmdb_get(f"/tv/{tmdb_id}/season/{season_number}")
    if not season or "episodes" not in season:
        print(f"[tv] reject {tmdb_id}: no season data")
        return None

    episodes = sorted(season["episodes"], key=lambda e: e.get("episode_number", 0))
    if not episodes:
        print(f"[tv] reject {tmdb_id}: empty episodes")
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
            next_ep_date = d.strftime("%b %d, %Y")
        if d <= TODAY:
            last_ep_number = ep_num
            last_ep_date = d.strftime("%b %d, %Y")

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
    time.sleep(0.2)

    append = "keywords,credits" + (",seasons" if kind == "tv" else "")
    details = tmdb_get(f"/{kind}/{tmdb_id}", append_to_response=append)
    if not details:
        print(f"[{kind}] reject {tmdb_id}: no details")
        return None

    credits = details.get("credits") or {}

    # Country
    if kind == "tv":
        origin = details.get("origin_country") or []
        country = origin[0] if origin else None
    else:
        pc = details.get("production_countries") or []
        country = pc[0].get("iso_3166_1") if pc else None

    if not country:
        print(f"[{kind}] reject {tmdb_id}: no country")
        return None

    # Date window
    date_str = details.get("first_air_date") if kind == "tv" else details.get("release_date")
    if not in_date_window(date_str):
        print(f"[{kind}] reject {tmdb_id}: date {date_str}")
        return None

    # BL/GL classification
    category = classify_bl_gl(details, credits)
    if category not in ("bl", "gl"):
        print(f"[{kind}] reject {tmdb_id}: not BL/GL")
        return None

    # TV logic
    if kind == "tv":
        seasons = details.get("seasons") or []
        valid = [s for s in seasons if s.get("season_number", 0) > 0]
        if not valid:
            print(f"[tv] reject {tmdb_id}: no valid seasons")
            return None

        season_number = max(s["season_number"] for s in valid)
        season_info = analyze_season(tmdb_id, season_number)
        if not season_info:
            return None

        if season_info["status"] == "ended":
            print(f"[tv] reject {tmdb_id}: ended")
            return None

        if not season_info["next_ep_date"]:
            print(f"[tv] reject {tmdb_id}: no next ep date")
            return None

        next_ep_number = season_info["next_ep_number"]
        next_ep_date = season_info["next_ep_date"]
        status = season_info["status"]
        ep_total = season_info["last_ep_number"]

    else:
        d = parse_date(date_str)
        if not d or d <= TODAY:
            print(f"[movie] reject {tmdb_id}: movie already released")
            return None

        next_ep_number = None
        next_ep_date = d.strftime("%b %d, %Y")
        ep_total = None
        status = "upcoming"

    title = details.get("name") or details.get("title")
    url = f"https://www.themoviedb.org/{kind}/{tmdb_id}"

    print(f"[{kind}] ACCEPT {tmdb_id}: {title}")

    return {
        "id": tmdb_id,
        "title": title,
        "url": url,
        "poster": f"https://image.tmdb.org/t/p/w500{details['poster_path']}" if details.get("poster_path") else None,
        "country_code": country,
        "episode_count": ep_total,
        "next_ep_number": next_ep_number,
        "next_ep_date": next_ep_date,
        "status": status,
        "category": category,
    }

# ---------------------------------------------------------
# HTML SCRAPER FOR KEYWORD PAGES
# ---------------------------------------------------------

def scrape_keyword_page(keyword_id, slug, kind):
    url = f"https://www.themoviedb.org/keyword/{keyword_id}-{slug}/{kind}"
    print(f"\n>>> SCRAPING HTML: {url}")

    html = fetch_html(url)
    if not html:
        print(f"[{kind}] keyword {keyword_id}: HTML fetch failed")
        return []

    # Extract TMDB IDs from HTML
    ids = set(map(int, re.findall(r'/'+kind+r'/(\d+)', html)))

    print(f"[{kind}] keyword {keyword_id}: FOUND {len(ids)} IDs in HTML")
    return list(ids)

# ---------------------------------------------------------
# MAIN DISCOVERY
# ---------------------------------------------------------

def discover_candidates(kind):
    print(f"\n=== DISCOVER VIA HTML ({kind.upper()}) START ===")

    combined = set()

    keyword_map = {**BL_KEYWORDS, **GL_KEYWORDS}

    for kw, slug in keyword_map.items():
        ids = scrape_keyword_page(kw, slug, kind)
        for i in ids:
            combined.add(i)

    print(f"[{kind}] TOTAL UNIQUE IDS FROM HTML: {len(combined)}")

    results = []
    for entry_id in combined:
        item = build_item(entry_id, kind)
        if item:
            results.append(item)

    print(f"[{kind}] FINAL ITEMS AFTER build_item: {len(results)}")
    print(f"=== DISCOVER VIA HTML ({kind.upper()}) END ===\n")

    return results

# ---------------------------------------------------------
# PUBLIC FETCHERS
# ---------------------------------------------------------

def fetch_bl_items():
    tv_items = discover_candidates("tv")
    movie_items = discover_candidates("movie")
    return [i for i in tv_items + movie_items if i["category"] == "bl"]

def fetch_gl_items():
    tv_items = discover_candidates("tv")
    movie_items = discover_candidates("movie")
    return [i for i in tv_items + movie_items if i["category"] == "gl"]
