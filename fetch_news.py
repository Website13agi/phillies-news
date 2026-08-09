import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
from urllib.parse import urljoin
import time


MLB_URL = "https://www.mlb.com/phillies/news"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


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


        # ① og:title
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


        # ② h1
        h1 = soup.find("h1")

        if h1:

            title = h1.get_text(
                " ",
                strip=True
            )

            if title:
                return title


        # ③ titleタグ
        if soup.title:

            title = soup.title.get_text(
                " ",
                strip=True
            )

            if title:

                # MLB | MLB.com のような部分を除去
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
# ニュース一覧から記事URLを取得
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
    seen = set()


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


        # 重複除外
        if href in seen:
            continue


        seen.add(href)

        urls.append(href)


        if len(urls) >= 30:
            break


    return urls


# =========================================================
# ニュース取得
# =========================================================

def fetch_news():

    urls = get_article_urls()

    articles = []


    for url in urls:

        print(
            "記事:",
            url
        )


        title = get_article_title(
            url
        )


        if not title:

            print(
                "タイトルを取得できませんでした"
            )

            continue


        # 「続きを読む」などは除外
        if title in [
            "続きを読む",
            "Read More",
            "Read more"
        ]:

            continue


        print(
            "タイトル:",
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
                url,

            "source":
                "MLB.com",

            "fetched_at":
                datetime.now(
                    timezone.utc
                ).isoformat()

        })


        # MLBサーバーへのアクセス間隔
        time.sleep(0.5)


        if len(articles) >= 30:
            break


    return articles


# =========================================================
# JSON保存
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
        f"{len(articles)} articles saved."
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()
