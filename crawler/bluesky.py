import hashlib
import os
import time
from datetime import datetime, timezone

import requests

from . import painpoints

BASE_URL = "https://public.api.bsky.app"
PLATFORM = "bsky"
_session_token = None


def _auth_header():
    """Neu co BLUESKY_HANDLE + BLUESKY_APP_PASSWORD thi dang nhap lay token."""
    global _session_token
    handle = os.getenv("BLUESKY_HANDLE")
    password = os.getenv("BLUESKY_APP_PASSWORD")
    if not (handle and password):
        return {}
    if _session_token is None:
        try:
            resp = requests.post("https://bsky.social/xrpc/com.atproto.server.createSession",
                                 json={"identifier": handle, "password": password},
                                 timeout=30, headers={"User-Agent": "painpoint-crawler/0.1"})
            resp.raise_for_status()
            _session_token = resp.json().get("accessJwt")
        except Exception:
            _session_token = ""
    return {"Authorization": f"Bearer {_session_token}"} if _session_token else {}


def _get(path, params):
    headers = {"User-Agent": "painpoint-crawler/0.1", **_auth_header()}
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=30, headers=headers)
    resp.raise_for_status()
    return resp.json()


def _parse_iso(s):
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _record(post, query):
    uri = post.get("uri") or ""
    record = post.get("record") or {}
    text = record.get("text") or ""
    author = (post.get("author") or {}).get("handle") or "[deleted]"
    n_replies = post.get("replyCount") or 0
    ups = post.get("likeCount") or 0
    pain, matched = painpoints.analyze_text(text)
    rid = hashlib.md5(uri.encode()).hexdigest()[:12]
    return {
        "id": f"bs_{rid}",
        "platform": PLATFORM,
        "subreddit": query,
        "title": text[:140],
        "selftext": text[:5000],
        "author": author,
        "url": f"https://bsky.app/profile/{author}/post/{uri.rsplit('/', 1)[-1]}",
        "created_utc": _parse_iso(record.get("createdAt")),
        "collected_at": time.time(),
        "score": int(ups),
        "num_comments": int(n_replies),
        "upvote_ratio": 0.0,
        "pain_score": painpoints.final_score(pain, n_replies, ups),
        "matched_keywords": ",".join(matched),
        "query": query or "",
        "comments": "",
    }


def discover(query=None, limit=100, time_filter="week", **_):
    if not query:
        return []
    after = time.time() - {"hour": 3600, "day": 86400, "week": 604800}.get(time_filter, 604800)
    data = _get("/xrpc/app.bsky.feed.searchPosts",
                {"q": query, "limit": min(limit, 100), "sort": "latest"})
    posts = []
    for p in data.get("posts", []):
        if _parse_iso((p.get("record") or {}).get("createdAt")) < after:
            continue
        posts.append(_record(p, query))
    return posts


def search(query, limit=100, time_filter="week", **_):
    return discover(query=query, limit=limit, time_filter=time_filter)
