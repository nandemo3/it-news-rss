# セットアップ手順

## ファイル構成

```
it-news-rss/                     ← GitHubリポジトリ名（任意）
├── .github/
│   └── workflows/
│       └── rss.yml              ← GitHub Actionsワークフロー
├── scripts/
│   └── generate_rss.py          ← ニュース収集・RSS生成スクリプト
├── feed.xml                     ← 自動生成されるRSSフィード（初回は空でOK）
└── index.html                   ← GitHub Pages用トップページ
```

---

## Step 1：GitHubリポジトリを作成

1. https://github.com/new を開く
2. Repository name: `it-news-rss`（任意）
3. **Public** を選択（GitHub Pages無料利用のため）
4. **Create repository**

---

## Step 2：ファイルをpush

ローカルで以下を実行：

```bash
git clone https://github.com/あなたのユーザー名/it-news-rss.git
cd it-news-rss

# ダウンロードしたファイルをコピー
cp -r /path/to/downloaded/. .

# 空のfeed.xmlを作成（初回用）
echo '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>AI &amp; IT News Digest</title></channel></rss>' > feed.xml

git add .
git commit -m "initial commit"
git push origin main
```

---

## Step 3：GitHub Secretsを設定

リポジトリページ → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-xxxxxxxxxxxx`（Anthropic APIキー） |
| `FEED_URL` | `https://あなたのユーザー名.github.io/it-news-rss/feed.xml` |

---

## Step 4：GitHub Pagesを有効化

リポジトリページ → **Settings** → **Pages**

- Source: **Deploy from a branch**
- Branch: `main` / `/ (root)`
- **Save**

数分後に `https://あなたのユーザー名.github.io/it-news-rss/` で公開される。

---

## Step 5：手動で初回テスト実行

リポジトリページ → **Actions** → **Daily RSS Feed Update** → **Run workflow**

成功すると `feed.xml` が更新されてcommitが作られる。

---

## RSSフィードURL

```
https://あなたのユーザー名.github.io/it-news-rss/feed.xml
```

FeedlyやReederなどのRSSリーダーにこのURLを登録すれば完成。

---

## スケジュール

毎朝8時JST（UTC 23時）に自動実行される。  
ワークフローファイルの `cron: '0 23 * * *'` を変更すれば時間を調整できる。
