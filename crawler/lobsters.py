import time
from datetime import datetime, timezone

import requests

from . import painpoints

BASE_URL = "https://lobste.rs"
PLATFORM = "lb"
TIME_DELTAS = {
    "hour": 3600,
    "day": 86400,
    "week": 604800,
    "month": 2592000,
    "year": 31536000,
}


def _get(path):
    resp = requests.get(f"{BASE_URL}{path}", timeout=30,
                        headers={"User-Agent": "painpoint-crawler/0.1"})
    resp.raise_for_status()
    return resp.json()


def _parse_iso(s):
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _record(story, query=None):
    sid = story.get("short_id") or ""
    title = story.get("title") or ""
    desc = story.get("description") or ""
    tags = ",".join((story.get("tags") or [])[:3])
    ups = story.get("score") or 0
    n_comments = story.get("comment_count") or 0
    pain, matched = painpoints.analyze_text(f"{title}\n{desc}")
    return {
        "id": f"lb_{sid}",
        "platform": PLATFORM,
        "subreddit": tags or "lobsters",
        "title": title,
        "selftext": desc[:5000],
        "author": (story.get("submitting_user") or "") or "[deleted]",
        "url": f"https://lobste.rs/s/{sid}" if sid else (story.get("short_id_url") or ""),
        "created_utc": _parse_iso(story.get("created_at")),
        "collected_at": time.time(),
        "score": int(ups),
        "num_comments": int(n_comments),
        "upvote_ratio": 0.0,
        "pain_score": painpoints.final_score(pain, n_comments, ups),
        "matched_keywords": ",".join(matched),
        "query": query or "",
        "comments": "",
    }


def discover(limit=100, time_filter="week", **_):
    after = time.time() - TIME_DELTAS.get(time_filter, TIME_DELTAS["week"])
    posts = []
    page = 1
    while len(posts) < limit and page <= 3:
        stories = _get(f"/newest.json?page={page}")
        if not stories:
            break
        for s in stories:
            if _parse_iso(s.get("created_at")) < after:
                return posts
            posts.append(_record(s))
        page += 1
        time.sleep(1)
    return posts[:limit]
