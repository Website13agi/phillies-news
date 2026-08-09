import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
from urllib.parse import quote


MLB_URL = "https://www.mlb.com/phillies/news"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# =========================================================
# 日本語翻訳
# =========================================================

def translate_to_japanese(text):

    if not text:
        return ""

    try:

        encoded_text = quote(text)

        url = (
            "https://api.mymemory.translated.net/get"
            "?q=" + encoded_text
            + "&langpair=en|ja"
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        translated = (
            data
            .get("responseData", {})
            .get("translatedText", "")
        )

        if translated:
            return translated

    except Exception as error:

        print(
            "Translation error:",
            error
        )

    # 翻訳できなかった場合は英語タイトルを使用
    return text


# =========================================================
# MLBニュース取得
# =========================================================

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

    for link in soup.select(
        "a[href*='/phillies/news/']"
    ):

        href = link.get("href")

        title = link.get_text(
            " ",
            strip=True
        )

        if not href or not title:
            continue

        # 相対URLを完全なURLにする
        if href.startswith("/"):
            href = (
                "https://www.mlb.com"
                + href
            )

        # 一覧ページ自身を除外
        if (
            href.rstrip("/")
            == MLB_URL.rstrip("/")
        ):
            continue

        # 重複記事を除外
        if any(
            article["url"] == href
            for article in articles
        ):
            continue

        print(
            "取得:",
            title
        )

        # 日本語に翻訳
        japanese_title = (
            translate_to_japanese(title)
        )

        print(
            "翻訳:",
            japanese_title
        )

        articles.append({

            "id": len(articles) + 1,

            "title_en": title,

            "title_ja": japanese_title,

            "url": href,

            "source": "MLB.com",

            "fetched_at":
                datetime.now(
                    timezone.utc
                ).isoformat()

        })

        # 最大30記事
        if len(articles) >= 30:
            break

    return articles


# =========================================================
# news.json作成
# =========================================================

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


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
