#!/usr/bin/env python3
"""
AI & IT News RSS Feed Generator (無料版)
既存のRSSフィードから記事を収集してfeed.xmlを生成する。
APIキー不要。GitHub Actionsから毎朝実行される。
"""

import os
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from email.utils import formatdate, parsedate_to_datetime
import xml.etree.ElementTree as ET

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "feed.xml")

FEED_TITLE = "AI & IT News Digest"
FEED_DESC  = "AI / Web / バックエンド / セキュリティの最新ニュース要約（自動生成）"

# 収集元RSSフィード（ジャンルごと）
SOURCE_FEEDS = [
    # AI / 機械学習
    {"url": "https://feeds.feedburner.com/venturebeat/SZYF", "genre": "AI"},
    {"url": "https://www.artificialintelligence-news.com/feed/", "genre": "AI"},
    # Web / フロントエンド
    {"url": "https://css-tricks.com/feed/", "genre": "Web"},
    {"url": "https://feeds.feedburner.com/smashingmagazine", "genre": "Web"},
    # バックエンド / インフラ
    {"url": "https://devops.com/feed/", "genre": "バックエンド"},
    {"url": "https://www.infoq.com/feed/", "genre": "バックエンド"},
    # セキュリティ
    {"url": "https://feeds.feedburner.com/TheHackersNews", "genre": "セキュリティ"},
    {"url": "https://www.bleepingcomputer.com/feed/", "genre": "セキュリティ"},
]

MAX_ITEMS = 5          # 最終的に含める記事数
MAX_PER_FEED = 2       # 1フィードから取得する最大記事数


def fetch_feed(url: str) -> list[dict]:
    """URLからRSSを取得してアイテムリストを返す。"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; RSSBot/1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
    except Exception as e:
        print(f"  [skip] {url}: {e}")
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"  [skip] parse error {url}: {e}")
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []

    # RSS 2.0
    for item in root.findall(".//item")[:MAX_PER_FEED]:
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link")  or "").strip()
        desc  = (item.findtext("description") or "").strip()
        pub   = item.findtext("pubDate") or ""
        if title and link:
            items.append({"title": title, "url": link, "summary": _clean(desc), "pubDate": pub})

    # Atom
    if not items:
        for entry in root.findall(".//atom:entry", ns)[:MAX_PER_FEED]:
            title   = (entry.findtext("atom:title", namespaces=ns) or "").strip()
            link_el = entry.find("atom:link", ns)
            link    = (link_el.get("href") if link_el is not None else "") or ""
            summary = (entry.findtext("atom:summary", namespaces=ns) or "").strip()
            pub     = entry.findtext("atom:updated", namespaces=ns) or ""
            if title and link:
                items.append({"title": title, "url": link, "summary": _clean(summary), "pubDate": pub})

    return items


def _clean(html: str) -> str:
    """HTMLタグを除去して最初の150文字を返す。"""
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:150] + "…" if len(text) > 150 else text


def collect_news() -> list[dict]:
    """各フィードから記事を収集し、ジャンルバランスを保ちつつMAX_ITEMS件返す。"""
    by_genre: dict[str, list[dict]] = {}

    for source in SOURCE_FEEDS:
        genre = source["genre"]
        print(f"  取得中: [{genre}] {source['url']}")
        articles = fetch_feed(source["url"])
        by_genre.setdefault(genre, []).extend(articles)

    # ジャンルを均等にサンプリング
    result, seen_urls = [], set()
    genres = list(by_genre.keys())
    idx = 0
    while len(result) < MAX_ITEMS:
        genre = genres[idx % len(genres)]
        candidates = [a for a in by_genre.get(genre, []) if a["url"] not in seen_urls]
        if candidates:
            article = candidates[0]
            by_genre[genre].remove(article)
            seen_urls.add(article["url"])
            article["genre"] = genre
            result.append(article)
        idx += 1
        # 全ジャンル枯渇したら終了
        if all(not [a for a in v if a["url"] not in seen_urls] for v in by_genre.values()):
            break

    return result


def build_feed_xml(items: list[dict], feed_url: str = "") -> str:
    """アイテムリストからRSS 2.0 XMLを生成する。"""
    now_rfc = formatdate(usegmt=True)

    def esc(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    items_xml = ""
    for item in items:
        items_xml += f"""
    <item>
      <title>{esc(item['title'])}</title>
      <link>{esc(item['url'])}</link>
      <description>{esc(item.get('summary', ''))}</description>
      <pubDate>{now_rfc}</pubDate>
      <guid isPermaLink="true">{esc(item['url'])}</guid>
      <category>{esc(item.get('genre', ''))}</category>
    </item>"""

    atom_link = f'<atom:link href="{esc(feed_url)}" rel="self" type="application/rss+xml"/>' if feed_url else ""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{esc(FEED_TITLE)}</title>
    <link>{esc(feed_url or 'https://github.com')}</link>
    <description>{esc(FEED_DESC)}</description>
    <language>ja</language>
    <lastBuildDate>{now_rfc}</lastBuildDate>
    <ttl>720</ttl>
    {atom_link}
{items_xml}
  </channel>
</rss>
"""


def main():
    feed_url = os.environ.get("FEED_URL", "")

    print("ニュース収集中...")
    items = collect_news()

    if not items:
        raise SystemExit("❌ 記事が1件も取得できませんでした。")

    print(f"\n{len(items)}件取得:")
    for item in items:
        print(f"  [{item.get('genre', '')}] {item['title'][:60]}")

    xml_content = build_feed_xml(items, feed_url)

    output_path = os.path.abspath(OUTPUT_PATH)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_content)

    print(f"\n✅ feed.xml を保存しました: {output_path}")


if __name__ == "__main__":
    main()