import os

import praw
from dotenv import load_dotenv

load_dotenv()


def has_credentials():
    cid = os.getenv("REDDIT_CLIENT_ID")
    secret = os.getenv("REDDIT_CLIENT_SECRET")
    return bool(cid and secret and "your_client_id" not in cid)


def get_reddit():
    if not has_credentials():
        raise SystemExit(
            "Thiếu thông tin Reddit API. Hãy copy .env.example thành .env "
            "và điền REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET (xem README.md), "
            "hoặc dùng --source arctic để chạy không cần API key."
        )
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "painpoint-crawler/0.1")
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        check_for_async=False,
    )
