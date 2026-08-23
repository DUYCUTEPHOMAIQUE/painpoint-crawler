import html as htmllib
import re
import time

import requests

from . import painpoints

BASE_URL = "https://hn.algolia.com/api/v1"
PLATFORM = "hn"
TIME_DELTAS = {
    "hour": 3600,
    "day": 86400,
    "week": 604800,
    "month": 2592000,
    "year": 31536000,
}


def _get(path, params=None):
    resp = requests.get(f"{BASE_URL}{path}", params=params or {}, timeout=30,
                        headers={"User-Agent": "painpoint-crawler/0.1"})
    resp.raise_for_status()
    return resp.json()


def _clean(text):
    if not text:
        return ""
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", str(text)))
    return re.sub(r"\s+", " ", text).strip()


def _record(hit, query=None, comments=None):
    hid = str(hit.get("objectID") or hit.get("story_id") or "")
    title = _clean(hit.get("title")) or _clean(hit.get("story_title")) or "(không tiêu đề)"
    body = _clean(hit.get("story_text"))
    ups = hit.get("points") or 0
    n_comments = hit.get("num_comments") or 0
    pain, matched = painpoints.analyze_text(f"{title}\n{body}")
    if comments:
        c_pain, c_matched = painpoints.analyze_text("\n".join(comments))
        pain = round(pain + 0.5 * c_pain, 2)
        matched = list(dict.fromkeys(matched + c_matched))
    return {
        "id": f"hn_{hid}",
        "platform": PLATFORM,
        "subreddit": "hn",
        "title": title,
        "selftext": body[:5000],
        "author": hit.get("author") or "[deleted]",
        "url": f"https://news.ycombinator.com/item?id={hid}",
        "created_utc": float(hit.get("created_at_i") or 0),
        "collected_at": time.time(),
        "score": int(ups),
        "num_comments": int(n_comments),
        "upvote_ratio": 0.0,
        "pain_score": painpoints.final_score(pain, n_comments, ups),
        "matched_keywords": ",".join(matched),
        "query": query or "",
        "comments": "\n---\n".join(comments) if comments else "",
    }


def discover(limit=100, time_filter="week", min_points=20,
             with_comments=False, comments_limit=5):
    after = int(time.time() - TIME_DELTAS.get(time_filter, TIME_DELTAS["week"]))
    filters = [f"created_at_i>{after}"]
    if min_points:
        filters.append(f"points>={int(min_points)}")
    params = {"tags": "story", "hitsPerPage": min(limit, 100),
              "numericFilters": ",".join(filters)}
    hits = _get("/search_by_date", params).get("hits", [])
    posts = []
    for hit in hits:
        comments = None
        if with_comments:
            comments = fetch_comments(hit.get("objectID"), comments_limit)
            time.sleep(0.2)
        posts.append(_record(hit, comments=comments))
    return posts


def search(query, limit=100, time_filter="week",
           with_comments=False, comments_limit=5):
    after = int(time.time() - TIME_DELTAS.get(time_filter, TIME_DELTAS["week"]))
    params = {"tags": "story", "query": query, "hitsPerPage": min(limit, 100),
              "numericFilters": f"created_at_i>{after}"}
    hits = _get("/search", params).get("hits", [])
    posts = []
    for hit in hits:
        comments = None
        if with_comments:
            comments = fetch_comments(hit.get("objectID"), comments_limit)
            time.sleep(0.2)
        posts.append(_record(hit, query=query, comments=comments))
    return posts


def fetch_comments(item_id, limit=5):
    out = []

    def walk(children):
        for ch in children or []:
            text = _clean(ch.get("text"))
            if text and len(out) < limit:
                out.append(text[:1000])
            if len(out) >= limit:
                return
            walk(ch.get("children"))

    try:
        data = _get(f"/items/{item_id}")
        walk(data.get("children"))
    except Exception:
        pass
    return out
