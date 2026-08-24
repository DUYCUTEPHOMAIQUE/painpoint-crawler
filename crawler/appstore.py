import time

import requests

from . import painpoints

PLATFORM = "asr"


def _clean(text):
    return (text or "").strip()


def _parse_iso(s):
    from datetime import datetime
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def fetch_app_reviews(app_id, country="us", pages=3):
    """RSS customer reviews cua Apple — mien phi, khong key.
    RSS hay tra ve rong tuy storefront -> thu danh sach quoc gia den khi co du lieu."""
    out = []
    tried = set()
    for c in [country, "sg", "gb", "au", "ca", "in", "jp"]:
        if c in tried:
            continue
        tried.add(c)
        for page in range(1, pages + 1):
            try:
                resp = requests.get(
                    f"https://itunes.apple.com/{c}/rss/customerreviews/"
                    f"page={page}/id={app_id}/sortby=mostrecent/json",
                    timeout=30, headers={"User-Agent": "painpoint-crawler/0.1"},
                )
                if resp.status_code != 200:
                    break
                feed = (resp.json() or {}).get("feed", {})
                entries = feed.get("entry", [])
                if isinstance(entries, dict):
                    entries = [entries]
                if not entries:
                    break
                out.extend(entries)
            except Exception:
                break
        if len(out) >= 20:
            break
    return out


def _record(entry, app_name):
    title = _clean((entry.get("title") or {}).get("label"))
    body = _clean((entry.get("content") or {}).get("label"))
    rating = int(((entry.get("im:rating") or {}).get("label")) or 0)
    author = ((entry.get("author") or {}).get("name") or {}).get("label") or "[deleted]"
    updated = (entry.get("updated") or {}).get("label")
    rid = _clean(entry.get("id", {}).get("label"))[:60] or f"{app_name}_{updated}"
    pain, matched = painpoints.analyze_text(f"{title}\n{body}")
    if rating and rating <= 2:
        pain += 2  # 1-2 sao la pain ro rang
    return {
        "id": f"asr_{abs(hash(rid)) % 10**12}",
        "platform": PLATFORM,
        "subreddit": app_name,
        "title": title or f"Review {rating}★",
        "selftext": body[:5000],
        "author": author,
        "url": f"https://apps.apple.com/app/id{_clean((entry.get('id', {}).get('label')) or app_name).split('/')[-1].replace('id', '')}",
        "created_utc": _parse_iso(updated),
        "collected_at": time.time(),
        "score": 0,
        "num_comments": 0,
        "upvote_ratio": 0.0,
        "pain_score": round(pain, 2),
        "matched_keywords": ",".join(matched),
        "query": "",
        "comments": "",
    }


def discover(app=None, limit=100, time_filter="week",
             country="us", name=None, **_):
    if not app:
        return []
    entries = fetch_app_reviews(app, country=country, pages=3)
    posts = [_record(e, name or str(app)) for e in entries]
    return posts[:limit]
