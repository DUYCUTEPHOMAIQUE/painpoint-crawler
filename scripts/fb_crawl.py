"""Crawl posts tu 1 nhom Facebook (can da dang nhap qua fb_auth.py).

Cach dung:
    .venv/bin/python scripts/fb_crawl.py "https://www.facebook.com/groups/XXXX" [so_bai]

Script mo nhom trong trinh duyet anti-detect, cuon de tai them bai,
trich xuat noi dung tung bai roi cham diem pain score va luu DB.
"""
import re
import sys
import time

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])

from antibrow import launch

from crawler import painpoints, storage

EXTRACT_JS = """
() => {
  const out = [];
  document.querySelectorAll('div[role="article"]').forEach(el => {
    const text = (el.innerText || "").trim();
    if (text && text.length > 40) out.push(text);
  });
  return out;
}
"""


def to_record(text, url):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = lines[0][:140] if lines else "(khong tieu de)"
    body = "\n".join(lines[1:])[:5000] or title
    pain, matched = painpoints.analyze_text(f"{title}\n{body}")
    rid = str(abs(hash(text[:200]))) [:12]
    return {
        "id": f"fb_{rid}",
        "platform": "fb",
        "subreddit": url.split("/groups/")[1].split("?")[0][:60] if "/groups/" in url else "facebook",
        "title": title,
        "selftext": body,
        "author": "[fb]",
        "url": url,
        "created_utc": 0.0,
        "collected_at": time.time(),
        "score": 0,
        "num_comments": 0,
        "upvote_ratio": 0.0,
        "pain_score": painpoints.final_score(pain, 0, 0),
        "matched_keywords": ",".join(matched),
        "query": "",
        "comments": "",
    }


def main():
    group_url = sys.argv[1] if len(sys.argv) > 1 else ""
    target = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    if not group_url:
        raise SystemExit('Cach dung: python scripts/fb_crawl.py "<link_group>" [so_bai]')

    storage.init_db()
    with launch(profile="facebook", label="FB crawl") as browser:
        page = browser.new_page()
        page.goto(group_url)
        time.sleep(6)

        seen = set()
        rounds = 0
        while len(seen) < target and rounds < target * 3:
            texts = page.evaluate(EXTRACT_JS)
            for t in texts:
                key = t[:120]
                seen.add(key)
            page.keyboard.press("End")
            time.sleep(3)
            rounds += 1
            print(f"  lan cuon {rounds}: {len(seen)} bai...")

        records = []
        for t in seen:
            clean = re.sub(r"\u200b|\ufeff", "", t)
            records.append(to_record(clean, group_url))
        saved = storage.save_posts(records)
        hot = sorted(records, key=lambda p: -p["pain_score"])[:10]
        print(f"\nDa luu {saved} posts (tong {len(records)} trich xuat).")
        print("Top pain vua crawl:")
        for p in hot:
            print(f"  [{p['pain_score']}] {p['title'][:80]}")


if __name__ == "__main__":
    main()
