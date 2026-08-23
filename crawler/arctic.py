import time

import requests

from . import painpoints

BASE_URL = "https://arctic-shift.photon-reddit.com/api"
FIELDS = "id,subreddit,title,selftext,author,score,num_comments,created_utc"

TIME_DELTAS = {
    "hour": 3600,
    "day": 86400,
    "week": 604800,
    "month": 2592000,
    "year": 31536000,
}


def _get(path, params):
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=30,
                        headers={"User-Agent": "painpoint-crawler/0.1"})
    resp.raise_for_status()
    data = resp.json().get("data")
    return data or []


def search_posts(subreddit=None, query=None, title=None, limit=100,
                 time_filter="week"):
    params = {"limit": min(limit, 100), "fields": FIELDS}
    if subreddit:
        params["subreddit"] = subreddit
    if query:
        params["title"] = query
    if title:
        params["title"] = title
    if time_filter in TIME_DELTAS:
        params["after"] = int(time.time() - TIME_DELTAS[time_filter])
    params.setdefault("sort", "desc")
    return _get("/posts/search", params)


def fetch_comments(post_id, limit=5):
    try:
        rows = _get("/comments/search", {
            "link_id": post_id,
            "limit": min(limit, 100),
            "sort": "desc",
            "fields": "body,score",
        })
    except Exception:
        return []
    return [r["body"][:1000] for r in rows
            if r.get("body") and r["body"] not in ("[deleted]", "[removed]")]


def to_record(raw, query=None, comments=None):
    text = f"{raw.get('title') or ''}\n{raw.get('selftext') or ''}"
    pain, matched = painpoints.analyze_text(text)
    if comments:
        c_pain, c_matched = painpoints.analyze_text("\n".join(comments))
        pain = round(pain + 0.5 * c_pain, 2)
        matched = list(dict.fromkeys(matched + c_matched))
    ups = raw.get("score") or 0
    n_comments = raw.get("num_comments") or 0
    return {
        "id": raw["id"],
        "subreddit": raw.get("subreddit", ""),
        "title": raw.get("title") or "",
        "selftext": (raw.get("selftext") or "")[:5000],
        "author": raw.get("author") or "[deleted]",
        "url": f"https://www.reddit.com{raw.get('permalink') or ('/comments/' + raw['id'])}",
        "created_utc": float(raw.get("created_utc") or 0),
        "collected_at": time.time(),
        "score": int(ups),
        "num_comments": int(n_comments),
        "upvote_ratio": 0.0,
        "pain_score": painpoints.final_score(pain, n_comments, ups),
        "matched_keywords": ",".join(matched),
        "query": query or "",
        "comments": "\n---\n".join(comments) if comments else "",
    }
