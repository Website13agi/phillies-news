import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone

URL = "https://www.mlb.com/phillies/news"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def fetch_news():

    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    articles = []

    # MLBのニュース一覧から記事リンクを取得
    for link in soup.select("a[href*='/phillies/news/']"):

        href = link.get("href")

        title = link.get_text(
            " ",
            strip=True
        )

        if not href or not title:
            continue

        # 記事URLを完全なURLにする
        if href.startswith("/"):
            href = "https://www.mlb.com" + href

        # 不要なリンクを除外
        if href.rstrip("/") == URL.rstrip("/"):
            continue

        # 同じ記事の重複を除外
        if any(
            article["url"] == href
            for article in articles
        ):
            continue

        articles.append({

            "id": len(articles) + 1,

            "title_en": title,

            # 現段階では英語タイトルを仮表示
            # 次の段階で日本語翻訳を接続します
            "title_ja": title,

            "url": href,

            "source": "MLB.com",

            "fetched_at":
                datetime.now(
                    timezone.utc
                ).isoformat()

        })

        # 最初の30記事まで
        if len(articles) >= 30:
            break


    return articles


def main():

    articles = fetch_news()

    data = {

        "updated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "articles": articles

    }

    with open(
        "news.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"{len(articles)} articles saved."
    )


if __name__ == "__main__":
    main()
