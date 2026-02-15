#!/usr/bin/env python3
"""
Inject missing newsletter entries from Substack RSS into newsletter_data.json and newsletter_data_en.json.

Usage: python3 scripts/inject_from_rss.py [--feed-url URL] [--data-dir DIR]

Idempotent: skips entries already present (matched by urlSlug).
"""

import json
import re
import sys
import os
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass

# Default config
DEFAULT_FEED_URL = "https://fortissimo.substack.com/feed"
SCRIPT_DIR = Path(__file__).parent
DEFAULT_DATA_DIR = SCRIPT_DIR.parent


def fetch_rss(feed_url):
    """Fetch RSS feed and return parsed XML root."""
    req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return ET.fromstring(resp.read())


def extract_ff_number(title):
    """Extract ff number from title like '🎼 ff.144 ...'"""
    m = re.search(r'ff\.(\d+)', title)
    return int(m.group(1)) if m else None


def slug_from_link(link):
    """Extract URL slug from Substack link."""
    # https://fortissimo.substack.com/p/ff144-il-fischio-dellaragosta -> ff144-il-fischio-dellaragosta
    m = re.search(r'/p/([^/?#]+)', link)
    return m.group(1) if m else None


def get_existing_slugs(data):
    """Get set of existing urlSlugs."""
    return {p.get("urlSlug") for p in data.get("publications", [])}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Saved {path}")


def insert_sorted(publications, new_entry):
    """Insert entry in descending ff number order."""
    new_num = extract_ff_number(new_entry.get("buttonLabel", ""))
    if new_num is None:
        publications.append(new_entry)
        return
    for i, p in enumerate(publications):
        existing_num = extract_ff_number(p.get("buttonLabel", ""))
        if existing_num is not None and new_num > existing_num:
            publications.insert(i, new_entry)
            return
    publications.append(new_entry)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Inject missing FF newsletters from RSS")
    parser.add_argument("--feed-url", default=DEFAULT_FEED_URL)
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    it_path = data_dir / "newsletter_data.json"
    en_path = data_dir / "newsletter_data_en.json"

    if not it_path.exists():
        print(f"ERROR: {it_path} not found")
        sys.exit(1)

    it_data = load_json(it_path)
    en_data = load_json(en_path) if en_path.exists() else {"publications": []}

    existing_slugs = get_existing_slugs(it_data)
    print(f"Existing entries: {len(it_data['publications'])}")

    # Parse RSS
    print(f"Fetching RSS from {args.feed_url}...")
    try:
        root = fetch_rss(args.feed_url)
    except Exception as e:
        print(f"ERROR fetching RSS: {e}")
        print("Note: Run this script where HTTP access is available, or manually add entries.")
        sys.exit(1)

    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
    items = root.findall(".//item")
    print(f"Found {len(items)} items in RSS feed")

    added = 0
    for item in items:
        title = item.find("title").text or ""
        link = item.find("link").text or ""
        slug = slug_from_link(link)
        ff_num = extract_ff_number(title)

        if not slug or not ff_num:
            continue

        if slug in existing_slugs:
            continue

        print(f"\n  Missing: {title} (ff.{ff_num}, slug={slug})")

        # Extract content from RSS content:encoded
        content_el = item.find("content:encoded", ns)
        html_content = content_el.text if content_el is not None else ""

        # Parse sections from HTML
        cards = parse_html_to_cards(html_content, ff_num, title)

        entry_it = {
            "buttonLabel": title,
            "substackLink": link,
            "urlSlug": slug,
            "title": title,
            "cards": cards,
        }

        # EN version
        en_link = f"https://translate.google.com/translate?sl=it&tl=en&u={link}"
        en_title = translate_title(title)
        en_cards = translate_cards(cards)

        entry_en = {
            "title": en_title,
            "buttonLabel": en_title,
            "urlSlug": slug,
            "substackLink": en_link,
            "cards": en_cards,
        }

        insert_sorted(it_data["publications"], entry_it)
        insert_sorted(en_data["publications"], entry_en)
        existing_slugs.add(slug)
        added += 1

    if added == 0:
        print("\nNo missing entries found. Everything up to date!")
    else:
        save_json(it_path, it_data)
        save_json(en_path, en_data)
        print(f"\nAdded {added} entries.")


