#!/usr/bin/env python3
"""
AI & IT News RSS Feed Generator
Claude APIでニュースを収集・要約し、feed.xmlを生成する。
GitHub Actionsから毎朝実行される。
"""

import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import formatdate
import anthropic

FEED_TITLE = "AI & IT News Digest"
FEED_DESC  = "AI / Web / バックエンド / セキュリティの最新ニュース要約（自動生成）"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "feed.xml")


def collect_and_summarize() -> list[dict]:
    """Claude APIでニュースを収集・要約して返す。"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    today = datetime.now(timezone.utc).strftime("%Y年%m月%d日")

    prompt = f"""今日は{today}です。以下4つのジャンルから合計3〜5件の最新ニュースを収集・要約してください。

## 対象ジャンル
1. AI / 機械学習（LLM, 生成AI, ChatGPT, Gemini等）
2. Web / フロントエンド（React, Next.js, ブラウザ, CSS等）
3. バックエンド / インフラ（API, クラウド, DB, DevOps等）
4. セキュリティ（脆弱性, CVE, サイバー攻撃等）

## 出力形式（JSON配列のみ、他のテキスト不要）
[
  {{
    "title": "日本語タイトル（50文字以内）",
    "url": "元記事のURL",
    "summary": "日本語要約（100〜150文字）",
    "genre": "AI/Web/バックエンド/セキュリティのいずれか"
  }}
]

## 条件
- 実在する記事のURLを使うこと
- 各ジャンルから最低1件
- 重複URLは除外
- JSON以外のテキストは出力しない"""

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 8,
        }],
        messages=[{"role": "user", "content": prompt}],
    )

    # レスポンスからJSONを抽出
    for block in response.content:
        if block.type == "text":
            text = block.text.strip()
            # JSON部分を抽出
            start = text.find("[")
            end   = text.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])

    raise ValueError("Claude APIからJSONが取得できませんでした")


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
      <description>{esc(item['summary'])}</description>
      <pubDate>{now_rfc}</pubDate>
      <guid isPermaLink="true">{esc(item['url'])}</guid>
      <category>{esc(item.get('genre', ''))}</category>
    </item>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{esc(FEED_TITLE)}</title>
    <link>{esc(feed_url)}</link>
    <description>{esc(FEED_DESC)}</description>
    <language>ja</language>
    <lastBuildDate>{now_rfc}</lastBuildDate>
    <ttl>720</ttl>
    {f'<atom:link href="{esc(feed_url)}" rel="self" type="application/rss+xml"/>' if feed_url else ''}
{items_xml}
  </channel>
</rss>
"""


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("❌ 環境変数 ANTHROPIC_API_KEY が未設定です。")

    feed_url = os.environ.get("FEED_URL", "")

    print("ニュース収集中...")
    items = collect_and_summarize()
    print(f"{len(items)}件取得:")
    for item in items:
        print(f"  [{item.get('genre','')}] {item['title']}")

    xml_content = build_feed_xml(items, feed_url)

    output_path = os.path.abspath(OUTPUT_PATH)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_content)

    print(f"✅ feed.xml を保存しました: {output_path}")


if __name__ == "__main__":
    main()
