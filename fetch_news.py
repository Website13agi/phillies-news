```python
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
from urllib.parse import urljoin, quote
import time
import re
import hashlib


# =========================================================
# 設定
# =========================================================

MLB_URL = "https://www.mlb.com/phillies/news"

BASE_URL = "https://www.mlb.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


# =========================================================
# セッション
# =========================================================

session = requests.Session()

session.headers.update(
    HEADERS
)


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
            "?q="
            + encoded_text
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
# 安定した記事ID
#
# URLから生成するので、
# 毎回ニュース取得してもIDが変わらない
# =========================================================

def make_article_id(url):

    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()[:16]


# =========================================================
# 日時をISO形式に変換
# =========================================================

def normalize_datetime(value):

    if not value:
        return None

    if isinstance(value, list):

        if not value:
            return None

        value = value[0]

    if not isinstance(value, str):
        return None

    value = value.strip()

    if not value:
        return None


    # HTMLエンティティ等を除去
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


    # Published / Updated 等
    value = re.sub(
        r"^(published|updated|posted)\s*:?\s*",
        "",
        value,
        flags=re.IGNORECASE
    ).strip()


    # -----------------------------------------------------
    # ISO 8601
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # 英語日時
    #
    # August 9, 2026 7:32 PM
    # Aug 9, 2026 7:32 PM
    # August 9, 2026
    # -----------------------------------------------------

    patterns = [

        (
            r"%B %d, %Y %I:%M %p"
        ),

        (
            r"%b %d, %Y %I:%M %p"
        ),

        (
            r"%B %d, %Y"
        ),

        (
            r"%b %d, %Y"
        ),

    ]


    clean_value = re.sub(
        r"\bat\b",
        "",
        value,
        flags=re.IGNORECASE
    )

    clean_value = re.sub(
        r"\s+",
        " ",
        clean_value
    ).strip()


    for pattern in patterns:

        try:

            dt = datetime.strptime(
                clean_value,
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
# JSON-LDから公開日時を探す
#
# datePublishedだけを使用
# dateModified/dateCreatedは公開日時として使わない
# =========================================================

def find_date_in_jsonld(data):

    if isinstance(data, dict):

        # 最優先
        value = data.get(
            "datePublished"
        )

        if value:

            return value


        # mainEntity
        main_entity = data.get(
            "mainEntity"
        )

        if isinstance(
            main_entity,
            (dict, list)
        ):

            result = (
                find_date_in_jsonld(
                    main_entity
                )
            )

            if result:
                return result


        # article
        article = data.get(
            "article"
        )

        if isinstance(
            article,
            (dict, list)
        ):

            result = (
                find_date_in_jsonld(
                    article
                )
            )

            if result:
                return result


        # @graph
        graph = data.get(
            "@graph"
        )

        if isinstance(
            graph,
            list
        ):

            result = (
                find_date_in_jsonld(
                    graph
                )
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
# metaタグから公開日時
# =========================================================

def find_date_in_meta(soup):

    candidates = [

        # OpenGraph
        (
            "meta",
            {
                "property":
                    "article:published_time"
            }
        ),

        (
            "meta",
            {
                "property":
                    "og:published_time"
            }
        ),

        # itemprop
        (
            "meta",
            {
                "itemprop":
                    "datePublished"
            }
        ),

        (
            "meta",
            {
                "itemprop":
                    "datepublished"
            }
        ),

        # name
        (
            "meta",
            {
                "name":
                    "date"
            }
        ),

        (
            "meta",
            {
                "name":
                    "publishdate"
            }
        ),

        (
            "meta",
            {
                "name":
                    "publish-date"
            }
        ),

        (
            "meta",
            {
                "name":
                    "published"
            }
        ),

        (
            "meta",
            {
                "name":
                    "published_at"
            }
        ),

        (
            "meta",
            {
                "name":
                    "datepublished"
            }
        ),

    ]


    for tag_name, attrs in candidates:

        tag = soup.find(
            tag_name,
            attrs=attrs
        )

        if not tag:
            continue


        value = (
            tag.get("content")
            or tag.get("datetime")
            or tag.get("value")
        )


        if not value:
            continue


        normalized = (
            normalize_datetime(
                value
            )
        )


        if normalized:

            return normalized


    return None


# =========================================================
# timeタグから公開日時
# =========================================================

def find_date_in_time_tags(soup):

    for tag in soup.find_all(
        "time"
    ):

        # datetime属性
        value = tag.get(
            "datetime"
        )


        if value:

            normalized = (
                normalize_datetime(
                    value
                )
            )

            if normalized:

                return normalized


        # timeタグの本文
        text = tag.get_text(
            " ",
            strip=True
        )


        if text:

            normalized = (
                normalize_datetime(
                    text
                )
            )

            if normalized:

                return normalized


    return None


# =========================================================
# ページ内テキストから日時を探す
# =========================================================

def find_date_in_text(soup):

    # body全体ではなく、
    # まず記事上部を重点的に探す

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
        r"(?:\.\d+)?"
        r"(?:Z|[+-]\d{2}:?\d{2})?",

        text

    )


    for value in iso_matches:

        normalized = (
            normalize_datetime(
                value
            )
        )

        if normalized:

            return normalized


    # -----------------------------------------------------
    # Month DD, YYYY HH:MM AM/PM
    # -----------------------------------------------------

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

        r"\s*(AM|PM)"

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


        normalized = (
            normalize_datetime(
                value
            )
        )


        if normalized:

            return normalized


    # -----------------------------------------------------
    # Month DD, YYYY
    # -----------------------------------------------------

    pattern_date_only = (

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
        pattern_date_only,
        text,
        re.IGNORECASE
    )


    for match in matches:

        value = (
            f"{match[0]} "
            f"{match[1]}, "
            f"{match[2]}"
        )


        normalized = (
            normalize_datetime(
                value
            )
        )


        if normalized:

            return normalized


    return None


# =========================================================
# ページから公開日時を総当たり
# =========================================================

def find_published_date(soup):

    methods = [

        (
            "JSON-LD",
            lambda:
                find_date_in_jsonld_page(
                    soup
                )
        ),

        (
            "META",
            lambda:
                find_date_in_meta(
                    soup
                )
        ),

        (
            "TIME",
            lambda:
                find_date_in_time_tags(
                    soup
                )
        ),

        (
            "TEXT",
            lambda:
                find_date_in_text(
                    soup
                )
        ),

    ]


    for name, function in methods:

        try:

            value = function()


            if value:

                print(
                    "日時取得方法:",
                    name
                )

                return value

        except Exception as error:

            print(
                "日時取得エラー:",
                name,
                error
            )


    return None


# =========================================================
# JSON-LDページ専用処理
# =========================================================

def find_date_in_jsonld_page(soup):

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


            raw = raw.strip()


            # 不正JSON対策
            raw = re.sub(
                r"^\s*<!--",
                "",
                raw
            )

            raw = re.sub(
                r"-->\s*$",
                "",
                raw
            )


            data = json.loads(
                raw
            )


            value = (
                find_date_in_jsonld(
                    data
                )
            )


            if value:

                normalized = (
                    normalize_datetime(
                        value
                    )
                )


                if normalized:

                    return normalized


        except Exception:

            continue


    return None


# =========================================================
# タイトル取得
# =========================================================

def get_title(soup):

    # -----------------------------------------------------
    # og:title
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # twitter:title
    # -----------------------------------------------------

    tag = soup.find(
        "meta",
        name="twitter:title"
    )


    if tag:

        value = tag.get(
            "content"
        )


        if value:

            return value.strip()


    # -----------------------------------------------------
    # h1
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # title
    # -----------------------------------------------------

    if soup.title:

        value = soup.title.get_text(
            " ",
            strip=True
        )


        if value:

            value = re.split(
                r"\s*\|\s*",
                value
            )[0].strip()


            if value:

                return value


    return None


# =========================================================
# 記事ページ取得
# =========================================================

def get_article_info(url):

    max_retries = 3


    for attempt in range(
        1,
        max_retries + 1
    ):

        try:

            print(
                f"記事ページ取得 "
                f"({attempt}/{max_retries})"
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


            # -------------------------------------------------
            # タイトル
            # -------------------------------------------------

            title = get_title(
                soup
            )


            # -------------------------------------------------
            # 公開日時
            # -------------------------------------------------

            published_at = (
                find_published_date(
                    soup
                )
            )


            # -------------------------------------------------
            # 結果
            # -------------------------------------------------

            print(
                "タイトル:",
                title
            )


            if published_at:

                print(
                    "公開日時:",
                    published_at
                )

            else:

                print(
                    "公開日時: 取得できず"
                )


            return (
                title,
                published_at
            )


        except Exception as error:

            print(
                "記事情報取得エラー:",
                error
            )


            if attempt < max_retries:

                time.sleep(
                    2 * attempt
                )


    return (
        None,
        None
    )


# =========================================================
# ニュース一覧ページからURL取得
# =========================================================

def get_article_urls():

    max_retries = 3


    for attempt in range(
        1,
        max_retries + 1
    ):

        try:

            print(
                f"ニュース一覧取得 "
                f"({attempt}/{max_retries})"
            )


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


                # Philliesの記事
                if "/phillies/news/" not in href:
                    continue


                href = urljoin(
                    BASE_URL,
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


        except Exception as error:

            print(
                "ニュース一覧取得エラー:",
                error
            )


            if attempt < max_retries:

                time.sleep(
                    2 * attempt
                )


    return []


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


    print("")
    print(
        f"取得対象URL: {len(urls)}"
    )
    print("")


    articles = []

    seen_urls = set()
    seen_titles = set()


    for index, url in enumerate(
        urls,
        start=1
    ):

        print("")
        print(
            "================================"
        )
        print(
            f"記事 {index}/{len(urls)}"
        )
        print(
            "================================"
        )


        normalized_url = (
            normalize_url(
                url
            )
        )


        # -----------------------------------------------------
        # URL重複
        # -----------------------------------------------------

        if normalized_url in seen_urls:

            print(
                "URL重複 → スキップ"
            )

            continue


        seen_urls.add(
            normalized_url
        )


        # -----------------------------------------------------
        # 記事ページ
        # -----------------------------------------------------

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


        # -----------------------------------------------------
        # 無効タイトル
        # -----------------------------------------------------

        if title.lower() in [
            "続きを読む",
            "read more",
            "read more..."
        ]:

            print(
                "無効タイトル → スキップ"
            )

            continue


        # -----------------------------------------------------
        # タイトル重複
        # -----------------------------------------------------

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


        # -----------------------------------------------------
        # 日本語翻訳
        # -----------------------------------------------------

        print("")
        print(
            "英語タイトル:"
        )
        print(
            title
        )


        japanese_title = (
            translate_to_japanese(
                title
            )
        )


        print("")
        print(
            "日本語タイトル:"
        )
        print(
            japanese_title
        )


        # -----------------------------------------------------
        # ID
        #
        # URLベースなので毎回変わらない
        # -----------------------------------------------------

        article_id = (
            make_article_id(
                normalized_url
            )
        )


        # -----------------------------------------------------
        # 記事保存
        # -----------------------------------------------------

        articles.append({

            "id":
                article_id,

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


        # -----------------------------------------------------
        # 次の記事まで少し待つ
        # -----------------------------------------------------

        time.sleep(
            0.8
        )


        if len(articles) >= 30:

            break


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
        "Phillies News Fetcher"
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
    # 結果確認
    # =====================================================

    with_date = 0
    without_date = 0


    for article in articles:

        if article.get(
            "published_at"
        ):

            with_date += 1

        else:

            without_date += 1


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
        f"記事数: {len(articles)}"
    )

    print(
        f"公開日時取得成功: {with_date}"
    )

    print(
        f"公開日時取得失敗: {without_date}"
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
