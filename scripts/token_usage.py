"""Xem token OpenClaw da tieu. Chay: python scripts/token_usage.py"""
import glob
import json

tin = tout = tcacheread = ttot = 0
n = 0
for f in glob.glob('/home/duy24ithust/.openclaw/agents/main/sessions/*.trajectory.jsonl'):
    for line in open(f):
        if '"usage"' not in line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        u = (d.get('data') or {}).get('usage') or {}
        if u:
            n += 1
            tin += u.get('input', 0) or 0
            tout += u.get('output', 0) or 0
            tcacheread += u.get('cacheRead', 0) or 0
            ttot += u.get('total', 0) or 0

print(f"So lan goi LLM : {n}")
print(f"Input tokens   : {tin:,}")
print(f"Output tokens  : {tout:,}")
print(f"Cache read     : {tcacheread:,}")
print(f"TONG           : {ttot:,}")
print("Chi phi        : $0 (model ox-alpha-free la mien phi)")
