"""LLM Digest Engine — tong hop pain points bang LLM (qua opencode CLI).

Cach dung trong main.py: python main.py digest --days 2
"""
import json
import os
import re
import subprocess

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def llm(prompt, model=None):
    """Goi 1 prompt qua opencode CLI, tra ve text tra loi."""
    model = model or os.getenv("LLM_MODEL", "opencode-go/hy3")
    result = subprocess.run(
        ["opencode", "run", "-m", model, prompt],
        capture_output=True, text=True, timeout=300,
    )
    out = ANSI_RE.sub("", result.stdout or "")
    lines = [l for l in out.splitlines()
             if l.strip() and not l.strip().startswith(">") and "opencode-go/" not in l]
    return "\n".join(lines).strip()


def _extract_json_array(text):
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def select_candidates(posts, limit=None):
    limit = limit or int(os.getenv("LLM_MAX_CANDIDATES", "60"))
    """Sap xep theo pain score va bo cac bai trung noi dung gan nhau."""
    def tokens(t):
        return set(re.findall(r"[a-zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ0-9]+",
                              (t or "").lower()))

    seen, out = [], []
    for p in sorted(posts, key=lambda x: -x["pain_score"]):
        tk = tokens(p["title"])
        if not tk:
            continue
        dup = False
        for s in seen:
            inter = len(tk & s)
            if len(tk | s) and len(tk & s) / len(tk | s) > 0.55:
                dup = True
                break
        if not dup:
            seen.append(tk)
            out.append(p)
        if len(out) >= limit:
            break
    return out


def extract_themes(posts, batch_size=15):
    """Trich xuat chu de tu cac post bang LLM, tra ve list dict."""
    themes = []
    for i in range(0, len(posts), batch_size):
        batch = posts[i:i + batch_size]
        items = "\n".join(
            f"- [{p['platform']}/{p['subreddit']}] pain={p['pain_score']} "
            f"| {p['title']} | {(p.get('selftext') or '')[:220]}"
            for p in batch)
        prompt = f"""Đây là các bài đăng về nỗi đau/vấn đề của người thật từ mạng xã hội:

{items}

Hãy nhóm chúng thành các CHỦ ĐỀ pain point nổi bật. Trả về DUY NHẤT một mảng JSON hợp lệ (không thêm chữ nào khác), mỗi phần tử:
[{{"theme": "tên chủ đề ngắn", "summary_vi": "tóm tắt 2-3 câu tiếng Việt", "audience": "ai bị ảnh hưởng", "severity": 1-5, "evidence": [{{"title": "tiêu đề bài minh họa", "url": "link"}}], "opportunity": "cơ hội sản phẩm/dịch vụ nếu giải quyết được"}}]
Chỉ gom bài CÙNG vấn đề vào một chủ đề. Bỏ qua bài spam/quảng cáo."""
        raw = llm(prompt)
        parsed = _extract_json_array(raw)
        if isinstance(parsed, list):
            themes.extend(t for t in parsed if isinstance(t, dict) and t.get("theme"))
    return themes


def synthesize(themes, stats):
    """Viet bao cao tong hop cuoi cung bang LLM."""
    themes_json = json.dumps(themes, ensure_ascii=False)[:12000]
    prompt = f"""Thống kê dữ liệu crawl hôm nay: {stats}

Các chủ đề pain point đã trích xuất bằng LLM:
{themes_json}

Hãy viết BÁO CÁO DIGEST tiếng Việt dạng markdown gồm:
1. **Tóm tắt điều hành** (3-4 câu: tình hình chung, điểm đáng chú ý nhất)
2. **Top 3 cơ hội sản phẩm** rõ nhất (dựa trên severity + tần suất)
3. **Rủi ro/lưu ý** (nếu có)

Chỉ xuất markdown bắt đầu từ '# ', không lời dẫn."""
    return llm(prompt)


def build_digest(posts):
    """Pipeline day du: chon -> trich xuat -> tong hop. Tra ve (markdown, themes)."""
    total = len(posts)
    by_platform = {}
    for p in posts:
        by_platform[p["platform"]] = by_platform.get(p["platform"], 0) + 1
    stats = f"tổng {total} posts (" + ", ".join(f"{k}: {v}" for k, v in sorted(by_platform.items())) + ")"

    candidates = select_candidates(posts)
    print(f"Chọn {len(candidates)} ứng viên chất lượng từ {total} posts...")
    themes = extract_themes(candidates)
    print(f"LLM trích xuất được {len(themes)} chủ đề.")
    if not themes:
        return None, []

    themes.sort(key=lambda t: -(t.get("severity") or 0))
    head = (
        f"# 🧠 Pain Point Digest\n\n"
        f"> {stats}\n\n"
        f"## Các chủ đề nổi bật ({len(themes)})\n\n"
    )
    body = ""
    for i, t in enumerate(themes, 1):
        sev = "🔥" * min(int(t.get("severity") or 1), 5)
        ev = "\n".join(f"   - [{e.get('title', '')[:70]}]({e.get('url', '')})"
                       for e in (t.get("evidence") or [])[:3])
        body += (
            f"### {i}. {t.get('theme')} {sev}\n"
            f"- **Tóm tắt:** {t.get('summary_vi', '')}\n"
            f"- **Ai bị ảnh hưởng:** {t.get('audience', '')}\n"
            f"- **Cơ hội:** {t.get('opportunity', '')}\n"
            f"- **Bằng chứng:**\n{ev}\n\n"
        )
    summary_md = synthesize(themes, stats)
    md = head + body + "---\n\n" + (summary_md or "")
    return md, themes
