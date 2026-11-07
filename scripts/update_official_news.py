#!/usr/bin/env python3
"""Refresh official finance headlines only; keep old timestamp on failure."""
import datetime as dt
import email.utils
import html
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

OUT = Path(__file__).resolve().parents[1] / "data" / "news.json"
FEEDS = [
    ("臺灣證券交易所", "https://www.twse.com.tw/rwd/zh/news/feed?type=rss", "twse.com.tw"),
    ("美國聯準會（原文英文）", "https://www.federalreserve.gov/feeds/press_monetary.xml", "federalreserve.gov"),
]

def allowed(link, domain):
    try:
        u = urlparse(link)
        return u.scheme == "https" and not (u.username or u.password) and (u.hostname == domain or (u.hostname or "").endswith("." + domain))
    except ValueError:
        return False

def get_child(node, key):
    for x in node:
        if x.tag.rsplit("}", 1)[-1].lower() == key:
            return x.attrib.get("href", "").strip() if key == "link" and x.attrib.get("href") else "".join(x.itertext()).strip()
    return ""

def tidy(s, limit):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html.unescape(s or ""))).strip()[:limit]

def parse_date(s):
    try:
        x = email.utils.parsedate_to_datetime(s)
    except (ValueError, TypeError):
        try:
            x = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
    return x.replace(tzinfo=dt.timezone.utc) if x.tzinfo is None else x.astimezone(dt.timezone.utc)

def fetch(source, url, domain, now):
    req = Request(url, headers={"User-Agent": "FamilyFinanceEducation/1.0", "Accept": "application/rss+xml, application/xml, text/xml"})
    with urlopen(req, timeout=16) as res:
        if not allowed(res.geturl(), domain):
            raise ValueError("unexpected redirect")
        data = res.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("RSS is too large")
    root = ET.fromstring(data)
    items = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1].lower() not in ("item", "entry"):
            continue
        title = tidy(get_child(node, "title"), 150)
        link = urljoin(url, get_child(node, "link"))
        day = parse_date(get_child(node, "pubdate") or get_child(node, "published") or get_child(node, "updated"))
        if not (title and allowed(link, domain) and day and now - dt.timedelta(days=180) < day < now + dt.timedelta(days=2)):
            continue
        desc = tidy(get_child(node, "description") or get_child(node, "summary"), 110)
        items.append({"title": title, "link": link, "date": day.isoformat(timespec="seconds"), "source": source, "snippet": "" if desc == title else desc})
    if not items:
        raise ValueError("no valid dated official news")
    return items

def main():
    now = dt.datetime.now(dt.timezone.utc)
    try:
        old = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    articles, failed, success = [], [], []
    for source, url, domain in FEEDS:
        try:
            got = fetch(source, url, domain, now)
            articles.extend(got)
            success.append(source)
            print("OK", source, len(got))
        except Exception as err:
            failed.append(source)
            print("WARN", source, str(err))
    if success:
        for article in old.get("articles", []):
            if article.get("source") in failed:
                date = parse_date(article.get("date", ""))
                if date and now - date < dt.timedelta(days=7):
                    articles.append(article)
        unique = {x["link"]: x for x in articles}
        pools = {}
        for item in sorted(unique.values(), key=lambda x: x["date"], reverse=True):
            pools.setdefault(item["source"], []).append(item)
        selected = []
        for source, _, _ in FEEDS:
            selected.extend(pools.get(source, [])[:6])
        used = {item["link"] for item in selected}
        selected.extend(item for item in sorted(unique.values(), key=lambda x: x["date"], reverse=True) if item["link"] not in used)
        result = {"updated_at": now.isoformat(timespec="seconds"), "articles": sorted(selected[:12], key=lambda x: x["date"], reverse=True)}
    else:
        result = {"updated_at": old.get("updated_at"), "articles": old.get("articles", [])}
    result["attempted_at"] = now.isoformat(timespec="seconds")
    result["failed_sources"] = failed
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Articles:", len(result["articles"]), "Failed:", failed)

if __name__ == "__main__":
    main()
