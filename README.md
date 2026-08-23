# Pain Point Crawler

Tool crawl đa nền tảng để tìm **pain points (nỗi đau)** của mọi người — dùng cho nghiên cứu thị trường ngách hoặc tìm ý tưởng kinh doanh/sản phẩm.

## Nền tảng hỗ trợ

| Nguồn (`--sources`) | Nền tảng | API key | Nội dung |
|---|---|---|---|
| `reddit` / `arctic` | Reddit | reddit cần, arctic không | Posts + comments từ subreddit |
| `hn` | Hacker News | Không cần | Story Ask HN / Show HN qua Algolia API |
| `so` | Stack Overflow | Không cần | Câu hỏi kỹ thuật theo tag |
| `gh` | GitHub Issues | Không cần | Bug report / feature request công khai |

## Cách hoạt động

- **`discover`** — quét các cộng đồng phổ biến (subreddit, tag StackOverflow, query GitHub...) và chấm điểm mức độ "nỗi đau" của từng post dựa trên từ khóa + độ tương tác.
- **`search`** — tìm theo ngách cụ thể bạn quan tâm (ví dụ: `meal prep`, `bookkeeping for freelancers`) trên một hoặc nhiều nền tảng cùng lúc.
- Dữ liệu lưu vào SQLite (`data/painpoints.db`), tự động chống trùng lặp (kèm tên nền tảng trong id), xuất ra CSV/JSON bất cứ lúc nào.

## Cài đặt

### 1. Tạo môi trường ảo & cài dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. (Tùy chọn) Đăng ký Reddit API — chỉ cần khi muốn dữ liệu realtime

1. Vào https://www.reddit.com/prefs/apps → kéo xuống → **create another app...**
2. Chọn loại **script**, đặt tên tùy ý.
3. `redirect uri` điền: `http://localhost:8080`
4. Sau khi tạo, bạn nhận được:
   - **client_id**: chuỗi ký tự dưới tên app
   - **secret**: chuỗi ký tự bên cạnh

### 3. Cấu hình (bỏ qua nếu dùng Arctic Shift)

```bash
cp .env.example .env
```

Mở `.env` và điền `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`.

## Chạy ngay không cần API key

```bash
# Reddit (lưu trữ Arctic Shift)
.venv/bin/python main.py discover --limit 50 --sources arctic

# Hacker News + StackOverflow + GitHub
.venv/bin/python main.py discover --sources hn,so,gh --limit 30
```

## Sử dụng

```bash
# Quét các subreddit mặc định trong config.yaml (tìm ý tưởng tổng quát)
.venv/bin/python main.py discover

# Quét nhiều nền tảng cùng lúc
.venv/bin/python main.py discover --sources arctic,hn,so,gh

# Chỉ lấy top posts tháng này, ngưỡng pain cao hơn
.venv/bin/python main.py discover --time month --min-pain 4

# Lấy thêm top comments/answers của mỗi post (chính xác hơn nhưng chậm hơn)
.venv/bin/python main.py discover --with-comments --limit 50

# Nghiên cứu một ngách cụ thể trên mọi nền tảng
.venv/bin/python main.py search --keyword "meal prep" --sources hn,so,gh

# Tìm nhiều từ khóa cùng lúc, giới hạn trong 1 subreddit
.venv/bin/python main.py search --keyword "invoicing" --extra "quotes,estimates" --subreddit smallbusiness

# Xuất dữ liệu đã crawl (lọc theo nền tảng nếu muốn)
.venv/bin/python main.py export --format csv
.venv/bin/python main.py export --format json --output data/ketqua.json --platform hn

# Xem thống kê DB (theo nền tảng + cộng đồng) + top pain points
.venv/bin/python main.py stats
```

## Chạy tự động hằng ngày (cron)

Lệnh `daily` quét **chỉ các bài mới** trong cửa sổ thời gian trên mọi nguồn (Reddit dùng `listing=new`, HN không lọc điểm, StackOverflow sort theo `creation`, GitHub lọc `created:>=hôm nay`), lưu toàn bộ vào DB nhưng **chỉ báo cáo những post chưa có trong DB** — nên chạy càng thường xuyên càng không bỏ lỡ.

```bash
# Chạy thử tay
.venv/bin/python main.py daily --window day

# Chạy thưa hơn 1 lần/ngày thì nới cửa sổ để phủ kín khoảng trống
.venv/bin/python main.py daily --window week
```

Báo cáo pain point mới nằm ở `data/reports/YYYY-MM-DD.md`, mỗi lần chạy được nối thêm vào cuối file.

