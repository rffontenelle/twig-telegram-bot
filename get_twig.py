#!/usr/bin/env python

import os
import re
import requests
import textwrap
import xml.etree.ElementTree as ET
from pprint import pprint

from bs4 import BeautifulSoup

# Constants
RSS_FEED_URL = "https://thisweek.gnome.org/index.xml"
TELEGRAM_API_BASE = "https://api.telegram.org/bot"
MAX_IMAGES_PER_MESSAGE = 10

# Environment variables (required)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise EnvironmentError("Please set BOT_TOKEN and CHAT_ID environment variables.")


def fetch_rss_content(url: str) -> str:
    """Fetch the XML content of the RSS feed."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        print(f"Error fetching RSS feed: {e}")
        return None


def get_latest_post_url(xml_content: str) -> str:
    """Extract the first post URL from the RSS feed."""
    try:
        root = ET.fromstring(xml_content)
        item = root.find(".//item/link")
        return item.text if item is not None else None
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return None


def fetch_post_content(url: str) -> BeautifulSoup:
    """Fetch and parse the post's HTML content."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return BeautifulSoup(response.content, "html.parser")
    except requests.RequestException as e:
        print(f"Error fetching post content: {e}")
        return None


def extract_post_data(soup: BeautifulSoup, post_url: str) -> tuple:
    """Extract the post title, headers and image URLs."""
    post_title_text = "Untitled Post"  # Default title to avoid UnboundLocalError

    img_tags = soup.select("body > main > div.post > blockquote > p > img")
    image_urls = [requests.compat.urljoin(post_url, img.get('src')) for img in img_tags if img.get('src')]

    headers = []
    for header in soup.find_all(["h1", "h3"]):
        if header.name == "h1":
            if "post-title" in header.get("class", []):
                post_title_text = header.text.strip()
            elif "thats-all-for-this-week" in header.get("id", []):
                continue
            else:
                h1_id = header.get("id")
                headers.append({"type": "h1", "id": h1_id, "content": header.text.strip()})
        elif header.name == "h3":
            h3_id = header.get("id")
            # Extract meaningful text from <h3>, excluding anchor icons or unnecessary elements
            text_parts = [t.strip() for t in header.find_all(string=True, recursive=False) if t.strip()]
            h3_text = text_parts[0] if text_parts else None
            if h3_id and h3_text:
                headers.append({"type": "h3", "id": h3_id, "content": h3_text})

    return post_title_text, headers, image_urls


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for MarkdownV2."""
    special_chars = r'_\*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)


def prepare_text_for_sending(title: str, headers: str, url: str) -> str:
    """Get the pieces together to format the text to be sent."""
    text = f"{escape_markdown_v2(title)}\\\n"
    for header in headers:
        content = f"[{escape_markdown_v2(header['content'])}]({url}#{header['id']})"
        if header["type"] == "h1":
            text += f"\\\n\- {content}"
        elif header["type"] == "h3":
            text += f"\\\n   \- {content}"
    return text


def send_telegram_message(bot_token: str, chat_id: str, text: str):
    """Send a text message to a Telegram chat."""
    try:
        url = f"{TELEGRAM_API_BASE}{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "MarkdownV2", "disable_web_page_preview": True}
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print("Message sent successfully!")
    except requests.RequestException as e:
        print(f"Error sending message: {e}")


def send_message_filtering_large_text(bot_token: str, chat_id: str, text: str):
    """Prevent reaching Telegram's 4096 characters limit by splitting."""
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        send_telegram_message(bot_token, chat_id, chunk)


def send_telegram_images(bot_token: str, chat_id: str, image_urls: list):
    """Send multiple images to a Telegram chat."""
    if not image_urls:
        print("No images to send.")
        return

    media_group = [{"type": "photo", "media": url} for url in image_urls[:MAX_IMAGES_PER_MESSAGE]]
    try:
        url = f"{TELEGRAM_API_BASE}{bot_token}/sendMediaGroup"
        response = requests.post(url, json={"chat_id": chat_id, "media": media_group})
        response.raise_for_status()
        print("Images sent successfully!")
    except requests.RequestException as e:
        print(f"Error sending images: {e}")


def main():
    xml_content = fetch_rss_content(RSS_FEED_URL)
    if not xml_content:
        return

    post_url = get_latest_post_url(xml_content)
    if not post_url:
        print("No post URL found.")
        return

    soup = fetch_post_content(post_url)
    if not soup:
        return

    post_title, headers, image_urls = extract_post_data(soup, post_url)

    #print(f"post_title: {post_title}")
    #print(f"headers: {headers}")
    #print(f"image_urls: {image_urls}")

    text = prepare_text_for_sending(post_title, headers, post_url)

    #print(text)
    #print(f"# of chars: {len(text)}")

    send_message_filtering_large_text(BOT_TOKEN, CHAT_ID, text)
    send_telegram_images(BOT_TOKEN, CHAT_ID, image_urls)


if __name__ == "__main__":
    main()
