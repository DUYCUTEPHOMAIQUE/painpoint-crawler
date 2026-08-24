import argparse
import os
import time

import yaml
from rich.console import Console
from rich.table import Table

from crawler import arctic, crawler, github, hackernews, stackexchange, storage
from crawler.client import get_reddit, has_credentials

console = Console()

KNOWN_SOURCES = {"auto", "reddit", "arctic", "hn", "so", "gh"}


def resolve_sources(args):
    raw = (getattr(args, "sources", None) or "auto").lower()
    parts = [p.strip() for p in raw.split(",") if p.strip()] or ["auto"]
    unknown = [p for p in parts if p not in KNOWN_SOURCES]
    if unknown:
        raise SystemExit(
            f"Nguồn không hỗ trợ: {', '.join(unknown)}. "
            f"Chọn trong: {', '.join(sorted(KNOWN_SOURCES))}"
        )
    if "auto" in parts:
        parts = [s for s in parts if s != "auto"]
        if not parts:
            if has_credentials():
                parts = ["reddit"]
            else:
                console.print("[yellow]Chưa có Reddit API key -> dùng nguồn Arctic Shift "
                              "(lưu trữ công khai, không cần key).[/yellow]")
                console.print("[dim]Muốn dữ liệu realtime hơn: thêm API key vào .env (xem README)."
                              "[/dim]\n")
                parts = ["arctic"]
    return parts


