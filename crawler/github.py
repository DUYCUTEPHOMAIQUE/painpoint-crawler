import time
from datetime import datetime, timezone

import requests

from . import painpoints

BASE_URL = "https://api.github.com"
PLATFORM = "gh"
TIME_DELTAS = {
    "hour": 3600,
    "day": 86400,
    "week": 604800,
    "month": 2592000,
    "year": 31536000,
}


def _get(path, params=None):
    resp = requests.get(f"{BASE_URL}{path}", params=params or {}, timeout=30,
                        headers={"Accept": "application/vnd.github+json",
                                 "User-Agent": "painpoint-crawler/0.1"})
    resp.raise_for_status()
    return resp.json()


def _parse_query(query, time_filter):
    q = (query or "").strip() or "is:issue state:open"
    if "is:issue" not in q:
        q += " is:issue"
    if time_filter in TIME_DELTAS:
        since = datetime.fromtimestamp(time.time() - TIME_DELTAS[time_filter], tz=timezone.utc)
        q += f" created:>={since:%Y-%m-%d}"
    return q


def _record(item, query=None, comments=None):
    repo_url = item.get("repository_url") or ""
    repo_name = "/".join(repo_url.rstrip("/").split("/")[-2:]) if repo_url else "github"
    title = item.get("title") or ""
    body = item.get("body") or ""
    n_comments = item.get("comments") or 0
    ups = (item.get("reactions") or {}).get("total_count") or 0
    labels = ",".join(l.get("name", "") for l in (item.get("labels") or [])[:3])
    pain, matched = painpoints.analyze_text(f"{title}\n{body}")
    if comments:
        c_pain, c_matched = painpoints.analyze_text("\n".join(comments))
        pain = round(pain + 0.5 * c_pain, 2)
        matched = list(dict.fromkeys(matched + c_matched))
    try:
        created = datetime.fromisoformat((item.get("created_at") or "").replace("Z", "+00:00")).timestamp()
    except ValueError:
        created = 0.0
    return {
        "id": f"gh_{item.get('id')}",
        "platform": PLATFORM,
        "subreddit": f"{repo_name} [{labels}]" if labels else repo_name,
        "title": title,
        "selftext": (body or "")[:5000],
        "author": (item.get("user") or {}).get("login") or "[deleted]",
        "url": item.get("html_url") or "",
        "created_utc": float(created),
        "collected_at": time.time(),
        "score": int(ups),
        "num_comments": int(n_comments),
        "upvote_ratio": 0.0,
        "pain_score": painpoints.final_score(pain, n_comments, ups),
        "matched_keywords": ",".join(matched),
        "query": query or "",
        "comments": "\n---\n".join(comments) if comments else "",
    }


def discover(query=None, limit=100, time_filter="month",
             with_comments=False, comments_limit=5):
    return _run(query, limit, time_filter, with_comments, comments_limit)


def search(query, limit=100, time_filter="week",
           with_comments=False, comments_limit=5):
    return _run(query, limit, time_filter, with_comments, comments_limit)


def _run(query, limit, time_filter, with_comments, comments_limit):
    params = {"q": _parse_query(query, time_filter),
              "per_page": min(limit, 50), "sort": "comments", "order": "desc"}
    data = _get("/search/issues", params)
    posts = []
    comment_budget = 15
    for item in data.get("items", []):
        if item.get("pull_request"):
            continue
        comments = None
        if with_comments and comment_budget > 0:
            comments = fetch_issue_comments(item, comments_limit)
            comment_budget -= 1
            time.sleep(0.5)
        posts.append(_record(item, query=query, comments=comments))
    return posts


def trending_repos(window_days=7, limit=20):
    since = datetime.fromtimestamp(time.time() - window_days * 86400, tz=timezone.utc)
    data = _get("/search/repositories",
                {"q": f"created:>={since:%Y-%m-%d}", "sort": "stars",
                 "order": "desc", "per_page": min(limit, 50)})
    out = []
    for r in data.get("items", []):
        stars = r.get("stargazers_count") or 0
        try:
            created = datetime.fromisoformat(
                (r.get("created_at") or "").replace("Z", "+00:00")).timestamp()
            age_days = max((time.time() - created) / 86400, 1 / 24)
        except ValueError:
            age_days = 1.0
        out.append({
            "full_name": r.get("full_name") or "",
            "url": r.get("html_url") or "",
            "description": (r.get("description") or "")[:200],
            "stars": int(stars),
            "stars_per_day": round(stars / age_days, 1),
            "language": r.get("language") or "",
        })
    return out


def fetch_issue_comments(item, limit=5):
    repo_url = item.get("repository_url") or ""
    parts = repo_url.rstrip("/").split("/")[-2:]
    if len(parts) != 2:
        return []
    try:
        items = _get(f"/repos/{'/'.join(parts)}/issues/{item.get('number')}/comments",
                     {"per_page": min(limit, 100)})
    except Exception:
        return []
    return [(i.get("body") or "")[:1000] for i in items[:limit] if i.get("body")]
