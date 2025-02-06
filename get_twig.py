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
MAX_IMAGES_PER_MESSAGE = 10 # Telegram allows a max of 10 images per call

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
    """Extract the post title and image URLs."""
    post_title_data = soup.select_one("body > main > div.post > h1.post-title")
    post_title = post_title_data.text if post_title_data else "Untitled Post"
    img_tags = soup.select("body > main > div.post > blockquote > p > img")
    image_urls = [requests.compat.urljoin(post_url, img.get('src')) for img in img_tags if img.get('src')]
    return post_title, image_urls


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for MarkdownV2."""
    special_chars = r'_\*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)


def prepare_caption(title: str, url: str) -> str:
    """Get the pieces together to format the text to be sent."""
    return escape_markdown_v2(f"{title} - Essa Semana no GNOME\n{url}")


def send_images_with_caption(bot_token, chat_id, image_urls, caption):
    """
    Sends multiple images to a Telegram chat with a caption on the first image.
    """
    if not image_urls:
        print("No images to send.")
        return

    telegram_api_url = f"https://api.telegram.org/bot{bot_token}/sendMediaGroup"

    media_group = []
    for index, img_url in enumerate(image_urls[:MAX_IMAGES_PER_MESSAGE]):  
        media_item = {"type": "photo", "media": img_url}
        
        # Add the caption only to the first image
        if index == 0:
            media_item["caption"] = caption
            media_item["parse_mode"] = "MarkdownV2"
        
        media_group.append(media_item)
    
    payload = {"chat_id": chat_id, "media": media_group}

    # Send the media group request
    try:
        requests.post(telegram_api_url, json=payload)
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

    post_title, image_urls = extract_post_data(soup, post_url)

    #print(f"post_title: {post_title}")
    #print(f"image_urls: {image_urls}")

    caption = prepare_caption(post_title, post_url)

    #print(text)
    #print(f"# of chars: {len(text)}")

    send_images_with_caption(BOT_TOKEN, CHAT_ID, image_urls, caption)


if __name__ == "__main__":
    main()
