import json
import requests
import random
import os
from datetime import datetime, timezone, timedelta

SOFT_EMOJIS = ["🌙", "💫", "⭐", "🌸", "🕊️", "✨"]

MINT_GREEN = 0xA8F0C6
PALE_YELLOW = 0xFFF4B8
WEEKLY_PASTEL = 0xD9E8FF


def center(text):
    return text


def build_embed(item):
    title = item["title"]
    url = item["url"]
    poster = item["poster"]
    country = item["country"]
    ep_total = item["episode_count"]
    next_ep = item["next_ep_number"]
    next_date = item["next_ep_date"]
    status = item["status"]

    # Color
    color = MINT_GREEN if status in ["airing", "currently airing"] else PALE_YELLOW

    # Title (centered + soft emoji)
    emoji = random.choice(SOFT_EMOJIS)
    embed_title = center(f"{title} {emoji}")

    # Country flag
    flag = {
        "thailand": "🇹🇭",
        "japan": "🇯🇵",
        "china": "🇨🇳",
        "south korea": "🇰🇷",
        "taiwan": "🇹🇼",
    }.get(country.lower() if country else "", "🌍")

    # Airs In
    airs_in = "Unknown"
    if next_date:
        try:
            dt = datetime.strptime(next_date, "%b %d, %Y").replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            days = (dt - now).days
            if days >= 0:
                airs_in = f"{days} days"
        except:
            pass

    # Build 4-column layout
    fields = [
        {
            "name": "🌍 Country",
            "value": f"{flag} {country}" if country else "—",
            "inline": True
        },
        {
            "name": "🎞️ Episodes",
            "value": f"{ep_total}" if ep_total else "—",
            "inline": True
        },
        {
            "name": "⏳ Airs In",
            "value": airs_in,
            "inline": True
        },
        {
            "name": "📡 Status",
            "value": status.title(),
            "inline": True
        }
    ]

    # Build embed (banner poster at bottom)
    embed = {
        "title": embed_title,
        "description": "",  # no synopsis
        "color": color,
        "fields": fields,
        "image": {"url": poster} if poster else {},  # full-width banner
        "footer": {"text": "🔗 View on MDL"},
        "url": url
    }

    return embed


def build_weekly_summary(items):
    upcoming = []

    now = datetime.now(timezone.utc)
    week_later = now + timedelta(days=7)

    for it in items:
        if not it["next_ep_date"]:
            continue
        try:
            dt = datetime.strptime(it["next_ep_date"], "%b %d, %Y").replace(tzinfo=timezone.utc)
            if now <= dt <= week_later:
                upcoming.append((dt, it))
        except:
            continue

    if not upcoming:
        return None

    upcoming.sort(key=lambda x: (x[0], x[1]["title"].lower()))

    lines = ["📅 **Episodes Airing This Week**\n"]

    current_day = None
    for dt, it in upcoming:
        day_str = dt.strftime("%b %d")
        if day_str != current_day:
            emoji = random.choice(SOFT_EMOJIS)
            lines.append(f"\n{emoji} **{day_str}**")
            current_day = day_str

        ep = it["next_ep_number"]
        lines.append(f"• {it['title']} — Ep {ep}")

    embed = {
        "title": center("Weekly Airing Summary"),
        "description": "\n".join(lines),
        "color": WEEKLY_PASTEL,
        "footer": {"text": "🔗 View on MDL"}
    }

    return embed


def post_new_items(feed_path):
    from rss_parser import parse_feed_items

    with open(feed_path, "r", encoding="utf-8") as f:
        xml = f.read()

    items = parse_feed_items(xml)

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("No webhook URL set.")
        return

    for item in items:
        embed = build_embed(item)
        payload = {
            "embeds": [embed],
            "components": [
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 2,
                            "style": 1,
                            "label": "🔔 Track Airing",
                            "custom_id": "track_airing"
                        },
                        {
                            "type": 2,
                            "style": 1,
                            "label": "📩 Track Finale",
                            "custom_id": "track_finale"
                        }
                    ]
                }
            ]
        }
        requests.post(webhook_url, json=payload)

    summary = build_weekly_summary(items)
    if summary:
        requests.post(webhook_url, json={"embeds": [summary]})