def load_config():
    with open("config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def show_results(posts, min_pain=0.0):
    table = Table(title=f"Kết quả ({len(posts)} posts, pain_score >= {min_pain})")
    table.add_column("Pain", style="bold red", justify="right")
    table.add_column("Nguồn", style="magenta")
    table.add_column("Cộng đồng", style="cyan")
    table.add_column("Tiêu đề", max_width=60, overflow="fold")
    table.add_column("↑", justify="right")
    table.add_column("💬", justify="right")
    for p in sorted(posts, key=lambda x: -x["pain_score"])[:30]:
        if p["pain_score"] < min_pain:
            continue
        title = p["title"][:90]
        table.add_row(
            str(p["pain_score"]),
            p.get("platform") or "reddit",
            p["subreddit"],
            title,
            str(p["score"]),
            str(p["num_comments"]),
        )
    console.print(table)


def crawl_reddit_sub(source, name, args, listing, time_filter, with_comments, comments_limit):
    if source == "arctic":
        posts = arctic.search_posts(subreddit=name, limit=args.limit,
                                    time_filter=time_filter)
        records = []
        for raw in posts:
            comments = arctic.fetch_comments(raw["id"], comments_limit) \
                if with_comments else None
            records.append(arctic.to_record(raw, comments=comments))
            if with_comments:
                time.sleep(0.3)
        return records
    reddit = get_reddit()
    return crawler.discover_subreddit(
        reddit, name, args.limit,
        listing=listing, time_filter=time_filter,
        with_comments=with_comments, comments_limit=comments_limit,
    )


def cmd_discover(args):
    cfg = load_config()
    dcfg = cfg.get("discover", {})
    rcfg = cfg.get("reddit", {})
    scfg = cfg.get("sources", {})
    subs = args.subreddits.split(",") if args.subreddits else dcfg.get("subreddits", [])
    listing = args.listing or rcfg.get("listing", "top")
    time_filter = args.time or rcfg.get("time_filter", "week")
    with_comments = args.with_comments
    comments_limit = rcfg.get("comments_per_post", 5)
    sources = resolve_sources(args)

    storage.init_db()
    all_posts = []
    for src in sources:
        if src in ("reddit", "arctic"):
            for name in subs:
                name = name.strip()
                if not name:
                    continue
                console.print(f"[yellow]Đang crawl r/{name} ({src})...[/yellow]")
                try:
                    posts = crawl_reddit_sub(src, name, args, listing, time_filter,
                                             with_comments, comments_limit)
                except Exception as e:
                    console.print(f"[red]Lỗi r/{name}: {e}[/red]")
                    continue
                saved = storage.save_posts(posts)
                all_posts.extend(posts)
                console.print(f"  -> {len(posts)} posts lấy về, {saved} lưu DB")
        elif src == "hn":
            opts = scfg.get("hackernews", {})
            console.print("[yellow]Đang quét Hacker News...[/yellow]")
            try:
                posts = hackernews.discover(
                    limit=args.limit, time_filter=time_filter,
                    min_points=opts.get("min_points", 20),
                    with_comments=with_comments, comments_limit=comments_limit)
            except Exception as e:
                console.print(f"[red]Lỗi Hacker News: {e}[/red]")
                continue
            saved = storage.save_posts(posts)
            all_posts.extend(posts)
            console.print(f"  -> {len(posts)} posts lấy về, {saved} lưu DB")
        elif src == "so":
            tags = scfg.get("stackoverflow", {}).get("tags", [])
            for tag in tags:
                console.print(f"[yellow]Đang quét StackOverflow tag #{tag}...[/yellow]")
                try:
                    posts = stackexchange.discover(
                        tag=tag, limit=args.limit, time_filter=time_filter,
                        with_comments=with_comments, comments_limit=comments_limit)
                except Exception as e:
                    console.print(f"[red]Lỗi tag {tag}: {e}[/red]")
                    continue
                saved = storage.save_posts(posts)
                all_posts.extend(posts)
                console.print(f"  -> {len(posts)} posts lấy về, {saved} lưu DB")
        elif src == "gh":
            queries = scfg.get("github", {}).get("queries", [])
            for q in queries:
                console.print(f'[yellow]Đang quét GitHub issues: "{q}"...[/yellow]')
                try:
                    posts = github.discover(
                        query=q, limit=args.limit, time_filter=time_filter,
                        with_comments=with_comments, comments_limit=comments_limit)
                except Exception as e:
                    console.print(f"[red]Lỗi GitHub '{q}': {e}[/red]")
                    continue
                saved = storage.save_posts(posts)
                all_posts.extend(posts)
                console.print(f"  -> {len(posts)} posts lấy về, {saved} lưu DB")

    min_pain = args.min_pain if args.min_pain is not None else dcfg.get("min_pain_score", 2.0)
    hot = [p for p in all_posts if p["pain_score"] >= min_pain]
    show_results(hot, min_pain)
    console.print(f"\n[green]Tổng cộng:[/green] {len(all_posts)} posts, "
                  f"{len(hot)} posts có pain_score >= {min_pain}. Xem lại bằng: python main.py stats")


def search_reddit_or_arctic(src, q, args, cfg, sort, time_filter, seen):
    rcfg = cfg.get("reddit", {})
    results = []
    if src == "arctic":
        if args.subreddit:
            sub_groups = [(q, [args.subreddit])]
        else:
            fallback_subs = [s for s in cfg.get("discover", {}).get("subreddits", [])][:8]
            console.print(f"[dim]Không chỉ định --subreddit -> tìm trong {len(fallback_subs)} subreddit phổ biến.[/dim]")
            sub_groups = [(q, fallback_subs)]
        for query, subs in sub_groups:
            for name in subs:
                console.print(f'[yellow]Đang tìm "{query}" trong r/{name}...[/yellow]')
                try:
                    raws = arctic.search_posts(subreddit=name, query=query,
                                               limit=args.limit,
                                               time_filter=time_filter)
                except Exception as e:
                    console.print(f"[red]Lỗi: {e}[/red]")
                    continue
                records = []
                for raw in raws:
                    if raw["id"] in seen:
                        continue
                    comments = arctic.fetch_comments(raw["id"], rcfg.get("comments_per_post", 5)) \
                        if args.with_comments else None
                    rec = arctic.to_record(raw, query=query, comments=comments)
                    rec["query"] = query
                    records.append(rec)
                    seen.add(raw["id"])
                results.extend(records)
                console.print(f"  -> {len(records)} kết quả")
                time.sleep(1)
    else:
        subreddit = args.subreddit or "all"
        console.print(f'[yellow]Đang tìm kiếm: "{q}" (r/{subreddit}, sort={sort}, time={time_filter})[/yellow]')
        try:
            posts = crawler.search_reddit(
                get_reddit(), q, args.limit, subreddit=subreddit, sort=sort,
                time_filter=time_filter, with_comments=args.with_comments,
                comments_limit=rcfg.get("comments_per_post", 5),
            )
        except Exception as e:
            console.print(f"[red]Lỗi khi tìm '{q}': {e}[/red]")
            return []
        new_posts = [p for p in posts if p["id"] not in seen]
        seen.update(p["id"] for p in new_posts)
        results.extend(new_posts)
        console.print(f"  -> {len(new_posts)} kết quả mới")
    return results


def cmd_search(args):
    cfg = load_config()
    rcfg = cfg.get("reddit", {})
    scfg = cfg.get("sources", {})
    sort = args.sort or cfg.get("search", {}).get("sort", "relevance")
    time_filter = args.time or rcfg.get("time_filter", "week")
    sources = resolve_sources(args)
    queries = [args.keyword] + ([k.strip() for k in args.extra.split(",")] if args.extra else [])

    storage.init_db()
    all_posts = []
    seen = set()

    for src in sources:
        if src in ("reddit", "arctic"):
            for q in queries:
                all_posts.extend(search_reddit_or_arctic(
                    src, q, args, cfg, sort, time_filter, seen))
        elif src == "hn":
            for q in queries:
                console.print(f'[yellow]Đang tìm Hacker News: "{q}"...[/yellow]')
                try:
                    posts = hackernews.search(
                        q, limit=args.limit, time_filter=time_filter,
                        with_comments=args.with_comments,
                        comments_limit=rcfg.get("comments_per_post", 5))
                except Exception as e:
                    console.print(f"[red]Lỗi Hacker News '{q}': {e}[/red]")
                    continue
                posts = [p for p in posts if p["id"] not in seen]
                seen.update(p["id"] for p in posts)
                all_posts.extend(posts)
                console.print(f"  -> {len(posts)} kết quả")
        elif src == "so":
            tags = scfg.get("stackoverflow", {}).get("tags", [])
            for q in queries:
                for tag in tags + [None]:
                    label = f"#{tag}" if tag else "toàn site"
                    console.print(f'[yellow]Đang tìm StackOverflow "{q}" ({label})...[/yellow]')
                    try:
                        posts = stackexchange.search(
                            q, limit=args.limit, time_filter=time_filter, tag=tag,
                            with_comments=args.with_comments,
                            comments_limit=rcfg.get("comments_per_post", 5))
                    except Exception as e:
                        console.print(f"[red]Lỗi SO '{q}' ({label}): {e}[/red]")
                        continue
                    posts = [p for p in posts if p["id"] not in seen]
                    seen.update(p["id"] for p in posts)
                    all_posts.extend(posts)
                    console.print(f"  -> {len(posts)} kết quả")
        elif src == "gh":
            for q in queries:
                console.print(f'[yellow]Đang tìm GitHub issues: "{q}"...[/yellow]')
                try:
                    posts = github.search(
                        q, limit=args.limit, time_filter=time_filter,
                        with_comments=args.with_comments,
                        comments_limit=rcfg.get("comments_per_post", 5))
                except Exception as e:
                    console.print(f"[red]Lỗi GitHub '{q}': {e}[/red]")
                    continue
                posts = [p for p in posts if p["id"] not in seen]
                seen.update(p["id"] for p in posts)
                all_posts.extend(posts)
                console.print(f"  -> {len(posts)} kết quả")

    if all_posts:
        storage.save_posts(all_posts)
    show_results(all_posts, args.min_pain)


def cmd_daily(args):
    cfg = load_config()
    rcfg = cfg.get("reddit", {})
    scfg = cfg.get("sources", {})
    dcfg = cfg.get("discover", {})
    window = args.window
    min_pain = args.min_pain if args.min_pain is not None else dcfg.get("min_pain_score", 2.0)
    comments_limit = rcfg.get("comments_per_post", 5)

    base_source = "reddit" if has_credentials() else "arctic"
    subs = [s.strip() for s in (args.subreddits or "").split(",") if s.strip()] \
        or dcfg.get("subreddits", [])
    so_tags = scfg.get("stackoverflow", {}).get("tags", [])
    gh_queries = scfg.get("github", {}).get("queries", [])
    raw_sources = getattr(args, "sources", None)
    if raw_sources in (None, "auto"):
        sources = ["auto", "hn", "so", "gh"]
    else:
        sources = [s.strip() for s in raw_sources.split(",") if s.strip()]
        unknown = [s for s in sources if s not in KNOWN_SOURCES]
        if unknown:
            raise SystemExit(f"Nguồn không hỗ trợ: {', '.join(unknown)}")
        sources = resolve_sources(args)

    storage.init_db()
    all_new = []
    total_fetched = 0

    def collect(posts, label):
        nonlocal total_fetched
        new_only = storage.filter_new(posts)
        storage.save_posts(posts)
        total_fetched += len(posts)
        all_new.extend(new_only)
        console.print(f"  {label}: {len(posts)} lấy về, [green]{len(new_only)} mới[/green]")

    for src in sources:
        actual = base_source if src == "auto" else src
        if actual in ("reddit", "arctic"):
            for name in subs:
                name = name.strip()
                if not name:
                    continue
                console.print(f"[yellow][daily] r/{name} ({actual}, listing=new, {window})...[/yellow]")
                try:
                    posts = crawl_reddit_sub(actual, name, args, listing="new",
                                             time_filter=window, with_comments=False,
                                             comments_limit=comments_limit)
                except Exception as e:
                    console.print(f"[red]Lỗi r/{name}: {e}[/red]")
                    continue
                collect(posts, f"r/{name}")
        elif actual == "hn":
            console.print(f"[yellow][daily] Hacker News (mới nhất, {window})...[/yellow]")
            try:
                posts = hackernews.discover(limit=args.limit, time_filter=window,
                                            min_points=0,
                                            with_comments=args.comments,
                                            comments_limit=comments_limit)
            except Exception as e:
                console.print(f"[red]Lỗi Hacker News: {e}[/red]")
                posts = []
            collect(posts, "hn")
        elif actual == "so":
            for tag in so_tags:
                console.print(f"[yellow][daily] StackOverflow #{tag} (mới nhất, {window})...[/yellow]")
                try:
                    posts = stackexchange.discover(tag=tag, limit=args.limit,
                                                   time_filter=window, sort="creation",
                                                   with_comments=args.comments,
                                                   comments_limit=comments_limit)
                except Exception as e:
                    console.print(f"[red]Lỗi tag {tag}: {e}[/red]")
                    continue
                collect(posts, f"so/#{tag}")
        elif actual == "gh":
            for q in gh_queries:
                console.print(f'[yellow][daily] GitHub "{q}" ({window})...[/yellow]')
                try:
                    posts = github.discover(query=q, limit=args.limit,
                                            time_filter=window,
                                            with_comments=args.comments,
                                            comments_limit=comments_limit)
                except Exception as e:
                    console.print(f"[red]Lỗi GitHub '{q}': {e}[/red]")
                    continue
                collect(posts, f"gh:{q}")

    trending = []
    try:
        console.print("[yellow][daily] GitHub Trending repos...[/yellow]")
        trending = github.trending_repos(window_days=7, limit=20)
        storage.save_star_snapshots(trending)
    except Exception as e:
        console.print(f"[red]Lỗi trending: {e}[/red]")
    growth = storage.star_growth(days=7)

    report_path = write_report(all_new, min_pain, trending=trending, growth=growth)

    hot = sorted([p for p in all_new if p["pain_score"] >= min_pain],
                 key=lambda x: -x["pain_score"])
    show_results(hot, min_pain)
    console.print(f"\n[green]Hoàn tất:[/green] quét {total_fetched} posts, "
                  f"{len(all_new)} post mới, {len(hot)} pain point mới >= {min_pain}.")
    if report_path:
        console.print(f"Báo cáo: {report_path}")


def _md_cell(text, limit=140):
    text = (text or "").replace("\n", " ").replace("|", "/").strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def write_report(all_new, min_pain, trending=None, growth=None):
    if not all_new and not trending:
        return None
    date_str = time.strftime("%Y-%m-%d")
    out_dir = os.path.join("data", "reports")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{date_str}.md")
    lines = ["", f"## Run {time.strftime('%H:%M')} — {len(all_new)} post mới", ""]
    labels = {"reddit": "Reddit", "hn": "Hacker News", "so": "StackOverflow",
              "gh": "GitHub Issues"}
    for plat in ("reddit", "hn", "so", "gh"):
        items = sorted([p for p in all_new if (p.get("platform") or "reddit") == plat
                        and p["pain_score"] >= min_pain],
                       key=lambda x: -x["pain_score"])[:20]
        if not items:
            continue
        lines.append(f"### {labels[plat]} ({len(items)} pain point mới)")
        lines.append("")
        lines.append("| Pain | Tiêu đề | Nội dung | Cộng đồng | ↑ | 💬 |")
        lines.append("|---|---|---|---|---|---|")
        for p in items:
            title = _md_cell(p["title"], 90)
            url = p["url"]
            community = _md_cell(p["subreddit"], 30)
            content = p.get("selftext") or ""
            if not content.strip():
                content = p.get("comments") or ""
            lines.append(
                f"| **{p['pain_score']}** | [{title}]({url}) "
                f"| {_md_cell(content)} | {community} "
                f"| {p['score']} | {p['num_comments']} |"
            )
        lines.append("")
    if trending:
        lines.append(f"### GitHub Trending — top repo mới nổi ({len(trending)})")
        lines.append("")
        lines.append("| ⭐ | ⭐/ngày | Repo | Ngôn ngữ | Mô tả |")
        lines.append("|---|---|---|---|---|")
        for r in trending[:20]:
            lines.append(
                f"| {r['stars']} | {r['stars_per_day']} "
                f"| [{r['full_name']}]({r['url']}) "
                f"| {r['language']} | {_md_cell(r['description'], 100)} |"
            )
        lines.append("")
    if growth:
        lines.append(f"### GitHub tăng sao nhanh nhất theo lịch sử bot ({len(growth)})")
        lines.append("")
        lines.append("| Tăng ⭐ | Từ → Đến | Repo |")
        lines.append("|---|---|---|")
        for g in growth:
            lines.append(f"| +{g['gain']} | {g['min_stars']} → {g['max_stars']} "
                         f"| [{g['full_name']}](https://github.com/{g['full_name']}) |")
        lines.append("")
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def cmd_trending(args):
    storage.init_db()
    console.print(f"[yellow]Top {args.limit} repo mới trong {args.days} ngày qua, xếp theo sao...[/yellow]")
    repos = github.trending_repos(window_days=args.days, limit=args.limit)
    saved = storage.save_star_snapshots(repos)

    t = Table(title=f"GitHub Trending — repo mới nổi ({args.days} ngày qua)")
    t.add_column("⭐", justify="right", style="bold yellow")
    t.add_column("⭐/ngày", justify="right")
    t.add_column("Repo", style="cyan", max_width=40, overflow="fold")
    t.add_column("Ngôn ngữ")
    t.add_column("Mô tả", max_width=50, overflow="fold")
    for r in repos:
        t.add_row(str(r["stars"]), str(r["stars_per_day"]), r["full_name"],
                  r["language"], r["description"][:80])
    console.print(t)
    console.print(f"[green]Đã lưu {saved} snapshot sao[/green] (chạy hằng ngày để có lịch sử đo tăng trưởng)")

    growth = storage.star_growth(days=7)
    if growth:
        g = Table(title="Tăng sao nhanh nhất theo lịch sử bot (7 ngày)")
        g.add_column("+⭐", justify="right", style="bold green")
        g.add_column("Từ → Đến", justify="right")
        g.add_column("Repo", style="cyan")
        for row in growth:
            g.add_row(f"+{row['gain']}", f"{row['min_stars']} → {row['max_stars']}",
                      row["full_name"])
        console.print(g)


def cmd_export(args):
    storage.init_db()
    fmt = args.format
    out = args.output or f"data/export.{fmt}"
    if fmt == "csv":
        n = storage.export_csv(out, min_pain=args.min_pain, platform=args.platform)
    else:
        n = storage.export_json(out, min_pain=args.min_pain, platform=args.platform)
    console.print(f"[green]Đã export {n} posts[/green] -> {out}")


def cmd_stats(args):
    storage.init_db()
    s = storage.stats()
    console.print(f"[bold]Tổng số posts trong DB:[/bold] {s['total']}")
    if s.get("by_platform"):
        t0 = Table(title="Theo nền tảng")
        t0.add_column("Nền tảng", style="magenta")
        t0.add_column("Số posts", justify="right")
        t0.add_column("Pain TB", justify="right")
        for r in s["by_platform"]:
            t0.add_row(r["platform"], str(r["n"]), str(r["avg_pain"]))
        console.print(t0)
    if s["by_subreddit"]:
        t1 = Table(title="Theo cộng đồng")
        t1.add_column("Nền tảng", style="magenta")
        t1.add_column("Cộng đồng", style="cyan")
        t1.add_column("Số posts", justify="right")
        t1.add_column("Pain TB", justify="right")
        for r in s["by_subreddit"]:
            t1.add_row(r.get("platform") or "reddit", r["subreddit"], str(r["n"]), str(r["avg_pain"]))
        console.print(t1)
    if s["top"]:
        t2 = Table(title="Top 10 pain points")
        t2.add_column("Pain", style="bold red", justify="right")
        t2.add_column("Nền tảng", style="magenta")
        t2.add_column("Cộng đồng", style="cyan")
        t2.add_column("Tiêu đề", max_width=70, overflow="fold")
        t2.add_column("💬", justify="right")
        for r in s["top"]:
            t2.add_row(str(r["pain_score"]), r.get("platform") or "reddit",
                       r["subreddit"], r["title"][:90], str(r["num_comments"]))
        console.print(t2)


def main():
    parser = argparse.ArgumentParser(description="Crawl đa nền tảng (Reddit, Hacker News, StackOverflow, GitHub) tìm pain points")
    sub = parser.add_subparsers(dest="command", required=True)

    p_d = sub.add_parser("discover", help="Quét các subreddit phổ biến để tìm pain points")
    p_d.add_argument("--limit", type=int, default=None, help="Số posts mỗi subreddit")
    p_d.add_argument("--listing", choices=["top", "new", "hot", "rising"], default=None)
    p_d.add_argument("--time", choices=["hour", "day", "week", "month", "year", "all"], default=None)
    p_d.add_argument("--subreddits", default=None, help="Danh sách sub cách nhau bởi dấu phẩy (mặc định: config.yaml)")
    p_d.add_argument("--min-pain", type=float, default=None, help="Ngưỡng pain_score hiển thị")
    p_d.add_argument("--with-comments", action="store_true", help="Lấy thêm top comments (chậm hơn)")
    p_d.add_argument("--sources", "--source", dest="sources", default="auto",
                     help="Danh sách nguồn, cách nhau bởi dấu phẩy: reddit, arctic, hn, so, gh "
                          "(hn: Hacker News, so: StackOverflow, gh: GitHub issues). Mặc định: auto")
    p_d.set_defaults(func=cmd_discover)

    p_s = sub.add_parser("search", help="Tìm theo ngách/cụm từ khóa cụ thể")
    p_s.add_argument("--keyword", required=True, help="Từ khóa ngách, ví dụ 'meal prep'")
    p_s.add_argument("--extra", default=None, help="Các từ khóa bổ sung, cách nhau bởi dấu phẩy")
    p_s.add_argument("--subreddit", default=None, help="Giới hạn trong 1 subreddit (mặc định: toàn Reddit)")
    p_s.add_argument("--limit", type=int, default=None, help="Số kết quả mỗi từ khóa")
    p_s.add_argument("--sort", choices=["relevance", "hot", "top", "new", "comments"], default=None)
    p_s.add_argument("--time", choices=["hour", "day", "week", "month", "year", "all"], default=None)
    p_s.add_argument("--min-pain", type=float, default=2.0)
    p_s.add_argument("--with-comments", action="store_true")
    p_s.add_argument("--sources", "--source", dest="sources", default="auto",
                     help="Danh sách nguồn: reddit, arctic, hn, so, gh. Mặc định: auto")
    p_s.set_defaults(func=cmd_search)

    p_daily = sub.add_parser("daily",
                             help="Quét bài MỚI trên mọi nguồn trong cửa sổ thời gian ngắn + xuất báo cáo pain point mới (dùng cho cron)")
    p_daily.add_argument("--limit", type=int, default=None, help="Số posts mỗi nguồn/cộng đồng")
    p_daily.add_argument("--window", choices=["hour", "day", "week"], default="day",
                         help="Cửa sổ thời gian quét (mặc định: day). Dùng week nếu chạy thưa hơn 1 lần/ngày")
    p_daily.add_argument("--min-pain", type=float, default=None,
                         help="Ngưỡng pain_score đưa vào báo cáo (mặc định: config discover.min_pain_score)")
    p_daily.add_argument("--subreddits", default=None,
                         help="Ghi đè danh sách subreddit (mặc định: config.yaml)")
    p_daily.add_argument("--sources", dest="sources", default="auto",
                         help="Giới hạn nguồn (dấu phẩy): reddit, arctic, hn, so, gh. Mặc định: tất cả")
    p_daily.add_argument("--comments", action=argparse.BooleanOptionalAction, default=True,
                         help="Lấy thêm comments/answers cho hn/so/gh (mặc định: bật). Reddit vẫn tắt trừ khi dùng discover --with-comments")
    p_daily.set_defaults(func=cmd_daily)

    p_tr = sub.add_parser("trending",
                          help="Top repo GitHub mới nổi theo sao + tăng trưởng sao theo lịch sử bot")
    p_tr.add_argument("--days", type=int, default=7, help="Cửa sổ 'repo mới tạo trong N ngày' (mặc định: 7)")
    p_tr.add_argument("--limit", type=int, default=20, help="Số repo (mặc định: 20)")
    p_tr.set_defaults(func=cmd_trending)

    p_e = sub.add_parser("export", help="Xuất dữ liệu đã lưu ra CSV/JSON")
    p_e.add_argument("--format", choices=["csv", "json"], default="csv")
    p_e.add_argument("--output", default=None, help="Đường dẫn file xuất ra")
    p_e.add_argument("--min-pain", type=float, default=0.0)
    p_e.add_argument("--platform", default=None,
                     help="Chỉ export 1 nền tảng: reddit, hn, so, gh (mặc định: tất cả)")
    p_e.set_defaults(func=cmd_export)

    p_st = sub.add_parser("stats", help="Thống kê dữ liệu trong DB")
    p_st.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    cfg = load_config()
    if getattr(args, "limit", None) is None:
        args.limit = cfg.get("reddit", {}).get("default_limit", 100)
    args.func(args)


if __name__ == "__main__":
    main()
