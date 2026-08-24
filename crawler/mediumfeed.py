import hashlib
import html as htmllib
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

from . import painpoints

PLATFORM = "medium"
TIME_DELTAS = {
    "hour": 3600,
    "day": 86400,
    "week": 604800,
    "month": 2592000,
    "year": 31536000,
}


def _clean(text):
    if not text:
        return ""
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", str(text)))
    return re.sub(r"\s+", " ", text).strip()


def _parse_rfc822(s):
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (TypeError, ValueError):
        return 0.0


def _fetch_tag_feed(tag):
    resp = requests.get(
        f"https://medium.com/feed/tag/{urllib.parse.quote(tag)}",
        timeout=30,
        headers={"User-Agent": "painpoint-crawler/0.1"},
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    ns = {"content": "http://purl.org/rss/1.0/modules/content/",
          "dc": "http://purl.org/dc/elements/1.1/"}
    items = []
    for item in root.iter("item"):
        items.append({
            "title": item.findtext("title") or "",
            "link": item.findtext("link") or "",
            "pubDate": item.findtext("pubDate") or "",
            "author": item.findtext("dc:creator", default="", namespaces=ns),
            "content": item.findtext("content:encoded", default="", namespaces=ns)
                       or item.findtext("description") or "",
            "categories": [c.text for c in item.findall("category") if c.text][:3],
        })
    return items


def _record(item, tag, query=None):
    title = item.get("title") or ""
    content = _clean(item.get("content"))
    tags = ",".join(item.get("categories") or [tag])
    pain, matched = painpoints.analyze_text(f"{title}\n{content}")
    link = item.get("link")
    rid = hashlib.md5((link or title).encode()).hexdigest()[:12]
    return {
        "id": f"md_{rid}",
        "platform": PLATFORM,
        "subreddit": tags or tag or "medium",
        "title": title,
        "selftext": content[:5000],
        "author": item.get("author") or "[deleted]",
        "url": link,
        "created_utc": _parse_rfc822(item.get("pubDate")),
        "collected_at": time.time(),
        "score": 0,
        "num_comments": 0,
        "upvote_ratio": 0.0,
        "pain_score": painpoints.final_score(pain, 0, 0),
        "matched_keywords": ",".join(matched),
        "query": query or "",
        "comments": "",
    }


def discover(tag=None, limit=100, time_filter="week",
             with_comments=False, comments_limit=5):
    if not tag:
        return []
    after = time.time() - TIME_DELTAS.get(time_filter, TIME_DELTAS["week"])
    items = _fetch_tag_feed(tag)
    posts = [_record(i, tag) for i in items
             if _parse_rfc822(i.get("pubDate")) >= after]
    return posts[:limit]


def search(query, limit=100, time_filter="week", **_):
    raise NotImplementedError
