import csv
import json
import os
import sqlite3
import time

import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
POSTS_COLUMNS = [
    "id", "platform", "subreddit", "title", "selftext", "author", "url",
    "created_utc", "collected_at", "score", "num_comments",
    "upvote_ratio", "pain_score", "matched_keywords", "query", "comments",
]


def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


def push_posts_supabase(posts):
    if not (SUPABASE_URL and SUPABASE_KEY and posts):
        return 0
    sent = 0
    for i in range(0, len(posts), 200):
        chunk = [{c: p.get(c) for c in POSTS_COLUMNS} for p in posts[i:i + 200]]
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/posts",
            headers=_sb_headers(),
            json=chunk,
            timeout=60,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Supabase upsert lỗi {resp.status_code}: {resp.text[:300]}")
        sent += len(chunk)
    return sent

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "painpoints.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL DEFAULT 'reddit',
    subreddit TEXT NOT NULL,
    title TEXT,
    selftext TEXT,
    author TEXT,
    url TEXT,
    created_utc REAL,
    collected_at REAL,
    score INTEGER DEFAULT 0,
    num_comments INTEGER DEFAULT 0,
    upvote_ratio REAL DEFAULT 0,
    pain_score REAL DEFAULT 0,
    matched_keywords TEXT,
    query TEXT,
    comments TEXT
);
CREATE INDEX IF NOT EXISTS idx_posts_subreddit ON posts(subreddit);
CREATE INDEX IF NOT EXISTS idx_posts_pain ON posts(pain_score DESC);
CREATE TABLE IF NOT EXISTS repo_stars (
    full_name TEXT NOT NULL,
    stars INTEGER NOT NULL,
    captured_at REAL NOT NULL,
    PRIMARY KEY (full_name, captured_at)
);
"""


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.executescript(SCHEMA)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(posts)")]
        if "platform" not in cols:
            conn.execute("ALTER TABLE posts ADD COLUMN platform TEXT NOT NULL DEFAULT 'reddit'")


def save_posts(posts):
    if not posts:
        return 0
    fields = [
        "id", "platform", "subreddit", "title", "selftext", "author", "url",
        "created_utc", "collected_at", "score", "num_comments",
        "upvote_ratio", "pain_score", "matched_keywords", "query", "comments",
    ]
    sql = f"INSERT INTO posts ({','.join(fields)}) VALUES ({','.join(['?'] * len(fields))}) ON CONFLICT(id) DO UPDATE SET"
    updates = ["score=excluded.score", "num_comments=excluded.num_comments",
               "upvote_ratio=excluded.upvote_ratio", "collected_at=excluded.collected_at"]
    sql += " " + ",".join(updates)
    saved = 0
    with _connect() as conn:
        for p in posts:
            if not p.get("platform"):
                p = {**p, "platform": "reddit"}
            conn.execute(sql, tuple(p.get(f) for f in fields))
            saved += 1
    try:
        push_posts_supabase(posts)
    except Exception as e:
        import sys
        print(f"[warn] Supabase sync lỗi: {e}", file=sys.stderr)
    return saved


def _sb_push(table, rows, on_conflict="full_name"):
    if not (SUPABASE_URL and SUPABASE_KEY and rows):
        return 0
    headers = _sb_headers()
    headers["Prefer"] = f"resolution=merge-duplicates,on_conflict={on_conflict},return=minimal"
    resp = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers, json=rows, timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Supabase {table} lỗi {resp.status_code}: {resp.text[:300]}")
    return len(rows)


def save_star_snapshots(repos):
    if not repos:
        return 0
    now = time.time()
    with _connect() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO repo_stars (full_name, stars, captured_at) VALUES (?,?,?)",
            [(r["full_name"], r["stars"], now) for r in repos],
        )
    try:
        _sb_push("repo_stars",
                 [{"full_name": r["full_name"], "stars": r["stars"], "captured_at": now}
                  for r in repos],
                 on_conflict="full_name,captured_at")
        _sb_push("repo_meta",
                 [{"full_name": r["full_name"], "description": r.get("description"),
                   "language": r.get("language"), "url": r.get("url")}
                  for r in repos])
    except Exception as e:
        import sys
        print(f"[warn] Supabase repo sync lỗi: {e}", file=sys.stderr)
    return len(repos)


def star_growth(days=7, limit=20):
    since = time.time() - days * 86400
    with _connect() as conn:
        rows = conn.execute(
            "SELECT full_name, MIN(stars) AS min_stars, MAX(stars) AS max_stars, "
            "MAX(stars) - MIN(stars) AS gain "
            "FROM repo_stars WHERE captured_at > ? "
            "GROUP BY full_name HAVING COUNT(*) > 1 "
            "ORDER BY gain DESC LIMIT ?",
            (since, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def filter_new(posts):
    if not posts:
        return []
    ids = [p["id"] for p in posts]
    placeholders = ",".join("?" * len(ids))
    with _connect() as conn:
        existing = {r[0] for r in conn.execute(
            f"SELECT id FROM posts WHERE id IN ({placeholders})", ids)}
    return [p for p in posts if p["id"] not in existing]


def load_posts(min_pain=0.0, subreddit=None, query=None, platform=None, limit=None):
    sql = "SELECT * FROM posts WHERE pain_score >= ?"
    params = [min_pain]
    if subreddit:
        sql += " AND LOWER(subreddit) = LOWER(?)"
        params.append(subreddit)
    if platform:
        sql += " AND LOWER(platform) = LOWER(?)"
        params.append(platform)
    if query:
        sql += " AND query LIKE ?"
        params.append(f"%{query}%")
    sql += " ORDER BY pain_score DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def export_csv(path, min_pain=0.0, platform=None):
    posts = load_posts(min_pain=min_pain, platform=platform)
    if not posts:
        return 0
    fields = list(posts[0].keys())
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(posts)
    return len(posts)


def export_json(path, min_pain=0.0, platform=None):
    posts = load_posts(min_pain=min_pain, platform=platform)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2, default=str)
    return len(posts)


def stats():
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        by_platform = conn.execute(
            "SELECT platform, COUNT(*) as n, ROUND(AVG(pain_score),2) as avg_pain "
            "FROM posts GROUP BY platform ORDER BY n DESC"
        ).fetchall()
        by_sub = conn.execute(
            "SELECT platform, subreddit, COUNT(*) as n, ROUND(AVG(pain_score),2) as avg_pain "
            "FROM posts GROUP BY platform, subreddit ORDER BY n DESC LIMIT 20"
        ).fetchall()
        top = conn.execute(
            "SELECT title, subreddit, platform, pain_score, num_comments FROM posts "
            "ORDER BY pain_score DESC LIMIT 10"
        ).fetchall()
    return {
        "total": total,
        "by_platform": [dict(r) for r in by_platform],
        "by_subreddit": [dict(r) for r in by_sub],
        "top": [dict(r) for r in top],
    }
