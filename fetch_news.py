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

MLB_NEWS_URL = "https://www.mlb.com/phillies/news"
MLB_VIDEO_URL = "https://www.mlb.com/phillies/video"

BASE_URL = "https://www.mlb.com"

MAX_ARTICLES = 50

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

```
if not url:
    return ""

url = url.split("?")[0]
url = url.split("#")[0]
url = url.rstrip("/")

return url
```

# =========================================================

# 安定した記事ID

# URLが同じなら毎回同じIDになる

# =========================================================

def make_article_id(url):

```
return hashlib.sha256(
    url.encode("utf-8")
).hexdigest()[:16]
```

# =========================================================

# 日時をISO形式へ変換

# =========================================================

def normalize_datetime(value):

```
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


patterns = [

    "%B %d, %Y %I:%M %p",
    "%b %d, %Y %I:%M %p",

    "%B %d, %Y",
    "%b %d, %Y",

]


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
```

# =========================================================

# JSON-LDからdatePublishedを探す

# =========================================================

def search_jsonld_date(data):

```
if isinstance(data, dict):

    # datePublishedのみを公開日時として採用
    value = data.get(
        "datePublished"
    )

    if value:

        return value


    # @graph
    graph = data.get(
        "@graph"
    )

    if isinstance(
        graph,
        (dict, list)
    ):

        result = search_jsonld_date(
            graph
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
```

# =========================================================

# JSON-LDから日時取得

# =========================================================

def get_date_from_jsonld(soup):

```
scripts = soup.find_all(
    "script",
    type="application/ld+json"
)

for script in scripts:

    try:

        raw = (
            script.string
            or script.get_text()
        )

        if not raw:
            continue

        raw = raw.strip()

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
```

# =========================================================

# Metaタグから日時取得

# =========================================================

def get_date_from_meta(soup):

```
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
        "itemprop":
            "datepublished"
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
```

# =========================================================

# timeタグから日時取得

# =========================================================

def get_date_from_time(soup):

```
for tag in soup.find_all("time"):

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
```

# =========================================================

# ページ内テキストから日時取得

# =========================================================

def get_date_from_text(soup):

```
# まず記事本文全体から探す
text = soup.get_text(
    " ",
    strip=True
)


# =====================================================
# ISO形式
# =====================================================

iso_pattern = (
    r"\b20\d{2}-\d{2}-\d{2}"
    r"(?:T|\s)"
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
# 日付のみ
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
```

# =========================================================

# 公開日時取得

# =========================================================

def get_published_date(soup):

```
methods = [

    (
        "JSON-LD",
        get_date_from_jsonld
    ),

    (
        "META",
        get_date_from_meta
    ),

    (
        "TIME",
        get_date_from_time
    ),

    (
        "TEXT",
        get_date_from_text
    ),

]


for name, function in methods:

    try:

        date = function(
            soup
        )

        if date:

            print(
                "日時取得方法:",
                name
            )

            return date

    except Exception as error:

        print(
            "日時取得エラー:",
            name,
            error
        )


print(
    "日時取得: 不明"
)

return None
```

# =========================================================

# タイトル取得

# =========================================================

def get_title(soup):

```
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
        )[0].strip()

        if value:

            return value


return None
```

# =========================================================

# 記事・動画ページ取得

# =========================================================

def get_page_info(url):

```
for attempt in range(1, 4):

    try:

        print(
            f"ページ取得 {attempt}/3"
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

        if attempt < 3:

            time.sleep(
                2 * attempt
            )


return (
    None,
    None
)
```

# =========================================================

# URL一覧取得共通処理

# =========================================================

def get_urls_from_page(
page_url,
url_pattern,
max_count=40
):

```
for attempt in range(1, 4):

    try:

        print(
            f"一覧取得 {attempt}/3:",
            page_url
        )

        response = session.get(
            page_url,
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

            # 絶対URLへ変換
            url = urljoin(
                BASE_URL,
                href
            )

            url = normalize_url(
                url
            )

            if not url:
                continue

            # 対象ページだけ
            if url_pattern not in url:
                continue

            if url in seen:
                continue

            seen.add(
                url
            )

            urls.append(
                url
            )

            if len(urls) >= max_count:

                break

        return urls

    except Exception as error:

        print(
            "一覧取得エラー:",
            error
        )

        if attempt < 3:

            time.sleep(
                2 * attempt
            )


return []
```

# =========================================================

# ニュースURL

# =========================================================

def get_news_urls():

```
return get_urls_from_page(
    MLB_NEWS_URL,
    "/phillies/news/",
    40
)
```

# =========================================================

# 動画URL

# =========================================================

def get_video_urls():

```
return get_urls_from_page(
    MLB_VIDEO_URL,
    "/phillies/video/",
    40
)
```

# =========================================================

# タイトル重複判定

# =========================================================

def normalize_title(title):

```
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
```

# =========================================================

# 日本語翻訳

# =========================================================

def translate_to_japanese(text):

```
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


# 翻訳失敗時は英語タイトルを残す
return text
```

# =========================================================

# ニュース＋動画取得

# =========================================================

def fetch_news():

```
print("")
print(
    "ニュースURLを取得中..."
)

news_urls = get_news_urls()

print(
    f"ニュースURL: {len(news_urls)}"
)


print("")
print(
    "動画URLを取得中..."
)

video_urls = get_video_urls()

print(
    f"動画URL: {len(video_urls)}"
)


# =====================================================
# 取得対象をまとめる
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


for index, (
    url,
    content_type
) in enumerate(
    targets,
    start=1
):

    print("")
    print(
        "================================"
    )
    print(
        f"{index}/{len(targets)}"
    )
    print(
        "種類:",
        content_type
    )
    print(
        url
    )
    print(
        "================================"
    )


    # =================================================
    # URL重複
    # =================================================

    if url in seen_urls:

        print(
            "URL重複 → スキップ"
        )

        continue

    seen_urls.add(
        url
    )


    # =================================================
    # ページ取得
    # =================================================

    title, published_at = get_page_info(
        url
    )


    if not title:

        print(
            "タイトル取得失敗 → スキップ"
        )

        continue


    # =================================================
    # 無効タイトル
    # =================================================

    invalid_titles = [

        "続きを読む",
        "read more",
        "read more...",
        "watch",
        "watch now"

    ]


    if title.strip().lower() in invalid_titles:

        print(
            "無効タイトル → スキップ"
        )

        continue


    # =================================================
    # タイトル重複
    # =================================================

    title_key = normalize_title(
        title
    )


    if title_key and title_key in seen_titles:

        print(
            "タイトル重複 → スキップ"
        )

        continue


    if title_key:

        seen_titles.add(
            title_key
        )


    # =================================================
    # 日本語タイトル
    # =================================================

    print(
        "日本語翻訳中..."
    )

    japanese_title = translate_to_japanese(
        title
    )


    # =================================================
    # 記事保存
    # =================================================

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


    print(
        "保存:",
        title
    )


    if published_at:

        print(
            "日時:",
            published_at
        )

    else:

        print(
            "日時: 不明"
        )


    time.sleep(
        0.8
    )


    if len(articles) >= MAX_ARTICLES:

        break


# =====================================================
# 公開日時順
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

        dt = datetime.fromisoformat(
            value
        )

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt

    except Exception:

        return datetime.min.replace(
            tzinfo=timezone.utc
        )


articles.sort(
    key=sort_key,
    reverse=True
)


return articles
```

# =========================================================

# JSON保存

# =========================================================

def main():

```
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
# 結果集計
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
```

# =========================================================

# START

# =========================================================

if **name** == "**main**":

```
main()
```
