import time
from datetime import datetime, timezone

from google_play_scraper import reviews, Sort

from . import painpoints

PLATFORM = "gpr"


def _record(review, app_name):
    text = (review.get("content") or "").strip()
    rating = review.get("score") or 0
    at = review.get("at")
    created = at.timestamp() if at else 0.0
    rid = review.get("reviewId") or f"{app_name}_{created}"
    title = text[:80] if text else f"Review {rating}★"
    pain, matched = painpoints.analyze_text(text)
    if rating and rating <= 2:
        pain += 2
    return {
        "id": f"gpr_{rid}",
        "platform": PLATFORM,
        "subreddit": app_name,
        "title": title,
        "selftext": text[:5000],
        "author": review.get("userName") or "[deleted]",
        "url": f"https://play.google.com/store/apps/details?id={app_name}",
        "created_utc": created,
        "collected_at": time.time(),
        "score": int(review.get("thumbsUpCount") or 0),
        "num_comments": int(review.get("replyCount") or 0) if review.get("replyCount") else 0,
        "upvote_ratio": 0.0,
        "pain_score": round(pain, 2),
        "matched_keywords": ",".join(matched),
        "query": "",
        "comments": "",
    }


def discover(app=None, limit=100, time_filter="week",
             country="us", lang="en", **_):
    if not app:
        return []
    result, _ = reviews(
        app,
        lang=lang,
        country=country,
        sort=Sort.NEWEST,
        count=min(limit, 200),
    )
    after = time.time() - {"hour": 3600, "day": 86400, "week": 604800}.get(time_filter, 604800)
    posts = []
    for r in result:
        rec = _record(r, str(app))
        if rec["created_utc"] and rec["created_utc"] < after:
            continue
        posts.append(rec)
    return posts
