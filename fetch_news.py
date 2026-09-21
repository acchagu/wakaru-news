from urllib.request import Request, urlopen
from urllib.parse import urljoin
from xml.etree import ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime
from pathlib import Path
import json, re, html, os, time
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FEEDS = [
    ("国内", "デジタル庁", "https://www.digital.go.jp/rss/news.xml"),
    ("国内", "総務省統計局", "https://www.stat.go.jp/whatsnew/news.rdf"),
    ("お金", "日本銀行", "https://www.boj.or.jp/rss/whatsnew.xml"),
    ("お金", "日本銀行 統計", "https://www.boj.or.jp/rss/statistics.xml"),
    ("お金", "金融庁", "https://www.fsa.go.jp/fsaNewsListAll_rss2.xml"),
    ("海外", "国連ジュネーブ", "https://www.ungeneva.org/en/news-media/press-items-list/rss.xml"),
    ("ゲーム・IT", "任天堂", "https://www.nintendo.co.jp/news/whatsnew.xml"),
    ("ゲーム・IT", "Apple Newsroom", "https://www.apple.com/jp/newsroom/rss-feed.rss"),
]

EXCLUDE_WORDS = [
    "一般競争入札", "企画競争", "調達", "入札公告", "落札",
    "採用情報", "職員採用", "非常勤職員",
    "人事異動", "期間業務職員",
    "ダッシュボードを更新", "ページを更新", "掲載しました",
    "募集を開始", "意見募集", "パブリックコメント",
    "仕様書", "公募", "契約",
"対象商品", "商品一覧", "分析結果", "報告受付",
"説明会", "開催について", "更新しました"
]

RSS1 = "http://purl.org/rss/1.0/"
ATOM = "http://www.w3.org/2005/Atom"
DC = "http://purl.org/dc/elements/1.1/"

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
    req = Request(url, headers={"User-Agent": "wakaru-news/1.1"})
    with urlopen(req, timeout=30) as r:
        root = ET.fromstring(r.read())

    # RSS 2.0 -> RSS 1.0/RDF -> Atom
    nodes = root.findall(".//item")
    if not nodes:
        nodes = root.findall(f".//{{{RSS1}}}item")
    if not nodes:
        nodes = root.findall(f".//{{{ATOM}}}entry")

    out = []
    for n in nodes[:20]:
        title = clean(text_of(n, [
            "title",
            f"{{{RSS1}}}title",
            f"{{{ATOM}}}title",
        ]))

        link = text_of(n, [
            "link",
            f"{{{RSS1}}}link",
        ])
        if not link:
            le = n.find(f"{{{ATOM}}}link")
            if le is not None:
                link = le.attrib.get("href", "")

        date = text_of(n, [
            "pubDate",
            f"{{{DC}}}date",
            f"{{{ATOM}}}updated",
            f"{{{ATOM}}}published",
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

def is_newsworthy(item):
    title = item.get("title", "")
    return not any(word in title for word in EXCLUDE_WORDS)

def add_ai_explanation(item):
    if not GEMINI_API_KEY:
        return item

    prompt = f"""
次のニュースを、ニュースに詳しくない人でも理解できるように日本語で説明してください。

ニュース見出し：
{item['title']}

必ず次の形式で答えてください。

【何があった？】
専門用語をできるだけ使わず、2〜3行で簡単に説明する。

【たとえると？】
「ドラゴンクエスト、ドラゴンボール、ガンダム、キン肉マン、幽☆遊☆白書、ポケモン、ロックマン」
の中から、このニュースを説明するのに一番分かりやすい作品を1つだけ選んでたとえる。
原作のセリフを引用せず、設定や状況を使って説明する。

【つまり？】
上のたとえが、現実のニュースでは何を意味しているのか簡単に説明する。

【ワイに関係ある？】
一般の日本在住者の生活への影響を
「かなりある」「少しある」「ほぼない」
のどれかで示し、その理由を1〜2行で説明する。

難しい言葉を使った場合は、その場で意味も説明してください。
見出しだけでは分からない事実を勝手に作らないでください。
"""

    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    body = json.dumps(data).encode("utf-8")

    req = Request(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        }
    )

    for attempt in range(1):
                    try:
                        with urlopen(req, timeout=30) as r:
                            result = json.loads(r.read().decode("utf-8"))
                
                        explanation = result["candidates"][0]["content"]["parts"][0]["text"]
                        item["ai_explanation"] = explanation
                        break
                
                    except Exception as e:
                        print(f"Gemini API error (attempt {attempt + 1}/3): {e}")
                        if attempt < 2:
                            time.sleep(10)
    return item

            
items = []
errors = []

for feed in FEEDS:
    try:
        items.extend(fetch(*feed))
    except Exception as e:
        errors.append(f"{feed[1]}: {e}")

items = [x for x in items if is_newsworthy(x)]

seen = set()
unique = []
for x in items:
    key = (x["title"], x["link"])
    if key not in seen:
        seen.add(key)
        unique.append(x)

unique.sort(key=lambda x: x.get("date", ""), reverse=True)
old_explanations = {}

try:
    with open("data/explanations.json", "r", encoding="utf-8") as f:
        saved = json.load(f)
        for key, value in saved.items():
            old_explanations[key] = value
except Exception:
    pass



try:
    with open("data/news.json", "r", encoding="utf-8") as f:
        old_data = json.load(f)
    for old_item in old_data.get("items", []):
        if old_item.get("ai_explanation"):
            old_explanations[(old_item["title"], old_item["link"])] = old_item["ai_explanation"]
except Exception:
    pass
ai_added = False

for i in range(len(unique)):
    key = (unique[i]["title"], unique[i]["link"])

    if key in old_explanations:
        unique[i]["ai_explanation"] = old_explanations[key]

    elif not ai_added:
        unique[i] = add_ai_explanation(unique[i])

        if unique[i].get("ai_explanation"):
            ai_added = True
payload = {
    "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "items": unique,
    "errors": errors
}

Path("data").mkdir(exist_ok=True)
saved_explanations = {}
for x in unique:
    if x.get("ai_explanation"):
        saved_explanations[x["title"] + "||" + x["link"]] = x["ai_explanation"]

with open("data/explanations.json", "w", encoding="utf-8") as f:
    json.dump(saved_explanations, f, ensure_ascii=False, indent=2)
with open("data/news.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

print(f"{len(unique)} items", errors)
