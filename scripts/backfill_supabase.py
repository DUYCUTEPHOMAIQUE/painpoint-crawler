"""Đẩy toàn bộ dữ liệu SQLite lên Supabase (chạy 1 lần khi chuyển đổi).

Cần env: SUPABASE_URL, SUPABASE_SERVICE_KEY
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler import storage


def main():
    if not (storage.SUPABASE_URL and storage.SUPABASE_KEY):
        raise SystemExit("Thiếu SUPABASE_URL / SUPABASE_SERVICE_KEY trong .env")
    posts = storage.load_posts(min_pain=-1)
    print(f"Có {len(posts)} posts trong SQLite")
    total = 0
    for i in range(0, len(posts), 200):
        chunk = posts[i:i + 200]
        sent = storage.push_posts_supabase(chunk)
        total += sent
        print(f"  đẩy {total}/{len(posts)}")
    print(f"Hoàn tất: {total} posts trên Supabase")


if __name__ == "__main__":
    main()
