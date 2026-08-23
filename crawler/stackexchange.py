import html as htmllib
import re
import time

import requests

from . import painpoints

BASE_URL = "https://api.stackexchange.com/2.3"
SITE = "stackoverflow"
PLATFORM = "so"
TIME_DELTAS = {
    "hour": 3600,
    "day": 86400,
    "week": 604800,
    "month": 2592000,
    "year": 31536000,
}


def _get(path, params):
    params = dict(params, site=SITE)
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=30,
                        headers={"User-Agent": "painpoint-crawler/0.1"})
    resp.raise_for_status()
    return resp.json().get("items", [])


def _clean(text):
    if not text:
        return ""
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", str(text)))
    return re.sub(r"\s+", " ", text).strip()


def _record(q, query=None, comments=None):
    title = htmllib.unescape(q.get("title") or "")
    body = _clean(q.get("body"))
    ups = q.get("score") or 0
    n_answers = q.get("answer_count") or 0
    tags = ",".join((q.get("tags") or [])[:3])
    pain, matched = painpoints.analyze_text(f"{title}\n{body}")
    if comments:
        c_pain, c_matched = painpoints.analyze_text("\n".join(comments))
        pain = round(pain + 0.5 * c_pain, 2)
        matched = list(dict.fromkeys(matched + c_matched))
    return {
        "id": f"so_{q.get('question_id')}",
        "platform": PLATFORM,
        "subreddit": tags or SITE,
        "title": title,
        "selftext": body[:5000],
        "author": (q.get("owner") or {}).get("display_name") or "[deleted]",
        "url": q.get("link") or "",
        "created_utc": float(q.get("creation_date") or 0),
        "collected_at": time.time(),
        "score": int(ups),
        "num_comments": int(n_answers),
        "upvote_ratio": 0.0,
        "pain_score": painpoints.final_score(pain, n_answers, ups),
        "matched_keywords": ",".join(matched),
        "query": query or "",
        "comments": "\n---\n".join(comments) if comments else "",
    }


def discover(tag=None, limit=100, time_filter="month", sort="votes",
             with_comments=False, comments_limit=5):
    params = {"order": "desc", "sort": sort, "pagesize": min(limit, 100)}
    if tag:
        params["tagged"] = tag
    if time_filter in TIME_DELTAS:
        params["fromdate"] = int(time.time() - TIME_DELTAS[time_filter])
    questions = _get("/questions", params)
    posts = []
    for q in questions:
        comments = None
        if with_comments:
            comments = fetch_answers(q.get("question_id"), comments_limit)
            time.sleep(0.2)
        posts.append(_record(q, comments=comments))
    return posts


def search(query, limit=100, time_filter="week", tag=None,
           with_comments=False, comments_limit=5):
    params = {"q": query, "order": "desc", "sort": "relevance",
              "pagesize": min(limit, 100)}
    if tag:
        params["tagged"] = tag
    if time_filter in TIME_DELTAS:
        params["fromdate"] = int(time.time() - TIME_DELTAS[time_filter])
    questions = _get("/search/advanced", params)
    posts = []
    for q in questions:
        comments = None
        if with_comments:
            comments = fetch_answers(q.get("question_id"), comments_limit)
            time.sleep(0.2)
        posts.append(_record(q, query=query, comments=comments))
    return posts


def fetch_answers(question_id, limit=5):
    if not question_id:
        return []
    try:
        items = _get(f"/questions/{question_id}/answers",
                     {"order": "desc", "sort": "votes",
                      "pagesize": min(limit, 100), "filter": "withbody"})
    except Exception:
        return []
    return [_clean(i.get("body"))[:1000] for i in items if i.get("body")]
