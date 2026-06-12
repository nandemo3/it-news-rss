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

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..")

# ジャンル定義：(ジャンル名, ファイル名, タイトル, 収集元RSS)
GENRES = [
    {
        "genre":    "AI",
        "filename": "feed_ai.xml",
        "title":    "AI・機械学習 News Digest",
        "desc":     "AI・機械学習の最新ニュース（自動生成）",
        "sources":  [
            "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",
            "https://gigazine.net/news/rss_2.0/",
        ],
    },
    {
        "genre":    "Web",
        "filename": "feed_web.xml",
        "title":    "Web・フロントエンド News Digest",
        "desc":     "Web・フロントエンド開発の最新ニュース（自動生成）",
        "sources":  [
            "https://zenn.dev/feed",
            "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",
        ],
    },
    {
        "genre":    "バックエンド",
        "filename": "feed_backend.xml",
        "title":    "バックエンド・インフラ News Digest",
        "desc":     "バックエンド・インフラの最新ニュース（自動生成）",
        "sources":  [
            "https://developers.srad.jp/index.rss",
            "https://codezine.jp/rss/new/20/index.xml",
        ],
    },
    {
        "genre":    "セキュリティ",
        "filename": "feed_security.xml",
        "title":    "セキュリティ News Digest",
        "desc":     "セキュリティの最新ニュース（自動生成）",
        "sources":  [
            "https://www.security-next.com/feed",
            "https://rss.itmedia.co.jp/rss/2.0/security.xml",
        ],
    },
]

MAX_ITEMS = 1      # 1フィードファイルに含める記事数
MAX_PER_FEED = 3   # 1収集元から取得する最大記事数


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


def collect_news_for_genre(genre_def: dict) -> list[dict]:
    """1ジャンル分の記事をソースRSSから収集してMAX_ITEMS件返す。"""
    articles, seen_urls = [], set()
    for url in genre_def["sources"]:
        print(f"  取得中: [{genre_def['genre']}] {url}")
        for item in fetch_feed(url):
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                item["genre"] = genre_def["genre"]
                articles.append(item)
            if len(articles) >= MAX_ITEMS:
                break
        if len(articles) >= MAX_ITEMS:
            break
    return articles[:MAX_ITEMS]


def build_feed_xml(items: list[dict], title: str, desc: str, feed_url: str = "") -> str:
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
    <title>{esc(title)}</title>
    <link>{esc(feed_url or 'https://github.com')}</link>
    <description>{esc(desc)}</description>
    <language>ja</language>
    <lastBuildDate>{now_rfc}</lastBuildDate>
    <ttl>720</ttl>
    {atom_link}
{items_xml}
  </channel>
</rss>
"""


def main():
    base_url = os.environ.get("FEED_URL", "").rstrip("/")
    # FEED_URLがfeed.xmlで終わっている場合はディレクトリ部分だけ使う
    if base_url.endswith(".xml"):
        base_url = base_url.rsplit("/", 1)[0]

    output_dir = os.path.abspath(OUTPUT_DIR)
    os.makedirs(output_dir, exist_ok=True)

    print("ニュース収集中...\n")
    total = 0
    for genre_def in GENRES:
        items = collect_news_for_genre(genre_def)
        if not items:
            print(f"  ⚠️  [{genre_def['genre']}] 記事が取得できませんでした。スキップします。\n")
            continue

        feed_url = f"{base_url}/{genre_def['filename']}" if base_url else ""
        xml_content = build_feed_xml(items, genre_def["title"], genre_def["desc"], feed_url)

        output_path = os.path.join(output_dir, genre_def["filename"])
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        print(f"  ✅ [{genre_def['genre']}] {len(items)}件 → {genre_def['filename']}")
        total += len(items)

    if total == 0:
        raise SystemExit("❌ 全ジャンルで記事が取得できませんでした。")

    print(f"\n合計{total}件のニュースを保存しました。")


if __name__ == "__main__":
    main()