"""Dang nhap Facebook 1 lan trong trinh duyet anti-detect.

Cach dung:
    .venv/bin/python scripts/fb_auth.py

Cua so trinh duyet se mo tren man hinh cua ban. Ban dang nhap tai khoan FB
trong do; script tu dong phat hien khi dang nhap xong va luu phien vao
profile "facebook" (dung lai lan sau, khong can dang nhap lai).
"""
import sys
import time

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])

from antibrow import launch


def is_logged_in(page):
    try:
        url = page.url or ""
        if "login" in url or "checkpoint" in url:
            return False
        for sel in ('div[aria-label="Facebook"]', '[data-pagelet="root"]',
                    'div[role="banner"]', '#viewport'):
            try:
                if page.locator(sel).count() > 0:
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def main():
    with launch(profile="facebook", label="FB session") as browser:
        page = browser.new_page()
        print("Dang mo Facebook trong trinh duyet anti-detect...")
        page.goto("https://www.facebook.com/")
        print(">> Hay dang nhap tai khoan Facebook trong cua so trinh duyet.")
        print(">> Script se tu dong nhan biet khi ban xong (toi da cho 10 phut).")
        deadline = time.time() + 600
        while time.time() < deadline:
            if is_logged_in(page):
                print("DANG NHAP THANH CONG! Phien da luu vao profile 'facebook'.")
                print("Gio chay: .venv/bin/python scripts/fb_crawl.py <link_group> [so_bai]")
                time.sleep(3)
                return
            time.sleep(5)
        print("Het thoi gian cho. Chay lai script neu chua kip dang nhap.")


if __name__ == "__main__":
    main()
