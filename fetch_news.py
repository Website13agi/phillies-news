import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone


MLB_URL = "https://www.mlb.com/phillies/news"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def fetch_news():

    response = requests.get(
        MLB_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    articles = []
    seen_urls = set()

    # MLBニュースページ内の記事カードを探す
    for article in soup.find_all("article"):

        link = article.find(
            "a",
            href=True
        )

        if not link:
            continue

        href = link.get("href")

        if not href:
            continue

        # Phillies記事だけ
        if "/phillies/news/" not in href:
            continue

        # 完全URL
        if href.startswith("/"):
            href = (
                "https://www.mlb.com"
                + href
            )

        # 重複除外
        if href in seen_urls:
            continue

        seen_urls.add(href)

        # 記事カード内の見出しを探す
        title_element = article.find(
            ["h1", "h2", "h3", "h4"]
        )

        if title_element:

            title = title_element.get_text(
                " ",
                strip=True
            )

        else:

            title = link.get_text(
                " ",
                strip=True
            )

        # 「続きを読む」などを除外
        if not title:
            continue

        if title in [
            "続きを読む",
            "Read More",
            "Read more"
        ]:
            continue

        # 明らかにボタンの場合も除外
        if len(title) < 10:
            continue

        print(
            "取得:",
            title
        )

        articles.append({

            "id":
                len(articles) + 1,

            "title_en":
                title,

            "title_ja":
                title,

            "url":
                href,

            "source":
                "MLB.com",

            "fetched_at":
                datetime.now(
                    timezone.utc
                ).isoformat()

        })

        # 最大30記事
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

        "articles":
            articles

    }

    with open(
        "news.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"{len(articles)} articles saved."
    )


if __name__ == "__main__":
    main()
