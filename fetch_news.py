import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
from urllib.parse import urljoin, quote
import time
import re
import hashlib

MLB_URL = "https://www.mlb.com/phillies/news"
BASE_URL = "https://www.mlb.com"

HEADERS = {
"User-Agent": "Mozilla/5.0"
}

session = requests.Session()
session.headers.update(HEADERS)

def translate_to_japanese(text):
if not text:
return ""

```
try:
    encoded_text = quote(text)

    url = (
        "https://api.mymemory.translated.net/get"
        "?q=" + encoded_text +
        "&langpair=en|ja"
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
    print("翻訳エラー:", error)

return text
```

def normalize_url(url):
if not url:
return ""

```
url = url.split("?")[0]
url = url.split("#")[0]
url = url.rstrip("/")

return url
```

def make_article_id(url):
return hashlib.sha256(
url.encode("utf-8")
).hexdigest()[:16]

def normalize_datetime(value):
if not value:
return None

```
if isinstance(value, list):
    if not value:
        return None
    value = value[0]

if not isinstance(value, str):
    return None

value = value.strip()

if not value:
    return None

value = value.replace(
    "&nbsp;",
    " "
)

value = value.replace(
    "\n",
    " "
)

value = value.replace(
    "\r",
    " "
)

value = re.sub(
    r"\s+",
    " ",
    value
).strip()

value = re.sub(
    r"^(published|posted)\s*:?\s*",
    "",
    value,
    flags=re.IGNORECASE
).strip()

if value.endswith("Z"):
    value = value[:-1] + "+00:00"

try:
    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    return dt.isoformat()

except Exception:
    pass

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
    "%b %d, %Y"
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
```

def find_date_in_jsonld(data):
if isinstance(data, dict):

```
    value = data.get(
        "datePublished"
    )

    if value:
        return value

    graph = data.get("@graph")

    if isinstance(graph, list):
        result = find_date_in_jsonld(
            graph
        )

        if result:
            return result

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
            result = find_date_in_jsonld(
                value
            )

            if result:
                return result

elif isinstance(data, list):

    for item in data:
        result = find_date_in_jsonld(
            item
        )

        if result:
            return result

return None
```

def find_date_in_jsonld_page(soup):
scripts = soup.find_all(
"script",
type="application/ld+json"
)

```
for script in scripts:

    try:
        raw = (
            script.string
            or script.get_text()
        )

        if not raw:
            continue

        data = json.loads(
            raw.strip()
        )

        value = find_date_in_jsonld(
            data
        )

        if value:
            return normalize_datetime(
                value
            )

    except Exception:
        continue

return None
```

def find_date_in_meta(soup):
candidates = [
("property", "article:published_time"),
("property", "og:published_time"),
("itemprop", "datePublished"),
("itemprop", "datepublished"),
("name", "date"),
("name", "publishdate"),
("name", "publish-date"),
("name", "published"),
("name", "published_at")
]

```
for attribute, value in candidates:

    tag = soup.find(
        "meta",
        attrs={
            attribute: value
        }
    )

    if not tag:
        continue

    date_value = (
        tag.get("content")
        or tag.get("datetime")
        or tag.get("value")
    )

    if date_value:

        normalized = normalize_datetime(
            date_value
        )

        if normalized:
            return normalized

return None
```

def find_date_in_time_tags(soup):
for tag in soup.find_all("time"):

```
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

def find_date_in_text(soup):
text = soup.get_text(
" ",
strip=True
)

```
iso_matches = re.findall(
    r"\b20\d{2}-\d{2}-\d{2}"
    r"(?:T|\s)"
    r"\d{2}:\d{2}"
    r"(?::\d{2})?"
    r"(?:Z|[+-]\d{2}:?\d{2})?",
    text
)

for value in iso_matches:

    normalized = normalize_datetime(
        value
    )

    if normalized:
        return normalized

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

    normalized = normalize_datetime(
        value
    )

    if normalized:
        return normalized

return None
```

def find_published_date(soup):

```
value = find_date_in_jsonld_page(
    soup
)

if value:
    print("日時取得: JSON-LD")
    return value

value = find_date_in_meta(
    soup
)

if value:
    print("日時取得: META")
    return value

value = find_date_in_time_tags(
    soup
)

if value:
    print("日時取得: TIME")
    return value

value = find_date_in_text(
    soup
)

if value:
    print("日時取得: TEXT")
    return value

print("日時取得: 不明")

return None
```

def get_title(soup):

```
tag = soup.find(
    "meta",
    property="og:title"
)

if tag and tag.get("content"):
    return tag.get(
        "content"
    ).strip()

tag = soup.find(
    "meta",
    name="twitter:title"
)

if tag and tag.get("content"):
    return tag.get(
        "content"
    ).strip()

h1 = soup.find("h1")

if h1:

    title = h1.get_text(
        " ",
        strip=True
    )

    if title:
        return title

if soup.title:

    title = soup.title.get_text(
        " ",
        strip=True
    )

    if title:
        return title.split(
            "|"
        )[0].strip()

return None
```

def get_article_info(url):

```
for attempt in range(1, 4):

    try:

        print(
            f"記事取得 {attempt}/3"
        )

        response = session.get(
            url,
            timeout=30
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        title = get_title(
            soup
        )

        published_at = find_published_date(
            soup
        )

        return (
            title,
            published_at
        )

    except Exception as error:

        print(
            "記事取得エラー:",
            error
        )

        if attempt < 3:
            time.sleep(
                2 * attempt
            )

return None, None
```

def get_article_urls():

```
for attempt in range(1, 4):

    try:

        print(
            f"ニュース一覧取得 {attempt}/3"
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

            if len(urls) >= 40:
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

def fetch_news():

```
urls = get_article_urls()

print(
    f"取得対象: {len(urls)}記事"
)

articles = []

seen_urls = set()
seen_titles = set()

for url in urls:

    url = normalize_url(
        url
    )

    if url in seen_urls:
        continue

    seen_urls.add(url)

    title, published_at = get_article_info(
        url
    )

    if not title:
        print(
            "タイトル取得失敗 → スキップ"
        )
        continue

    if title.lower() in [
        "続きを読む",
        "read more",
        "read more..."
    ]:
        continue

    title_key = normalize_title(
        title
    )

    if title_key in seen_titles:
        continue

    seen_titles.add(
        title_key
    )

    print("")
    print(
        "英語タイトル:",
        title
    )

    if published_at:

        print(
            "公開日時:",
            published_at
        )

    else:

        print(
            "公開日時: 不明"
        )

    japanese_title = translate_to_japanese(
        title
    )

    print(
        "日本語タイトル:",
        japanese_title
    )

    articles.append({

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

        "published_at":
            published_at
    })

    time.sleep(0.8)

    if len(articles) >= 30:
        break

return articles
```

def main():

```
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

success = sum(
    1
    for article in articles
    if article.get(
        "published_at"
    )
)

unknown = (
    len(articles)
    - success
)

print("")
print(
    "=============================="
)
print(
    "取得完了"
)
print(
    f"記事数: {len(articles)}"
)
print(
    f"日時取得成功: {success}"
)
print(
    f"日時不明: {unknown}"
)
print(
    "=============================="
)
```

if **name** == "**main**":
main()
