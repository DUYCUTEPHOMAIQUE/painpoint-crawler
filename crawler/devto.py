import html as htmllib
import re
import time
from datetime import datetime

import requests

from . import painpoints

BASE_URL = "https://dev.to/api"
PLATFORM = "devto"
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


def _parse_iso(s):
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _record(a, query=None, comments=None):
    title = a.get("title") or ""
    desc = a.get("description") or ""
    body = _clean(a.get("body_html"))
    ups = a.get("positive_reactions_count") or 0
    n_comments = a.get("comments_count") or 0
    tags = ",".join((a.get("tag_list") or [])[:3])
    pain, matched = painpoints.analyze_text(f"{title}\n{desc}\n{body}")
    if comments:
        c_pain, c_matched = painpoints.analyze_text("\n".join(comments))
        pain = round(pain + 0.5 * c_pain, 2)
        matched = list(dict.fromkeys(matched + c_matched))
    return {
        "id": f"dv_{a.get('id')}",
        "platform": PLATFORM,
        "subreddit": tags or "dev",
        "title": title,
        "selftext": f"{desc}\n{body}".strip()[:5000],
        "author": (a.get("user") or {}).get("username") or "[deleted]",
        "url": a.get("url") or "",
        "created_utc": _parse_iso(a.get("published_at")),
        "collected_at": time.time(),
        "score": int(ups),
        "num_comments": int(n_comments),
        "upvote_ratio": 0.0,
        "pain_score": painpoints.final_score(pain, n_comments, ups),
        "matched_keywords": ",".join(matched),
        "query": query or "",
        "comments": "\n---\n".join(comments) if comments else "",
    }


def discover(tag=None, limit=100, time_filter="week",
             with_comments=False, comments_limit=5):
    params = {"per_page": min(limit, 100)}
    if tag:
        resp = requests.get(f"{BASE_URL}/articles", params=dict(params, tag=tag),
                            timeout=30, headers={"User-Agent": "painpoint-crawler/0.1"})
    else:
        resp = requests.get(f"{BASE_URL}/articles/latest", params=params,
                            timeout=30, headers={"User-Agent": "painpoint-crawler/0.1"})
    resp.raise_for_status()
    after = time.time() - TIME_DELTAS.get(time_filter, TIME_DELTAS["week"])
    articles = [a for a in resp.json()
                if _parse_iso(a.get("published_at")) >= after]
    comment_budget = 5
    posts = []
    for a in articles:
        comments = None
        if with_comments and comment_budget > 0:
            comments = fetch_comments(a.get("id"), comments_limit)
            comment_budget -= 1
            time.sleep(0.3)
        posts.append(_record(a, comments=comments))
    return posts


def fetch_comments(article_id, limit=5):
    try:
        resp = requests.get(f"{BASE_URL}/comments",
                            params={"a_id": article_id},
                            timeout=30, headers={"User-Agent": "painpoint-crawler/0.1"})
        resp.raise_for_status()
        items = resp.json()
    except Exception:
        return []
    out = []
    for c in items[:limit]:
        t = _clean(c.get("body_html"))
        if t:
            out.append(t[:1000])
    return out
