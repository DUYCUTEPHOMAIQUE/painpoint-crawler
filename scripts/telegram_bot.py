"""Telegram bot cho Pain Point Radar — xu ly lenh /trending, /digest, /top.

Chay 1 pass moi lan goi (phu hop GitHub Actions cron moi 15 phut),
hoac chay loop lien tuc o local: python scripts/telegram_bot.py --loop
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import requests

from crawler import github, llm_engine, storage

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OFFSET_FILE = os.path.join("data", "tg_offset.txt")
HELP_TEXT = (
    "🧠 <b>Pain Point Radar</b>\n\n"
    "/trending [số] [ngày] — GitHub trending (vd: /trending 5 7)\n"
    "/top [số] — Pain points cao nhất trong DB\n"
    "/digest [ngày] — Phân tích LLM tổng hợp\n\n"
    "Mặc định: /trending 10 7"
)


def api(method, **params):
    resp = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}",
                         json=params, timeout=60)
    return resp.json()


def get_offset():
    try:
        return int(open(OFFSET_FILE).read().strip())
    except Exception:
        return 0


def save_offset(o):
    os.makedirs(os.path.dirname(OFFSET_FILE), exist_ok=True)
    with open(OFFSET_FILE, "w") as f:
        f.write(str(o))


def esc(s):
    import html
    return html.escape(str(s or ""), quote=False)


def fmt_trending(repos, n, days):
    lines = []
    for i, r in enumerate(repos[:n], 1):
        gain = f" · <b class='g'>+{r['gain']}</b>" if r.get("gain") else ""
        gain = f" · +{r['gain']}⭐/7 ngày" if r.get("gain") else ""
        lang = f" · {esc(r['language'])}" if r.get("language") else ""
        desc = esc((r.get("description") or "")[:80])
        lines.append(
            f"<b>{i}. ⭐ {r['stars']}</b> · {r['perDay']}/ngày{gain}{lang}\n"
            f"<a href=\"{r['url']}\">{esc(r['full_name'])}</a>"
            + (f"\n<i>{desc}</i>" if desc else "")
        )
    head = f"🏆 <b>GitHub Trending — top {min(n, len(repos))} ({days} ngày qua)</b>\n"
    return head + "\n\n" + "\n\n".join(lines)


def handle(text):
    parts = (text or "").split()
    cmd = parts[0].lower().split("@")[0]
    args = parts[1:]
    num = lambda i, d: int(args[i]) if len(args) > i and args[i].isdigit() else d

    if cmd in ("/start", "/help"):
        return HELP_TEXT

    if cmd == "/trending":
        n, days = num(0, 10), num(1, 7)
        repos = github.trending_repos(window_days=days, limit=max(n, 25))
        storage.init_db()
        storage.save_star_snapshots(repos)
        growth = {g["full_name"]: g["gain"] for g in storage.star_growth(days=7)}
        for r in repos:
            r["gain"] = growth.get(r["full_name"], 0)
        repos.sort(key=lambda r: -r["stars"])
        return fmt_trending(repos, n, days)

    if cmd == "/top":
        storage.init_db()
        n = num(0, 10)
        posts = sorted(storage.load_posts(min_pain=3),
                       key=lambda p: -p["pain_score"])[:n]
        if not posts:
            return "Chưa có dữ liệu."
        lines = []
        for i, p in enumerate(posts, 1):
            lines.append(f"<b>{i}. [{p['pain_score']}]</b> "
                         f"<a href=\"{p['url']}\">{esc(p['title'][:70])}</a>\n"
                         f"<i>({p['platform']} · {esc(p['subreddit'][:18])})</i>")
        return "🔥 <b>Top pain points</b>\n\n" + "\n".join(lines)

    if cmd == "/digest":
        days = num(0, 2)
        since = time.time() - days * 86400
        posts = [p for p in storage.load_posts(min_pain=3)
                 if p["collected_at"] >= since]
        if not posts:
            return f"Không có posts nào {days} ngày qua."
        md, themes = llm_engine.build_digest(posts)
        if not themes:
            return "LLM chưa trích xuất được chủ đề. Thử lại sau."
        msgs = llm_engine.format_telegram_digest(themes, {})
        return "\n".join(msgs)

    return "Lệnh không rõ. Gửi /help để xem danh sách."


def main():
    if not TOKEN:
        raise SystemExit("Thiếu TELEGRAM_BOT_TOKEN")
    loop = "--loop" in sys.argv
    while True:
        offset = get_offset()
        try:
            data = api("getUpdates", offset=offset, timeout=50,
                       allowed_updates=["message"])
        except Exception as e:
            print(f"[warn] getUpdates lỗi: {e}")
            if not loop:
                return
            time.sleep(15)
            continue

        for u in data.get("result", []):
            offset = u["update_id"] + 1
            msg = u.get("message") or {}
            text = msg.get("text") or ""
            chat_id = (msg.get("chat") or {}).get("id")
            if not text or not chat_id:
                continue
            print(f"<- {text[:60]}")
            try:
                reply = handle(text)
            except Exception as e:
                reply = f"⚠️ Lỗi xử lý: {esc(e)}"
                print(f"[err] {e}")
            api("sendMessage", chat_id=chat_id, text=reply,
                parse_mode="HTML", disable_web_page_preview=True)
            save_offset(offset)

        if not loop:
            break
        time.sleep(2)


if __name__ == "__main__":
    main()