def parse_html_to_cards(html, ff_num, main_title):
    """Parse HTML content to extract cards (sections) matching ff.XXX.Y pattern."""
    from html.parser import HTMLParser
    import html as html_mod

    cards = []

    # Find all h4 sections which contain ff.XXX.Y
    # Pattern: <h4>emoji ff.XXX.Y Title</h4> followed by content until next <h4> or <hr>
    section_pattern = re.compile(
        r'<h4[^>]*>(.*?)</h4>(.*?)(?=<h4|<div><hr></div>|$)',
        re.DOTALL
    )

    matches = list(section_pattern.finditer(html))

    if not matches:
        # Try simpler approach - create a single overview card
        desc_match = re.search(r'<p>(.*?)</p>', html)
        desc = clean_html(desc_match.group(1)) if desc_match else main_title
        return [{
            "title": "📖 Panorama",
            "tags": ["🤖"],
            "contentBlocks": [{
                "type": "paragraphs",
                "content": [desc]
            }]
        }]

    # First, create a Panorama card from the intro (before first h4)
    intro_match = re.search(r'^(.*?)(?=<h4)', html, re.DOTALL)
    if intro_match:
        intro_text = intro_match.group(1)
        # Extract bullet points from intro
        bullet_pattern = re.compile(r'<li[^>]*><p>(.*?)</p></li>', re.DOTALL)
        bullets = [clean_html(b.group(1)) for b in bullet_pattern.finditer(intro_text)]
        if bullets:
            cards.append({
                "title": "📖 Panorama",
                "tags": extract_tags_from_content(intro_text),
                "contentBlocks": [{
                    "type": "paragraphs",
                    "content": bullets
                }]
            })

    for match in matches:
        section_title = clean_html(match.group(1))
        section_content = match.group(2)

        # Skip footer sections
        if "supporta con un caffè" in section_title.lower() or "futuro fortissimo" in section_title.lower():
            continue

        # Extract paragraphs
        para_pattern = re.compile(r'<p[^>]*>(.*?)</p>', re.DOTALL)
        paragraphs = []
        for p in para_pattern.finditer(section_content):
            text = clean_html(p.group(1))
            # Skip empty, button wrappers, subscribe links
            if text and len(text) > 5 and "Iscriviti ora" not in text and "ENGLISH VERSION" not in text:
                paragraphs.append(text)

        # Also extract blockquotes
        bq_pattern = re.compile(r'<blockquote>(.*?)</blockquote>', re.DOTALL)
        for bq in bq_pattern.finditer(section_content):
            bq_text = clean_html(bq.group(1))
            if bq_text and len(bq_text) > 5:
                paragraphs.append(f"«{bq_text}»")

        if not paragraphs:
            continue

        # Limit to key sentences (max 3)
        if len(paragraphs) > 4:
            paragraphs = paragraphs[:3]

        tags = extract_tags_from_title(section_title)

        cards.append({
            "title": section_title,
            "tags": tags,
            "contentBlocks": [{
                "type": "paragraphs",
                "content": paragraphs
            }]
        })

    return cards if cards else [{
        "title": "📖 Panorama",
        "tags": ["🤖"],
        "contentBlocks": [{
            "type": "paragraphs",
            "content": [clean_html(main_title)]
        }]
    }]


def clean_html(text):
    """Remove HTML tags and decode entities."""
    import html as html_mod
    # Remove tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = html_mod.unescape(text)
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_tags_from_title(title):
    """Extract emoji tags from section title."""
    emojis = re.findall(r'[\U0001F300-\U0001FAFF\u2600-\u27BF\u2702-\u27B0]', title)
    tag_map = {
        "🤖": "🤖", "🧠": "🧠", "🌿": "🍃", "🍃": "🍃",
        "🔥": "🔥", "☀": "☀️", "🐒": "🧠", "🌍": "🌍",
        "📱": "📱", "💻": "💻", "🦞": "🦞", "🕳": "🧠",
    }
    tags = []
    for e in emojis:
        if e in tag_map:
            tags.append(tag_map[e])
        else:
            tags.append(e)
    if not tags:
        tags = ["🤖"]
    return list(dict.fromkeys(tags))  # dedupe preserving order


def extract_tags_from_content(content):
    """Extract tags based on content themes."""
    tags = []
    content_lower = content.lower()
    if any(w in content_lower for w in ["ai", "intelligenza artificiale", "gpt", "gemini"]):
        tags.append("🤖")
    if any(w in content_lower for w in ["natura", "clima", "ambiente"]):
        tags.append("🍃")
    if any(w in content_lower for w in ["social", "app", "tech"]):
        tags.append("📱")
    return tags or ["🤖"]


def translate_title(title):
    """Simple title translation IT->EN for common patterns."""
    # Keep ff.XXX numbering, translate the rest simply
    translations = {
        "🎼 ff.140 Tutti App-fluencers?": "🎼 ff.140 All App-fluencers?",
        "🎼 ff.141 Il 2025 su un Floppy Disk": "🎼 ff.141 2025 on a Floppy Disk",
        "🎼 ff.142 Caro Marziano...": "🎼 ff.142 Dear Martian...",
        "🎼 ff.144 Il fischio dell'aragosta": "🎼 ff.144 The Lobster's Whistle",
    }
    return translations.get(title, title)


def translate_cards(cards):
    """Create EN version of cards with translated titles."""
    en_cards = []
    title_translations = {
        "📖 Panorama": "📖 Overview",
    }
    for card in cards:
        en_card = dict(card)
        en_card["title"] = title_translations.get(card["title"], card["title"])
        # Keep content as-is (link to translated version instead)
        en_cards.append(en_card)
    return en_cards


if __name__ == "__main__":
    main()
