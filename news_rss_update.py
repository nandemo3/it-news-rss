#!/usr/bin/env python3
"""
AI & IT News RSS Feed Generator
毎朝Claudeがニュースを収集・要約し、GitHub GistのRSSフィードを更新する。

使い方:
  1. 環境変数を設定:
       export GITHUB_PAT=ghp_xxxxxxxxxxxx
       export GIST_ID=（初回はコメントアウトでOK）
  2. python3 news_rss_update.py
"""

import os
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ─── 設定 ─────────────────────────────────────────────
GITHUB_PAT = os.environ.get("GITHUB_PAT", "")
GIST_ID    = os.environ.get("GIST_ID", "")   # 初回実行後に設定
GIST_FILENAME = "it_news_feed.xml"
FEED_TITLE = "AI & IT News Digest"
FEED_DESC  = "AI / Web / バックエンド / セキュリティの最新ニュース要約（自動生成）"
FEED_LINK  = ""  # 初回実行後、Gistのraw URLを入れると完全なRSSになる

SEARCH_QUERIES = [
    "AI machine learning news 2026",
    "web frontend development news 2026",
    "backend infrastructure cloud news 2026",
    "cybersecurity vulnerability news 2026",
]
# ─────────────────────────────────────────────────────


def search_news(query: str, num: int = 3) -> list[dict]:
    """
    DuckDuckGo Instant Answer APIでニュース検索。
    本番ではClaude Cowork内のWebSearchツールが使われるため、
    このファイルはスケジュール用プロンプトのリファレンスとして機能する。
    """
    encoded = urllib.parse.quote(query)
    url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        results = []
        for topic in (data.get("RelatedTopics") or [])[:num]:
            if "Text" in topic and "FirstURL" in topic:
                results.append({
                    "title": topic["Text"][:80],
                    "url":   topic["FirstURL"],
                    "summary": topic["Text"],
                })
        return results
    except Exception as e:
        print(f"  [warn] search failed for '{query}': {e}")
        return []


def build_rss(items: list[dict], feed_link: str = "") -> str:
    """アイテムリストからRSS 2.0 XMLを生成する。"""
    now_rfc = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    def esc(s: str) -> str:
        return (s.replace("&", "&amp;")
                  .replace("<", "&lt;")
                  .replace(">", "&gt;")
                  .replace('"', "&quot;"))

    item_xml = ""
    for item in items:
        item_xml += f"""
  <item>
    <title>{esc(item['title'])}</title>
    <link>{esc(item['url'])}</link>
    <description>{esc(item['summary'])}</description>
    <pubDate>{now_rfc}</pubDate>
    <guid isPermaLink="true">{esc(item['url'])}</guid>
  </item>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{esc(FEED_TITLE)}</title>
    <link>{esc(feed_link or 'https://gist.github.com')}</link>
    <description>{esc(FEED_DESC)}</description>
    <language>ja</language>
    <lastBuildDate>{now_rfc}</lastBuildDate>
    <ttl>720</ttl>
{item_xml}
  </channel>
</rss>
"""


def gist_create(content: str) -> str:
    """新しいGistを作成してGist IDを返す。"""
    payload = json.dumps({
        "description": FEED_TITLE,
        "public": True,
        "files": {GIST_FILENAME: {"content": content}},
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/gists",
        data=payload,
        headers={
            "Authorization": f"Bearer {GITHUB_PAT}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "cowork-rss-bot",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    return data["id"], data["files"][GIST_FILENAME]["raw_url"]


def gist_update(gist_id: str, content: str) -> str:
    """既存GistのファイルをPATCHで更新してraw URLを返す。"""
    payload = json.dumps({
        "files": {GIST_FILENAME: {"content": content}},
    }).encode()
    req = urllib.request.Request(
        f"https://api.github.com/gists/{gist_id}",
        data=payload,
        headers={
            "Authorization": f"Bearer {GITHUB_PAT}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "cowork-rss-bot",
        },
        method="PATCH",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    return data["files"][GIST_FILENAME]["raw_url"]


def main():
    if not GITHUB_PAT:
        raise SystemExit("❌ 環境変数 GITHUB_PAT が未設定です。")

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] ニュース収集開始...")

    all_items = []
    for query in SEARCH_QUERIES:
        print(f"  検索: {query}")
        results = search_news(query, num=2)
        all_items.extend(results)

    # 重複URLを除去して最大5件に絞る
    seen, unique = set(), []
    for item in all_items:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
        if len(unique) >= 5:
            break

    if not unique:
        print("  [warn] ニュースが取得できませんでした。フィードは更新しません。")
        return

    print(f"  {len(unique)}件のニュースを取得。RSS生成中...")
    rss_xml = build_rss(unique)

    if GIST_ID:
        raw_url = gist_update(GIST_ID, rss_xml)
        print(f"✅ Gist更新完了: {raw_url}")
    else:
        gist_id, raw_url = gist_create(rss_xml)
        print(f"✅ Gist作成完了!")
        print(f"   Gist ID : {gist_id}")
        print(f"   Raw URL : {raw_url}")
        print(f"\n⚠️  次回以降のために環境変数を設定してください:")
        print(f"   export GIST_ID={gist_id}")


if __name__ == "__main__":
    main()