### Tạo cron job

```bash
crontab -e
```

Thêm dòng (ví dụ chạy 7h sáng mỗi ngày):

```cron
0 7 * * * cd /home/duy24ithust/workspace/personal/crawler-tool && .venv/bin/python main.py daily >> data/cron.log 2>&1
```

Muốn chắc tay hơn nữa thì chạy 2 lần/ngày (7h và 19h) với `--window day`:

```cron
0 7,19 * * * cd /home/duy24ithust/workspace/personal/crawler-tool && .venv/bin/python main.py daily >> data/cron.log 2>&1
```

Nguyên tắc "không bỏ lỡ": cửa sổ quét (`--window`) phải ≥ khoảng cách giữa 2 lần chạy. Mỗi post có id riêng theo nền tảng nên crawl trùng lặp không sinh dữ liệu trùng; bài cũ được quét lại sẽ tự cập nhật lại điểm tương tác.

## Deploy miễn phí lên GitHub Actions

Không cần server — dùng **GitHub Actions** chạy `daily` theo lịch, tự commit DB + báo cáo ngược lại repo:

- **Public repo**: hoàn toàn free không giới hạn phút
- **Private repo**: cũng free (dùng ~10 phút/ngày trong hạn mức 2000 phút/tháng)

### Các bước

1. Tạo repo trống trên https://github.com/new (private hoặc public đều được), **không** tick khởi tạo README.

2. Push code lên:

```bash
git remote add origin git@github.com:<username>/<repo>.git
git push -u origin main
```

3. Bật workflow: vào tab **Actions** của repo → chọn "Daily pain point crawl" → **Enable workflows**. Có thể bấm **Run workflow** để chạy thử ngay.

4. (Tùy chọn) Muốn crawl Reddit API realtime trên cloud: repo **Settings → Secrets and variables → Actions**, thêm 2 secret `REDDIT_CLIENT_ID` và `REDDIT_CLIENT_SECRET`. Không thêm cũng được — tool tự dùng nguồn Arctic Shift không cần key.

### Lịch chạy & dữ liệu

- Cron mặc định: `0 0,12 * * *` UTC = **7h sáng & 7h tối giờ Việt Nam**
- Mỗi lần chạy quét `--window week` (phủ 7 ngày) nên bỏ sót tối đa vài tiếng kể cả khi 1 lần chạy bị lừa
- DB (`data/painpoints.db`) và báo cáo (`data/reports/`) được bot commit lại mỗi run — xem báo cáo trực tiếp trên GitHub hoặc pull về máy:

```bash
git pull
sqlite3 data/painpoints.db "SELECT platform, COUNT(*) FROM posts GROUP BY platform"
```

Lưu ý: GitHub tắt schedule nếu repo "im lặng" 60 ngày — bot commit hằng ngày nên không bao giờ bị. Xem log từng lần chạy ở tab Actions.

## Pain score là gì?

Mỗi post được chấm điểm theo 2 yếu tố:

1. **Từ khóa đau** trong tiêu đề/nội dung/comments — ví dụ:
   - Mạnh (+2): `struggling`, `frustrated`, `wish there was`, `can't afford`, `need advice`, `nightmare`...
   - Vừa (+1): `annoying`, `expensive`, `doesn't work`, `how do i`, `alternative to`...
2. **Độ tương tác** — nhiều upvote/comment hơn → nỗi đau càng phổ biến (hệ số cộng nhẹ).

Danh sách từ khóa nằm trong `crawler/painpoints.py`, chỉnh sửa thoải mái.

## Tùy chỉnh

- `config.yaml`:
  - `discover.subreddits` — thêm/bớt subreddit cần quét.
  - `sources.stackoverflow.tags` — các tag StackOverflow cần theo dõi.
  - `sources.github.queries` — query GitHub issues (hỗ trợ cú pháp tìm kiếm GitHub, ví dụ `label:bug language:python`).
  - `sources.hackernews.min_points` — lọc story HN theo số điểm tối thiểu.
- Reddit API miễn phí giới hạn ~100 requests/phút; StackOverflow ~300 request/ngày (không key); GitHub search ~10 request/phút (không key) — tool chạy tuần tự nên không lo bị block.

## Lưu ý

- Chỉ dùng cho mục đích nghiên cứu cá nhân, tôn trọng quy định của Reddit API.
- Bước tiếp theo (khi sẵn sàng): tích hợp LLM để tự phân loại chủ đề + tóm tắt insight từ dữ liệu đã lưu trong DB.
