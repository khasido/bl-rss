import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin
from pathlib import Path
import re

LIST_URL = "https://mydramalist.com/list/3kPbQnZ4"
BASE_URL = "https://mydramalist.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BL-RSS-Bot/1.0)"
}

def fetch(url):
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.text

def parse_list_page(html):
    """Return absolute show URLs from the MDL list page."""
    soup = BeautifulSoup(html, "lxml")
    show_links = []

    for a in soup.select("div.list-item a[href^='/']"):
        href = a.get("href")
        if href and re.match(r"^/\d+", href):
            full = urljoin(BASE_URL, href.split("#")[0])
            if full not in show_links:
                show_links.append(full)

    return show_links

def get_text_after_label(details_soup, label):
    """Extract text after a labeled field in the details section."""
    for li in details_soup.select("li"):
        label_span = li.find("span")
        if label_span and label_span.get_text(strip=True).startswith(label):
            text = li.get_text(" ", strip=True)
            return text.replace(label, "").strip(": ").strip()
    return None

def parse_air_date(details_soup):
    aired = get_text_after_label(details_soup, "Aired:")
    if not aired:
        aired = get_text_after_label(details_soup, "Airs:")
    return aired

def parse_next_episode_date(soup):
    next_ep_text = soup.find(string=re.compile(r"Next Episode", re.I))
    if next_ep_text:
        nearby = next_ep_text.parent
        if nearby:
            text = nearby.get_text(" ", strip=True)
            match = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2}, \d{4}", text)
            if match:
                return match.group(0)
    return None

def parse_show_page(url):
    html = fetch(url)
    soup = BeautifulSoup(html, "lxml")

    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else url

    poster = None
    img = soup.select_one("img[src*='https://i.mydramalist.com']")
    if img and img.get("src"):
        poster = img["src"]

    details = soup.select_one("div.show-details, div.box")
    country = None
    air_date_str = None
    if details:
        country = get_text_after_label(details, "Country:")
        air_date_str = parse_air_date(details)

    next_ep_date = parse_next_episode_date(soup)
    countdown_str = None
    if next_ep_date:
        try:
            dt = datetime.strptime(next_ep_date, "%b %d, %Y").replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = dt - now
            if delta.days >= 0:
                countdown_str = f"Next episode in {delta.days} days"
        except ValueError:
            countdown_str = None

    return {
        "title": title,
        "url": url,
        "poster": poster,
        "country": country,
        "air_date": air_date_str,
        "next_ep_date": next_ep_date,
        "countdown": countdown_str,
    }

def format_rfc2822(date_str):
    if not date_str:
        return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")

    for fmt in ("%b %d, %Y", "%b %Y", "%Y"):
        try:
            dt = datetime.strptime(date_str.split("–")[0].strip(), fmt)
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime("%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            continue

    return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")

def build_rss(items):
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
    rss_items = []

    for it in items:
        desc_parts = []
        if it["country"]:
            desc_parts.append(f"Country: {it['country']}")
        if it["air_date"]:
            desc_parts.append(f"Air Date: {it['air_date']}")
        if it["next_ep_date"]:
            desc_parts.append(f"Next Episode: {it['next_ep_date']}")
        if it["countdown"]:
            desc_parts.append(it["countdown"])

        description_html = "<br>".join(desc_parts) if desc_parts else "No additional info."
        media_tag = ""
        if it["poster"]:
            media_tag = f"\n    <media:content url=\"{it['poster']}\" type=\"image/jpeg\" />"

        item_xml = (
            "  <item>\n"
            f"    <title>{it['title']}</title>\n"
            f"    <link>{it['url']}</link>\n"
            f"    <description><![CDATA[{description_html}]]></description>\n"
            f"    <pubDate>{format_rfc2822(it['air_date'])}</pubDate>{media_tag}\n"
            "  </item>"
        )
        rss_items.append(item_xml)

    rss_body = "\n".join(rss_items)
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<rss version=\"2.0\" xmlns:media=\"http://search.yahoo.com/mrss/\">\n"
        "<channel>\n"
        "  <title>MyDramaList BL List</title>\n"
        f"  <link>{LIST_URL}</link>\n"
        "  <description>Auto-generated feed from MyDramaList list 3kPbQnZ4</description>\n"
        f"  <lastBuildDate>{now}</lastBuildDate>\n"
        f"{rss_body}\n"
        "</channel>\n"
        "</rss>\n"
    )

def main():
    list_html = fetch(LIST_URL)
    show_urls = parse_list_page(list_html)

    items = []
    for url in show_urls:
        try:
            print(f"Parsing {url}")
            data = parse_show_page(url)
            items.append(data)
        except Exception as exc:
            print(f"Error parsing {url}: {exc}")

    rss_xml = build_rss(items)
    Path("feed.xml").write_text(rss_xml, encoding="utf-8")
    print("feed.xml updated.")

if __name__ == "__main__":
    main()
