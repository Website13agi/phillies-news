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
# 日時をISO形式に変換
# =========================================================

def normalize_datetime(value):

    if not value:
        return None

    value = value.strip()

    # 不要な文字を除去
    value = value.replace(
        "Published",
        ""
    ).strip()

    value = value.replace(
        "Updated",
        ""
    ).strip()

    try:

        if value.endswith("Z"):

            dt = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00"
                )
            )

        else:

            dt = datetime.fromisoformat(
                value
            )

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.isoformat()

    except Exception:

        return value


# =========================================================
# JSON-LDから日時を探す
# =========================================================

def find_date_in_jsonld(data):

    if isinstance(data, dict):

        # datePublishedを最優先
        if data.get("datePublished"):

            return data.get(
                "datePublished"
            )

        # dateCreated
        if data.get("dateCreated"):

            return data.get(
                "dateCreated"
            )

        # @graph
        if isinstance(
            data.get("@graph"),
            list
        ):

            for item in data["@graph"]:

                result = (
                    find_date_in_jsonld(
                        item
                    )
                )

                if result:
                    return result

        # 入れ子
        for value in data.values():

            if isinstance(
                value,
                (dict, list)
            ):

                result = (
                    find_date_in_jsonld(
                        value
                    )
                )

                if result:
                    return result


    elif isinstance(data, list):

        for item in data:

            result = (
                find_date_in_jsonld(
                    item
                )
            )

            if result:
                return result


    return None


# =========================================================
# ページ内テキストから日時を探す
# =========================================================

def find_date_in_text(soup):

    text = soup.get_text(
        " ",
        strip=True
    )


    # -----------------------------------------------------
    # ISO形式
    # -----------------------------------------------------

    iso_matches = re.findall(
        r"\b20\d{2}-\d{2}-\d{2}"
        r"(?:T|\s)"
        r"\d{2}:\d{2}"
        r"(?::\d{2})?"
        r"(?:Z|[+-]\d{2}:?\d{2})?",
        text
    )


    if iso_matches:

        return iso_matches[0]


    # -----------------------------------------------------
    # Month DD, YYYY HH:MM
    # 例:
    # August 9, 2026 7:32 PM
    # -----------------------------------------------------

    pattern = (
        r"\b("
        r"January|February|March|April|May|June|"
        r"July|August|September|October|November|December"
        r")\s+"
        r"(\d{1,2}),\s+"
        r"(20\d{2})"
        r"(?:\s+at)?\s+"
        r"(\d{1,2}:\d{2})"
        r"\s*(AM|PM)"
    )


    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )


    if match:

        return match.group(0)


    return None


# =========================================================
# 記事ページから情報取得
# =========================================================

def get_article_info(url):

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


        # =================================================
        # タイトル
        # =================================================

        title = None


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


        # h1
        if not title:

            h1 = soup.find("h1")

            if h1:

                title = h1.get_text(
                    " ",
                    strip=True
                )


        # title
        if not title and soup.title:

            title = soup.title.get_text(
                " ",
                strip=True
            )

            if title:

                title = title.split(
                    "|"
                )[0].strip()


        # =================================================
        # 公開日時
        # =================================================

        published_at = None


        # -------------------------------------------------
        # ① JSON-LD
        # -------------------------------------------------

        for script in soup.find_all(
            "script",
            type="application/ld+json"
        ):

            try:

                raw = (
                    script.string
                    or
                    script.get_text()
                )

                data = json.loads(raw)

                date_value = (
                    find_date_in_jsonld(
                        data
                    )
                )

                if date_value:

                    published_at = (
                        normalize_datetime(
                            date_value
                        )
                    )

                    break

            except Exception:

                continue


        # -------------------------------------------------
        # ② article:published_time
        # -------------------------------------------------

        if not published_at:

            tag = soup.find(
                "meta",
                property="article:published_time"
            )

            if tag:

                value = tag.get(
                    "content"
                )

                if value:

                    published_at = (
                        normalize_datetime(
                            value
                        )
                    )


        # -------------------------------------------------
        # ③ datePublished
        # -------------------------------------------------

        if not published_at:

            tag = soup.find(
                "meta",
                itemprop="datePublished"
            )

            if tag:

                value = (
                    tag.get("content")
                    or
                    tag.get("datetime")
                )

                if value:

                    published_at = (
                        normalize_datetime(
                            value
                        )
                    )


        # -------------------------------------------------
        # ④ timeタグ
        # -------------------------------------------------

        if not published_at:

            for tag in soup.find_all(
                "time"
            ):

                value = (
                    tag.get("datetime")
                )

                if value:

                    published_at = (
                        normalize_datetime(
                            value
                        )
                    )

                    if published_at:
                        break


        # -------------------------------------------------
        # ⑤ ページ内テキスト
        # -------------------------------------------------

        if not published_at:

            value = find_date_in_text(
                soup
            )

            if value:

                published_at = (
                    normalize_datetime(
                        value
                    )
                )


        return title, published_at


    except Exception as error:

        print(
            "記事情報取得エラー:",
            error
        )

        return None, None


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

        href = link.get(
            "href"
        )


        if not href:
            continue


        if "/phillies/news/" not in href:
            continue


        href = urljoin(
            "https://www.mlb.com",
            href
        )


        normalized_url = (
            normalize_url(
                href
            )
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


        normalized_url = (
            normalize_url(
                url
            )
        )


        # URL重複
        if normalized_url in seen_urls:

            print(
                "URL重複 → スキップ"
            )

            continue


        seen_urls.add(
            normalized_url
        )


        # 記事情報
        title, published_at = (
            get_article_info(
                normalized_url
            )
        )


        if not title:

            print(
                "タイトル取得失敗 → スキップ"
            )

            continue


        # 「続きを読む」除外
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


        # 公開日時
        print("公開日時:")


        if published_at:

            print(
                published_at
            )

        else:

            print(
                "取得できませんでした"
            )


        # 日本語
        japanese_title = (
            translate_to_japanese(
                title
            )
        )


        print("日本語:")
        print(japanese_title)


        # 記事保存
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

            "published_at":
                published_at

        })


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
