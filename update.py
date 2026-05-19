import hashlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin
from pathlib import Path
from xml.sax.saxutils import escape
import re
import json
import time

LIST_URL = "https://mydramalist.com/list/3kPbQnZ4"
BASE_URL = "https://mydramalist.com"
MAX_ITEMS = 100
FEED_TITLE = "BL Updates"
FEED_DESCRIPTION = "Auto-generated feed from MyDramaList list 3kPbQnZ4"
FEED_LINK = LIST_URL

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BL-RSS-Bot/1.0)"
}

# ---------------------------------------------------------
# FREEZE-PROOF FETCH WITH RETRIES + TIMEOUT
# ---------------------------------------------------------
def fetch(url, retries=3, delay=2):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            print(f"[WARN] Fetch failed ({attempt+1}/{retries}) for {url}: {exc}")
            time.sleep(delay)
    print(f"[ERROR] Skipping URL after repeated failures: {url}")
    return None

# ---------------------------------------------------------
# PARSE LIST PAGE
# ---------------------------------------------------------
def parse_list_page(html):
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    show_links = []

    for li in soup.find_all("li", {"class": "list-group-item"}):
        link = li.find("a", href=re.compile(r"^/\d+"))
        if link:
            href = link.get("href")
            if href and re.match(r"^/\d+-", href):
                full = urljoin(BASE_URL, href.split("#")[0])
                if full not in show_links:
                    show_links.append(full)

    return show_links

# ---------------------------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------------------------
def safe_text(element):
    return element.get_text(" ", strip=True) if element else None

def xml_text(value):
    return escape(str(value)) if value is not None else ""

def get_text_after_label(soup, label):
    for li in soup.find_all("li", {"class": "list-item"}):
        b_tag = li.find("b")
        if b_tag and label in b_tag.get_text(strip=True):
            full_text = li.get_text(strip=True)
            label_pos = full_text.find(label)
            if label_pos >= 0:
                return full_text[label_pos + len(label):].strip()
    return None

def parse_episode_count(episodes):
    if not episodes:
        return None
    match = re.search(r"(\d+)", episodes)
    return int(match.group(1)) if match else None

