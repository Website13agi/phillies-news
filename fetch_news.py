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

        print(
            "翻訳エラー:",
            error
        )

    # 翻訳できなかった場合は英語を残す
    return text


# =========================================================
# URLを正規化
# =========================================================

def normalize_url(url):

    if not url:
        return ""

    # クエリや末尾のスラッシュを除去
    url = url.split("?")[0]
    url = url.rstrip("/")

    return url


# =========================================================
# 記事ページから正式なタイトルを取得
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


        # -------------------------------------------------
        # ① og:title
        # -------------------------------------------------

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


        # -------------------------------------------------
        # ② h1
        # -------------------------------------------------

        h1 = soup.find("h1")

        if h1:

            title = h1.get_text(
                " ",
                strip=True
            )

            if title:

                return title


        # -------------------------------------------------
        # ③ titleタグ
        # -------------------------------------------------

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
# ニュース記事URLを取得
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


        # Philliesニュース記事だけ
        if "/phillies/news/" not in href:
            continue


        # 完全URL
        href = urljoin(
            "https://www.mlb.com",
            href
        )


        # URL正規化
        normalized =
            normalize_url(href)


        if not normalized:
            continue


        # URLによる重複除去
        if normalized in seen_urls:
            continue


        seen_urls.add(
            normalized
        )


        urls.append(
            normalized
        )


        # 最大40記事取得
        if len(urls) >= 40:
            break


    return urls


# =========================================================
# タイトルの重複を判定するための正規化
# =========================================================

def normalize_title(title):

    if not title:
        return ""

    title = title.lower()

    # 記号を除去
    title = re.sub(
        r"[^a-z0-9\s]",
        "",
        title
    )

    # 連続スペースを1つに
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

        print(
            "記事:",
            url
        )


        # -------------------------------------------------
        # URL重複チェック
        # -------------------------------------------------

        normalized_url =
            normalize_url(url)


        if normalized_url in seen_urls:

            print(
                "重複URL → スキップ"
            )

            continue


        seen_urls.add(
            normalized_url
        )


        # -------------------------------------------------
        # タイトル取得
        # -------------------------------------------------

        title = get_article_title(
            normalized_url
        )


        if not title:

            print(
                "タイトル取得失敗 → スキップ"
            )

            continue


        # -------------------------------------------------
        # 「続きを読む」などを除外
        # -------------------------------------------------

        if title.lower() in [
            "続きを読む",
            "read more",
            "read more..."
        ]:

            print(
                "無効なタイトル → スキップ"
            )

            continue


        # -------------------------------------------------
        # タイトル重複チェック
        # -------------------------------------------------

        title_key =
            normalize_title(title)


        if title_key in seen_titles:

            print(
                "重複タイトル → スキップ"
            )

            continue


        seen_titles.add(
            title_key
        )


        print(
            "英語:",
            title
        )


        # -------------------------------------------------
        # 日本語翻訳
        # -------------------------------------------------

        japanese_title =
            translate_to_japanese(
                title
            )


        print(
            "日本語:",
            japanese_title
        )


        # -------------------------------------------------
        # 記事データ
        # -------------------------------------------------

        articles.append({

            "id":
                len(articles) + 1,

            "title_en":
                title,

            "title_ja":
                japanese_title,

            "url":
                normalized_url,

            "source":
                "MLB.com",

            "fetched_at":
                datetime.now(
                    timezone.utc
                ).isoformat()

        })


        # MLBサーバーへのアクセス間隔
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
        "================================"
    )

    print(
        f"{len(articles)} articles saved."
    )

    print(
        "================================"
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()
