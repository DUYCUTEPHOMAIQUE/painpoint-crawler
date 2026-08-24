import time
from datetime import datetime

import requests

from . import painpoints

PLATFORM = "lm"
DEFAULT_INSTANCE = "https://lemmy.world"
TIME_DELTAS = {
    "hour": 3600,
    "day": 86400,
    "week": 604800,
    "month": 2592000,
    "year": 31536000,
}


def _fetch_community(instance, community, limit):
    resp = requests.get(
        f"{instance}/api/v3/post/list",
        params={"community_name": community, "limit": min(limit, 50), "sort": "New"},
        timeout=30, headers={"User-Agent": "painpoint-crawler/0.1"},
    )
    resp.raise_for_status()
    return resp.json().get("posts", [])


def _record(entry, community):
    post = entry.get("post") or {}
    creator = (entry.get("creator") or {}).get("name") or "[deleted]"
    title = post.get("name") or ""
    body = post.get("body") or ""
    ups = post.get("score") or 0
    n_comments = post.get("comments") or 0
    published = post.get("published") or ""
    try:
        created = datetime.fromisoformat(published.replace("Z", "+00:00")).timestamp()
    except ValueError:
        created = 0.0
    pain, matched = painpoints.analyze_text(f"{title}\n{body}")
    return {
        "id": f"lm_{post.get('id')}",
        "platform": PLATFORM,
        "subreddit": community,
        "title": title,
        "selftext": body[:5000],
        "author": creator,
        "url": post.get("ap_id") or "",
        "created_utc": created,
        "collected_at": time.time(),
        "score": int(ups),
        "num_comments": int(n_comments),
        "upvote_ratio": 0.0,
        "pain_score": painpoints.final_score(pain, n_comments, ups),
        "matched_keywords": ",".join(matched),
        "query": "",
        "comments": "",
    }


def discover(community=None, limit=100, time_filter="week",
             instance=DEFAULT_INSTANCE, **_):
    if not community:
        return []
    after = time.time() - TIME_DELTAS.get(time_filter, TIME_DELTAS["week"])
    entries = _fetch_community(instance, community, limit)
    posts = []
    for e in entries:
        rec = _record(e, community)
        if rec["created_utc"] and rec["created_utc"] < after:
            continue
        posts.append(rec)
    return posts[:limit]