def parse_next_episode_number(html):
    if not html:
        return None
    try:
        match = re.search(r'var nextEpisodeAiring\s*=\s*({.*?});', html, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            for key in ("episode_number", "episodeNumber", "episode"):
                if key in data and data[key] is not None:
                    return int(data[key])
    except:
        pass
    return None

def parse_next_episode_date(html):
    if not html:
        return None
    try:
        match = re.search(r'var nextEpisodeAiring\s*=\s*({.*?});', html, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            if "released_at" in data:
                timestamp = int(data["released_at"])
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                return dt.strftime("%b %d, %Y")
    except:
        pass
    return None

def parse_json_ld_description(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue

        if isinstance(data, dict) and data.get("description"):
            return data["description"].strip()

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("description"):
                    return item["description"].strip()
    return None

def parse_synopsis(soup):
    selectors = [
        "div.show-synopsis",
        "div.storyline",
        "div.synopsis",
        "section.show__description",
        "div.content",
    ]
    for selector in selectors:
        section = soup.select_one(selector)
        if section:
            for ui_node in section.select("a.text-primary, ul.mdl-synopsis-languages"):
                ui_node.decompose()

            paragraphs = [p.get_text(" ", strip=True) for p in section.find_all("p") if p.get_text(strip=True)]
            if paragraphs:
                return "\n\n".join(paragraphs[:2])

            text = section.get_text(" ", strip=True)
            if text:
                return text
    return None

# ---------------------------------------------------------
# PARSE SHOW PAGE
# ---------------------------------------------------------
def parse_show_page(url):
    html = fetch(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")

    # Title
    title_el = soup.find("h1")
    title = safe_text(title_el) if title_el else None
    if not title:
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"].strip() if og_title else url

    # Poster
    poster = None
    for selector in ("img.cover", "img[src*='mydramalist.com']", "img[src*='mydramalist']"):
        img = soup.select_one(selector)
        if img and img.get("src"):
            poster = img["src"].strip()
            break
    if poster and poster.startswith("//"):
        poster = f"https:{poster}"

    country = get_text_after_label(soup, "Country:")
    episodes = get_text_after_label(soup, "Episodes:")
    episode_count = parse_episode_count(episodes)
    air_date_str = get_text_after_label(soup, "Aired:")
    next_ep_date = parse_next_episode_date(html)
    next_ep_number = parse_next_episode_number(html)

    # Status
    status = get_text_after_label(soup, "Status:")
    status = status.lower() if status else None

    # Synopsis
    synopsis = parse_synopsis(soup) or parse_json_ld_description(soup)

    return {
        "title": title,
        "url": url,
        "poster": poster,
        "country": country,
        "episodes": episodes,
        "episode_count": episode_count,
        "air_date": air_date_str,
        "synopsis": synopsis,
        "next_ep_date": next_ep_date,
        "next_ep_number": next_ep_number,
        "status": status,
    }

# ---------------------------------------------------------
# SORTING LOGIC (CHRONOLOGICAL + ALPHABETICAL)
# ---------------------------------------------------------
def parse_sort_date(date_str):
    if not date_str:
        return None

    clean = re.split(r"\s*[-–]\s*", date_str)[0].strip()
    for fmt in ("%b %d, %Y", "%b %Y", "%Y"):
        try:
            return datetime.strptime(clean, fmt).replace(tzinfo=timezone.utc)
        except:
            continue
    return None

def sort_key(item):
    # 1. Full date > month-year > year > no date
    d1 = parse_sort_date(item["next_ep_date"])
    d2 = parse_sort_date(item["air_date"])

    date = d1 or d2

    # Items with no date go last
    if not date:
        return (3, datetime.max, item["title"].lower())

    # Items with only year
    if re.fullmatch(r"\d{4}", item["next_ep_date"] or item["air_date"] or ""):
        return (2, date, item["title"].lower())

    # Items with month-year only
    if re.fullmatch(r"[A-Za-z]{3} \d{4}", item["next_ep_date"] or item["air_date"] or ""):
        return (1, date, item["title"].lower())

    # Full date
    return (0, date, item["title"].lower())

# ---------------------------------------------------------
# BUILD RSS
# ---------------------------------------------------------
def image_mime_type(url):
    url = url.lower()
    if url.endswith(".png"):
        return "image/png"
    if url.endswith(".gif"):
        return "image/gif"
    return "image/jpeg"

def build_rss(items):
    base_dt = datetime.now(timezone.utc)
    now = base_dt.strftime("%a, %d %b %Y %H:%M:%S %z")
    rss_items = []

    for idx, it in enumerate(items):
        desc_lines = []

        if it["poster"]:
            desc_lines.append(
                f"<p><img src=\"{it['poster']}\" alt=\"{it['title']} poster\" "
                f"style=\"width:100%;max-width:700px;height:auto;border:0;display:block;margin:0 0 1em;\" /></p>"
            )

        if it["country"]:
            desc_lines.append(f"<p><strong>Country:</strong> {escape(it['country'])}</p>")

        if it.get("episode_count") is not None:
            desc_lines.append(f"<p><strong>Total Episodes:</strong> {it['episode_count']}</p>")

        if it.get("next_ep_date"):
            ep = it.get("next_ep_number")
            total = it.get("episode_count")
            if ep and total:
                desc_lines.append(
                    f"<p><strong>Next Episode:</strong> {ep} of {total} — {escape(it['next_ep_date'])}</p>"
                )
            else:
                desc_lines.append(
                    f"<p><strong>Next Episode:</strong> {escape(it['next_ep_date'])}</p>"
                )

        if it["synopsis"]:
            syn = escape(it["synopsis"]).replace("\n\n", "<br><br>")
            desc_lines.append(f"<p>{syn}</p>")

        desc_lines.append(f"<p><a href=\"{it['url']}\">View on MyDramaList</a></p>")

        description_html = "\n".join(desc_lines)

        enclosure_tag = ""
        if it["poster"]:
            mime = image_mime_type(it["poster"])
            enclosure_tag = f"\n    <enclosure url=\"{it['poster']}\" type=\"{mime}\" length=\"0\" />"

        pub_date = (base_dt - timedelta(seconds=idx)).strftime("%a, %d %b %Y %H:%M:%S %z")
        guid = hashlib.sha256(it["url"].encode("utf-8")).hexdigest()

        item_xml = (
            "  <item>\n"
            f"    <title>{xml_text(it['title'])}</title>\n"
            f"    <link>{xml_text(it['url'])}</link>\n"
            f"    <guid isPermaLink=\"false\">{guid}</guid>\n"
            f"    <pubDate>{pub_date}</pubDate>\n"
            f"    <description><![CDATA[{description_html}]]></description>\n"
            f"    <content:encoded><![CDATA[{description_html}]]></content:encoded>\n"
            f"{enclosure_tag}\n"
            "  </item>"
        )
        rss_items.append(item_xml)

    channel_header = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<rss version=\"2.0\" xmlns:media=\"http://search.yahoo.com/mrss/\" "
        "xmlns:content=\"http://purl.org/rss/1.0/modules/content/\">\n"
        "<channel>\n"
        f"  <title>{FEED_TITLE}</title>\n"
        f"  <link>{FEED_LINK}</link>\n"
        f"  <description>{FEED_DESCRIPTION}</description>\n"
        "  <language>en-US</language>\n"
        "  <generator>BL-RSS Auto Generator</generator>\n"
        f"  <lastBuildDate>{now}</lastBuildDate>\n"
    )

    return f"{channel_header}{''.join(rss_items)}\n</channel>\n</rss>\n"

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    list_html = fetch(LIST_URL)
    show_urls = parse_list_page(list_html)[:MAX_ITEMS]

    items = []
    for url in show_urls:
        print(f"Parsing {url}")
        data = parse_show_page(url)
        if not data:
            continue

        # Skip completed/ended shows
        if data.get("status") in ["completed", "finished", "ended"]:
            continue

        items.append(data)

    # Sort using the multi-tiered key
    items.sort(key=sort_key, reverse=True)

    rss_xml = build_rss(items)
    Path("feed.xml").write_text(rss_xml, encoding="utf-8")
    print("feed.xml updated.")

    # Optional Discord posting
    try:
        import os
        if os.environ.get("DISCORD_WEBHOOK_URL"):
            from post_to_discord import post_new_items
            post_new_items("feed.xml")
    except Exception as exc:
        print(f"Error posting to Discord: {exc}")

if __name__ == "__main__":
    main()

