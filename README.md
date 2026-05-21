🌿 Kohei’s Feed — Automated BL/GL Airing Tracker
TMDB‑Powered Discovery • Aesthetic Discord Embeds • Auto‑Generated RSS Feeds
Kohei’s Feed is a fully automated system that discovers upcoming and ongoing Boys’ Love (BL) and Girls’ Love (GL) titles from TMDB, generates clean RSS feeds, and posts beautifully styled embeds to Discord — all without manual updates.

This project is built for fans who want a soft, aesthetic, always‑up‑to‑date BL/GL airing feed.

----------------------------------------------------------------------------------------------------

✨ What Kohei’s Feed Does
🔍 Automatic BL/GL Discovery
Scrapes TMDB keyword pages for BL/GL content

Supports both TV shows and movies

Filters out:

Ended shows

Items without future episodes

Titles outside the date window

Prioritizes Asian countries (TH, JP, KR, CN, etc.)

🧠 Smart Metadata Extraction
Each title includes:

Title

Poster

Country

Category (BL/GL)

Episode count

Next episode number + date

Clipped overview

TMDB link

📰 RSS Feed Generation
Creates two feeds:

```feed_bl.xml

feed_gl.xml
```
Each feed item includes:

Poster image

Country

Episode count

Next episode info

Synopsis

TMDB link

💬 Aesthetic Discord Posting
Posts soft, pastel‑themed embeds with:

Mint green color

Soft emojis

Clean metadata block

Poster image

Shortened overview


Messages update automatically when metadata changes.

🗂 State Tracking
Stored in:

```state_bl.json

state_gl.json
```

Tracks:

Next episode date

Next episode number

Status

Discord message ID

Ensures no duplicates and correct ordering.

🤖 Fully Automated via GitHub Actions
Runs every 6 minutes:

Discovers new titles

Updates RSS feeds

Updates Discord messages

Commits changes back to the repo

---------------------------------------------------------------------------------------------------

📁 Project Structure
```.
├── update.py              # Main orchestrator
├── tmdb_fetcher.py        # TMDB scraping + metadata builder
├── rss_builder.py         # RSS feed generator
├── rss_parser.py          # RSS parser (for Discord posting)
├── post_to_discord.py     # Webhook embed builder + posting logic
├── state_manager.py       # Persistent state tracking
├── data/
│   └── blacklist.json     # Optional blacklist for BL/GL filtering
├── feed_bl.xml            # Generated BL RSS feed
├── feed_gl.xml            # Generated GL RSS feed
├── state_bl.json          # BL posted state
├── state_gl.json          # GL posted state
└── .github/workflows/
    └── update-rss.yml     # Scheduled automation workflow
```
🚀 Setup
1. Clone the repository
```git clone https://github.com/<yourname>/<repo>.git
cd <repo>
```
2. Install dependencies
```pip install -r requirements.txt```
3. Add GitHub Secrets
Go to Settings → Secrets → Actions and add:

Secret	           Description
TMDB_API_KEY	      Your TMDB API key
DISCORD_WEBHOOK_BL	Webhook for BL channel
DISCORD_WEBHOOK_GL	Webhook for GL channel

-------------------------------------------------------------------------------------------------------
🧩 How It Works
Scrape TMDB for BL/GL keyword pages

Build metadata for each title

Filter + sort by priority and next episode date

Post or update Discord embeds

Generate RSS feeds

Commit changes automatically

🎨 Example Discord Embed
```✦ Show Title 🌸 ✦

Country: TH
Category: BL
Status: Ongoing
Episodes: 12
Next Episode: May 23, 2026

Shortened overview…
```

🛠 Customization
Blacklist
Add TMDB IDs to:
```data/blacklist.json```
Priority Countries
Edit:
```PRIORITY_COUNTRIES = ["TH", "JP", "KR", ...]```
Aesthetic Theme
Modify colors/emojis in:
```post_to_discord.py```

-------------------------------------------------------------------------------------------------------
❤️ Credits
Built with:

TMDB API

GitHub Actions

Discord Webhooks

Python 3.11

Created for BL/GL fans who want a soft, modern, automated airing feed.
