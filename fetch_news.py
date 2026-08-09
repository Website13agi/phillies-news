import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
from urllib.parse import urljoin, quote
import time
import re


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
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        translated = (
            data
            .get("responseData", {})
            .get("translatedText", "")
        )

        if translated:
            return translated.strip()

    except Exception as error:

        print("翻訳エラー:", error)

    return text


# =========================================================
# URL正規化
# =========================================================

def normalize_url(url):

    if not url:
        return ""

    url = url.split("?")[0]
    url = url.rstrip("/")

    return url


# =========================================================
# 記事ページからタイトル取得
# =========================================================

def get_article_title(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # og:title
        og_title = soup.find(
            "meta",
            property="og:title"
        )

        if og_title:

            title = og_title.get(
                "content",
                ""
            ).strip()

            if title:
                return title

        # h1
        h1 = soup.find("h1")

        if h1:

            title = h1.get_text(
                " ",
                strip=True
            )

            if title:
                return title

        # titleタグ
        if soup.title:

            title = soup.title.get_text(
                " ",
                strip=True
            )

            if title:

                title = title.split("|")[0].strip()

                if title:
                    return title

    except Exception as error:

        print(
            "タイトル取得エラー:",
            error
        )

    return None


# =========================================================
# ニュースURL取得
# =========================================================

def get_article_urls():

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

    urls = []
    seen_urls = set()

    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link.get("href")

        if not href:
            continue

        if "/phillies/news/" not in href:
            continue

        href = urljoin(
            "https://www.mlb.com",
            href
        )

        normalized_url = normalize_url(
            href
        )

        if not normalized_url:
            continue

        if normalized_url in seen_urls:
            continue

        seen_urls.add(
            normalized_url
        )

        urls.append(
            normalized_url
        )

        if len(urls) >= 40:
            break

    return urls


# =========================================================
# タイトル正規化
# =========================================================

def normalize_title(title):

    if not title:
        return ""

    title = title.lower()

    title = re.sub(
        r"[^a-z0-9\s]",
        "",
        title
    )

    title = re.sub(
        r"\s+",
        " ",
        title
    )

    return title.strip()


# =========================================================
# ニュース取得
# =========================================================

def fetch_news():

    urls = get_article_urls()

    articles = []

    seen_urls = set()
    seen_titles = set()

    for url in urls:

        print("")
        print("記事URL:")
        print(url)

        normalized_url = normalize_url(
            url
        )

        # URL重複
        if normalized_url in seen_urls:

            print("URL重複 → スキップ")

            continue

        seen_urls.add(
            normalized_url
        )

        # タイトル取得
        title = get_article_title(
            normalized_url
        )

        if not title:

            print(
                "タイトル取得失敗 → スキップ"
            )

            continue

        # 不要タイトル除外
        if title.lower() in [
            "続きを読む",
            "read more",
            "read more..."
        ]:

            print(
                "無効タイトル → スキップ"
            )

            continue

        # タイトル重複
        title_key = normalize_title(
            title
        )

        if title_key in seen_titles:

            print(
                "タイトル重複 → スキップ"
            )

            continue

        seen_titles.add(
            title_key
        )

        print("英語:")
        print(title)

        # 日本語翻訳
        japanese_title = (
            translate_to_japanese(
                title
            )
        )

        print("日本語:")
        print(japanese_title)

        # 保存
        articles.append({

            "id": len(articles) + 1,

            "title_en": title,

            "title_ja": japanese_title,

            "url": normalized_url,

            "source": "MLB.com",

            "fetched_at": datetime.now(
                timezone.utc
            ).isoformat()

        })

        # 少し待つ
        time.sleep(0.5)

        # 最大30記事
        if len(articles) >= 30:
            break

    return articles


# =========================================================
# news.json保存
# =========================================================

def main():

    articles = fetch_news()

    data = {

        "updated_at": datetime.now(
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

    print("")
    print("==============================")
    print(
        f"{len(articles)} articles saved."
    )
    print("==============================")


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
