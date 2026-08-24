"""Chạy schema Supabase qua kết nối Postgres trực tiếp.

Cần env SUPABASE_DB_URL (chuỗi kết nối pooler/direct có mật khẩu thật).
"""
import os
import sys

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "db", "supabase_schema.sql")


def main():
    url = os.getenv("SUPABASE_DB_URL")
    if not url or "YOUR-PASSWORD" in url:
        raise SystemExit("Thiếu SUPABASE_DB_URL (phải chứa mật khẩu thật)")
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        sql = f.read()
    raw = [s.strip() for s in sql.split(";")]
    statements = []
    for s in raw:
        lines = [ln for ln in s.splitlines() if ln.strip() and not ln.strip().startswith("--")]
        body = "\n".join(lines).strip()
        if body:
            statements.append(body)
    conn = psycopg2.connect(url, sslmode="require", connect_timeout=20)
    conn.autocommit = True
    with conn.cursor() as cur:
        for i, stmt in enumerate(statements, 1):
            try:
                cur.execute(stmt)
                print(f"OK {i}/{len(statements)}: {stmt.splitlines()[0][:60]}")
            except Exception as e:
                print(f"SKIP {i}: {str(e).strip()[:100]}")
    # verify
    with conn.cursor() as cur:
        cur.execute("select count(*) from information_schema.tables where table_schema='public'")
        print("Bảng trong public:", cur.fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
