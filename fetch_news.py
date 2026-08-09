```python
import requests
from bs4 import BeautifulSoup
import json
import re
import time
import hashlib
from datetime import datetime, timezone
from urllib.parse import urljoin, quote


# =========================================================
# 設定
# =========================================================

MLB_URL = "https://www.mlb.com/phillies/news"
MLB_VIDEO_URL = "https://www.mlb.com/phillies/video"

BASE_URL = "https://www.mlb.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# =========================================================
# Session
# =========================================================

session = requests.Session()
session.headers.update(HEADERS)


# =========================================================
# URL正規化
# =========================================================

def normalize_url(url):

    if not url:
        return ""

    url = url.split("?")[0]
    url = url.split("#")[0]
    url = url.rstrip("/")

    return url


# =========================================================
# 安定したID
# =========================================================

def make_article_id(url):

    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()[:16]


# =========================================================
# 日時変換
# =========================================================

def normalize_datetime(value):

    if not value:
        return None

    if not isinstance(value, str):
        return None

    value = value.strip()

    if not value:
        return None

    value = (
        value
        .replace("&nbsp;", " ")
        .replace("\n", " ")
        .replace("\r", " ")
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    ).strip()

    value = re.sub(
        r"^(published|updated|posted)\s*:?\s*",
        "",
        value,
        flags=re.IGNORECASE
    ).strip()


    # =====================================================
    # ISO 8601
    # =====================================================

    iso_value = value

    if iso_value.endswith("Z"):

        iso_value = (
            iso_value[:-1]
            + "+00:00"
        )

    try:

        dt = datetime.fromisoformat(
            iso_value
        )

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.isoformat()

    except Exception:
        pass


    # =====================================================
    # 英語日時
    # =====================================================

    value = re.sub(
        r"\bat\b",
        "",
        value,
        flags=re.IGNORECASE
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    ).strip()


    patterns = [

        "%B %d, %Y %I:%M %p",
        "%b %d, %Y %I:%M %p",

        "%B %d, %Y",
        "%b %d, %Y",

    ]


    for pattern in patterns:

        try:

            dt = datetime.strptime(
                value,
                pattern
            )

            dt = dt.replace(
                tzinfo=timezone.utc
            )

            return dt.isoformat()

        except Exception:
            continue


    return None


# =========================================================
# JSON-LD検索
# =========================================================

def search_jsonld_date(data):

    if isinstance(data, dict):

        # 公開日時だけを使用
        if data.get("datePublished"):

            return data.get(
                "datePublished"
            )


        # @graph
        if isinstance(
            data.get("@graph"),
            list
        ):

            result = search_jsonld_date(
                data["@graph"]
            )

            if result:
                return result


        # その他の入れ子
        for key, value in data.items():

            if key in [
                "dateModified",
                "dateCreated"
            ]:
                continue


            if isinstance(
                value,
                (dict, list)
            ):

                result = search_jsonld_date(
                    value
                )

                if result:
                    return result


    elif isinstance(data, list):

        for item in data:

            result = search_jsonld_date(
                item
            )

            if result:
                return result


    return None


# =========================================================
# JSON-LDから日時
# =========================================================

def get_date_from_jsonld(soup):

    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):

        try:

            raw = (
                script.string
                or script.get_text()
            )

            if not raw:
                continue

            data = json.loads(
                raw
            )

            value = search_jsonld_date(
                data
            )

            if value:

                normalized = normalize_datetime(
                    value
                )

                if normalized:
                    return normalized

        except Exception:
            continue


    return None


# =========================================================
# METAから日時
# =========================================================

def get_date_from_meta(soup):

    selectors = [

        {
            "property":
                "article:published_time"
        },

        {
            "property":
                "og:published_time"
        },

        {
            "itemprop":
                "datePublished"
        },

        {
            "name":
                "datePublished"
        },

        {
            "name":
                "publishdate"
        },

        {
            "name":
                "publish-date"
        },

        {
            "name":
                "published_at"
        },

        {
            "name":
                "published"
        },

    ]


    for attrs in selectors:

        tag = soup.find(
            "meta",
            attrs=attrs
        )

        if not tag:
            continue


        value = (
            tag.get("content")
            or tag.get("datetime")
            or tag.get("value")
        )


        normalized = normalize_datetime(
            value
        )


        if normalized:
            return normalized


    return None


# =========================================================
# TIMEタグから日時
# =========================================================

def get_date_from_time(soup):

    for tag in soup.find_all(
        "time"
    ):

        value = tag.get(
            "datetime"
        )


        if value:

            normalized = normalize_datetime(
                value
            )

            if normalized:
                return normalized


        text = tag.get_text(
            " ",
            strip=True
        )


        if text:

            normalized = normalize_datetime(
                text
            )

            if normalized:
                return normalized


    return None


# =========================================================
# ページ本文から日時
# =========================================================

def get_date_from_text(soup):

    text = soup.get_text(
        " ",
        strip=True
    )


    # =====================================================
    # ISO
    # =====================================================

    iso_pattern = (
        r"\b20\d{2}-\d{2}-\d{2}"
        r"T"
        r"\d{2}:\d{2}"
        r"(?::\d{2})?"
        r"(?:\.\d+)?"
        r"(?:Z|[+-]\d{2}:?\d{2})?"
    )


    matches = re.findall(
        iso_pattern,
        text
    )


    for value in matches:

        normalized = normalize_datetime(
            value
        )

        if normalized:
            return normalized


    # =====================================================
    # Month DD, YYYY HH:MM AM/PM
    # =====================================================

    pattern = (
        r"\b("
        r"January|February|March|April|May|June|"
        r"July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|"
        r"Oct|Nov|Dec"
        r")\s+"
        r"(\d{1,2}),\s+"
        r"(20\d{2})"
        r"(?:\s+at)?\s+"
        r"(\d{1,2}:\d{2})"
        r"\s*"
        r"(AM|PM)"
    )


    matches = re.findall(
        pattern,
        text,
        re.IGNORECASE
    )


    for match in matches:

        value = (
            f"{match[0]} "
            f"{match[1]}, "
            f"{match[2]} "
            f"{match[3]} "
            f"{match[4]}"
        )


        normalized = normalize_datetime(
            value
        )


        if normalized:
            return normalized


    # =====================================================
    # 日付だけ
    # =====================================================

    pattern_date = (
        r"\b("
        r"January|February|March|April|May|June|"
        r"July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|"
        r"Oct|Nov|Dec"
        r")\s+"
        r"(\d{1,2}),\s+"
        r"(20\d{2})"
    )


    matches = re.findall(
        pattern_date,
        text,
        re.IGNORECASE
    )


    for match in matches:

        value = (
            f"{match[0]} "
            f"{match[1]}, "
            f"{match[2]}"
        )


        normalized = normalize_datetime(
            value
        )


        if normalized:
            return normalized


    return None


# =========================================================
# 公開日時を総当たり
# =========================================================

def get_published_date(soup):

    # ① JSON-LD
    date = get_date_from_jsonld(
        soup
    )

    if date:

        print(
            "日時取得方法: JSON-LD"
        )

        return date


    # ② META
    date = get_date_from_meta(
        soup
    )

    if date:

        print(
            "日時取得方法: META"
        )

        return date


    # ③ TIME
    date = get_date_from_time(
        soup
    )

    if date:

        print(
            "日時取得方法: TIME"
        )

        return date


    # ④ 本文
    date = get_date_from_text(
        soup
    )

    if date:

        print(
            "日時取得方法: TEXT"
        )

        return date


    print(
        "日時取得: 不明"
    )

    return None


# =========================================================
# タイトル取得
# =========================================================

def get_title(soup):

    # og:title
    tag = soup.find(
        "meta",
        property="og:title"
    )


    if tag:

        value = tag.get(
            "content"
        )

        if value:
            return value.strip()


    # twitter:title
    tag = soup.find(
        "meta",
        attrs={
            "name":
                "twitter:title"
        }
    )


    if tag:

        value = tag.get(
            "content"
        )

        if value:
            return value.strip()


    # h1
    h1 = soup.find(
        "h1"
    )


    if h1:

        value = h1.get_text(
            " ",
            strip=True
        )

        if value:
            return value


    # title
    if soup.title:

        value = soup.title.get_text(
            " ",
            strip=True
        )


        if value:

            value = re.split(
                r"\s*\|\s*",
                value
            )[0]


            return value.strip()


    return None


# =========================================================
# 記事 / 動画ページ取得
# =========================================================

def get_page_info(url):

    for attempt in range(3):

        try:

            print(
                f"ページ取得 {attempt + 1}/3"
            )


            response = session.get(
                url,
                timeout=30,
                allow_redirects=True
            )


            response.raise_for_status()


            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )


            title = get_title(
                soup
            )


            published_at = get_published_date(
                soup
            )


            print(
                "タイトル:",
                title
            )


            print(
                "公開日時:",
                published_at
                if published_at
                else "日時不明"
            )


            return (
                title,
                published_at
            )


        except Exception as error:

            print(
                "ページ取得エラー:",
                error
            )


            time.sleep(
                2
            )


    return (
        None,
        None
    )


# =========================================================
# ニュース記事URL取得
# =========================================================

def get_news_urls():

    try:

        response = session.get(
            MLB_URL,
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

            href = link.get(
                "href"
            )


            if not href:
                continue


            if "/phillies/news/" not in href:
                continue


            url = urljoin(
                BASE_URL,
                href
            )


            url = normalize_url(
                url
            )


            if not url:
                continue


            if url in seen:
                continue


            seen.add(url)
            urls.append(url)


            if len(urls) >= 30:
                break


        return urls


    except Exception as error:

        print(
            "ニュース一覧取得エラー:",
            error
        )

        return []


# =========================================================
# 動画URL取得
# =========================================================

def get_video_urls():

    try:

        response = session.get(
            MLB_VIDEO_URL,
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

            href = link.get(
                "href"
            )


            if not href:
                continue


            if "/phillies/video/" not in href:
                continue


            url = urljoin(
                BASE_URL,
                href
            )


            url = normalize_url(
                url
            )


            if not url:
                continue


            if url in seen:
                continue


            seen.add(url)
            urls.append(url)


            if len(urls) >= 30:
                break


        return urls


    except Exception as error:

        print(
            "動画一覧取得エラー:",
            error
        )

        return []


# =========================================================
# タイトル重複判定
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
# 日本語翻訳
# =========================================================

def translate_to_japanese(text):

    if not text:
        return ""


    try:

        url = (
            "https://api.mymemory.translated.net/get"
            "?q="
            + quote(text)
            + "&langpair=en|ja"
        )


        response = session.get(
            url,
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


    return text


# =========================================================
# ニュース + 動画取得
# =========================================================

def fetch_news():

    print("")
    print(
        "ニュースURLを取得中..."
    )


    news_urls = get_news_urls()


    print(
        f"ニュース: {len(news_urls)}"
    )


    print("")
    print(
        "動画URLを取得中..."
    )


    video_urls = get_video_urls()


    print(
        f"動画: {len(video_urls)}"
    )


    # =====================================================
    # 記事と動画をまとめる
    # =====================================================

    targets = []


    for url in news_urls:

        targets.append(
            (
                url,
                "article"
            )
        )


    for url in video_urls:

        targets.append(
            (
                url,
                "video"
            )
        )


    articles = []

    seen_urls = set()
    seen_titles = set()


    for index, item in enumerate(
        targets,
        start=1
    ):

        url, content_type = item


        print("")
        print(
            "================================"
        )
        print(
            f"{index}/{len(targets)}"
        )
        print(
            content_type.upper()
        )
        print(
            url
        )
        print(
            "================================"
        )


        if url in seen_urls:
            continue


        seen_urls.add(url)


        title, published_at = get_page_info(
            url
        )


        if not title:
            continue


        # 無効タイトル
        if title.lower() in [
            "続きを読む",
            "read more",
            "read more..."
        ]:
            continue


        # タイトル重複
        title_key = normalize_title(
            title
        )


        if title_key in seen_titles:
            continue


        seen_titles.add(
            title_key
        )


        print(
            "日本語翻訳中..."
        )


        japanese_title = translate_to_japanese(
            title
        )


        article = {

            "id":
                make_article_id(url),

            "title_en":
                title,

            "title_ja":
                japanese_title,

            "url":
                url,

            "source":
                "MLB.com",

            "type":
                content_type,

            "published_at":
                published_at

        }


        articles.append(
            article
        )


        time.sleep(
            0.8
        )


        if len(articles) >= 50:
            break


    # =====================================================
    # 日時順
    # =====================================================

    def sort_key(article):

        value = article.get(
            "published_at"
        )


        if not value:
            return datetime.min.replace(
                tzinfo=timezone.utc
            )


        try:

            return datetime.fromisoformat(
                value
            )

        except Exception:

            return datetime.min.replace(
                tzinfo=timezone.utc
            )


    articles.sort(
        key=sort_key,
        reverse=True
    )


    return articles


# =========================================================
# JSON保存
# =========================================================

def main():

    print("")
    print(
        "================================"
    )
    print(
        "PHILLIES NEWS FETCHER"
    )
    print(
        "================================"
    )


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


    # =====================================================
    # 結果
    # =====================================================

    news_count = sum(
        1
        for article in articles
        if article.get("type") == "article"
    )


    video_count = sum(
        1
        for article in articles
        if article.get("type") == "video"
    )


    date_count = sum(
        1
        for article in articles
        if article.get("published_at")
    )


    unknown_count = (
        len(articles)
        - date_count
    )


    print("")
    print(
        "================================"
    )
    print(
        "取得完了"
    )
    print(
        "================================"
    )


    print(
        f"合計: {len(articles)}"
    )


    print(
        f"記事: {news_count}"
    )


    print(
        f"動画: {video_count}"
    )


    print(
        f"日時取得成功: {date_count}"
    )


    print(
        f"日時不明: {unknown_count}"
    )


    print(
        "================================"
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()
```
