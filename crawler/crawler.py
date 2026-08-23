import time

from . import painpoints


def post_to_dict(post, query=None, comments=None):
    title = post.title or ""
    selftext = post.selftext or ""
    raw, matched = painpoints.analyze_text(f"{title}\n{selftext}")
    if comments:
        joined = "\n".join(comments)
        c_raw, c_matched = painpoints.analyze_text(joined)
        raw = round(raw + 0.5 * c_raw, 2)
        matched = list(dict.fromkeys(matched + c_matched))
    score = painpoints.final_score(raw, post.num_comments, post.score)
    return {
        "id": post.id,
        "subreddit": str(post.subreddit),
        "title": title,
        "selftext": selftext[:5000],
        "author": str(post.author) if post.author else "[deleted]",
        "url": f"https://www.reddit.com{post.permalink}",
        "created_utc": float(post.created_utc),
        "collected_at": time.time(),
        "score": int(post.score),
        "num_comments": int(post.num_comments),
        "upvote_ratio": float(post.upvote_ratio),
        "pain_score": score,
        "matched_keywords": ",".join(matched),
        "query": query or "",
        "comments": "\n---\n".join(comments) if comments else "",
    }


def fetch_comments(post, limit):
    comments = []
    try:
        post.comments.replace_more(limit=0)
        for c in post.comments[:limit]:
            body = (c.body or "").strip()
            if body and body != "[deleted]" and body != "[removed]":
                comments.append(body[:1000])
    except Exception:
        pass
    return comments


def iter_posts(posts, with_comments=False, comments_limit=5):
    for post in posts:
        if post.stickied:
            continue
        comments = None
        if with_comments:
            comments = fetch_comments(post, comments_limit)
        yield post_to_dict(post, comments=comments)


def discover_subreddit(reddit, name, limit, listing="top", time_filter="week",
                       with_comments=False, comments_limit=5):
    sub = reddit.subreddit(name)
    if listing == "new":
        posts = sub.new(limit=limit)
    elif listing == "hot":
        posts = sub.hot(limit=limit)
    elif listing == "rising":
        posts = sub.rising(limit=limit)
    else:
        posts = sub.top(time_filter=time_filter, limit=limit)
    return list(iter_posts(posts, with_comments, comments_limit))


def search_reddit(reddit, query, limit, subreddit="all", sort="relevance",
                  time_filter="week", with_comments=False, comments_limit=5):
    sub = reddit.subreddit(subreddit)
    posts = sub.search(query, sort=sort, time_filter=time_filter, limit=limit)
    return list(iter_posts(posts, with_comments, comments_limit))
