from urllib.request import Request, urlopen
from urllib.parse import urljoin
from xml.etree import ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime
import json, re, html

FEEDS = [
    ("国内", "デジタル庁", "https://www.digital.go.jp/rss/news.xml"),
    ("国内", "総務省統計局", "https://www.stat.go.jp/whatsnew/news.rdf"),
    ("お金", "日本銀行", "https://www.boj.or.jp/rss/whatsnew.xml"),
    ("お金", "日本銀行 統計", "https://www.boj.or.jp/rss/statistics.xml"),
    ("お金", "金融庁", "https://www.fsa.go.jp/fsaNewsListAll_rss2.xml"),
]

def text_of(node, names):
    for name in names:
        el = node.find(name)
        if el is not None and el.text:
            return el.text.strip()
    return ""

def clean(s):
    s = html.unescape(s or "")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()

def fmt_date(raw):
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", raw)
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else raw[:25]

def fetch(category, source, url):
    req = Request(url, headers={"User-Agent":"wakaru-news/1.0"})
    with urlopen(req, timeout=30) as r:
        root = ET.fromstring(r.read())

    out = []
    # RSS 2.0
    nodes = root.findall(".//item")
    # Atom
    if not nodes:
        nodes = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    for n in nodes[:20]:
        title = clean(text_of(n, ["title", "{http://www.w3.org/2005/Atom}title"]))
        link = text_of(n, ["link"])
        if not link:
            le = n.find("{http://www.w3.org/2005/Atom}link")
            if le is not None:
                link = le.attrib.get("href","")
        date = text_of(n, [
            "pubDate",
            "{http://purl.org/dc/elements/1.1/}date",
            "{http://www.w3.org/2005/Atom}updated",
            "{http://www.w3.org/2005/Atom}published"
        ])
        if title and link:
            out.append({
                "category": category,
                "source": source,
                "title": title,
                "link": urljoin(url, link),
                "date": fmt_date(date)
            })
    return out

# 「ニュース一覧」に不要な事務連絡を除外
EXCLUDE_WORDS = [
    "一般競争入札", "企画競争", "調達", "入札公告", "落札",
    "採用情報", "職員採用", "非常勤職員",
    "ダッシュボードを更新", "ページを更新", "掲載しました",
    "募集を開始", "意見募集", "パブリックコメント",
    "仕様書", "公募", "契約"
]

def is_newsworthy(item):
    title = item.get("title", "")
    return not any(word in title for word in EXCLUDE_WORDS)

items = []
errors = []
for feed in FEEDS:
    try:
        items.extend(fetch(*feed))
    except Exception as e:
        errors.append(f"{feed[1]}: {e}")

# 事務連絡を除外
items = [x for x in items if is_newsworthy(x)]

# 重複除去
seen = set()
unique = []
for x in items:
    key = (x["title"], x["link"])
    if key not in seen:
        seen.add(key)
        unique.append(x)

payload = {
    "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "items": unique,
    "errors": errors
}
with open("data/news.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
print(f"{len(unique)} items", errors)
