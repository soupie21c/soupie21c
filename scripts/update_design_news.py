from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
FEEDS = (
    ("https://uxdesign.cc/feed", "UX Collective", True),
    ("https://www.smashingmagazine.com/feed/", "Smashing Magazine", False),
)
KEYWORDS = ("ux", "user", "design", "product", "interface", "research", "accessibility", "figma", "typography", "service design")
EXCLUDED = ("wallpaper", "desktop wallpaper", "job board")
START = "<!-- DESIGN_NEWS:START -->"
END = "<!-- DESIGN_NEWS:END -->"
USER_AGENT = "soupie21c-profile-news/1.0"


def text_of(parent, name):
    element = parent.find(name)
    return unescape(element.text or "").strip() if element is not None else ""


def translate_title(title):
    query = urllib.parse.urlencode({"q": title, "langpair": "en|ko"})
    request = urllib.request.Request(
        f"https://api.mymemory.translated.net/get?{query}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
        translated = result.get("responseData", {}).get("translatedText", "").strip()
        if result.get("responseStatus") == 200 and translated and not translated.startswith("MYMEMORY WARNING"):
            return unescape(translated)
    except Exception as error:
        print(f"Could not translate article title: {error}")
    return title


def fetch_feed(url, source, broad):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())

    articles = []
    for item in root.findall("./channel/item"):
        title = text_of(item, "title")
        link = text_of(item, "link")
        date_text = text_of(item, "pubDate")
        category_text = " ".join(category.text or "" for category in item.findall("category"))
        searchable = f"{title} {category_text}".lower()
        if not title or not link or any(word in searchable for word in EXCLUDED):
            continue
        if not broad and not any(word in searchable for word in KEYWORDS):
            continue
        try:
            published = parsedate_to_datetime(date_text)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            published = datetime.min.replace(tzinfo=timezone.utc)
        articles.append((published, title, link, source))
    return articles


def main():
    articles = []
    for url, source, broad in FEEDS:
        try:
            articles.extend(fetch_feed(url, source, broad))
        except Exception as error:
            print(f"Could not read {source}: {error}")

    articles.sort(key=lambda article: article[0], reverse=True)
    articles = articles[:3]
    if not articles:
        raise SystemExit("No news articles found; leaving README unchanged.")

    lines = []
    for published, title, link, source in articles:
        korean_title = translate_title(title)
        safe_title = korean_title.replace("[", "\\[").replace("]", "\\]")
        date = published.astimezone(timezone.utc).strftime("%Y-%m-%d")
        lines.append(f"- [{safe_title}]({link}) · {source} · {date}")

    readme = README.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    replacement = f"{START}\n" + "\n".join(lines) + f"\n{END}"
    updated, count = pattern.subn(lambda _: replacement, readme, count=1)
    if count != 1:
        raise SystemExit("News markers not found exactly once; leaving README unchanged.")
    if updated != readme:
        README.write_text(updated, encoding="utf-8")
        print(f"Updated README with {len(articles)} articles.")
    else:
        print("README already contains the latest articles.")


if __name__ == "__main__":
    main()
