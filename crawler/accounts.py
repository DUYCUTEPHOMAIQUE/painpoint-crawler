import json
from pathlib import Path

STORE = Path(__file__).resolve().parent.parent / "data" / "accounts.json"


def load():
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {}


def save(data):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def add_account(source, **fields):
    data = load()
    src = data.setdefault(source, {})
    accs = src.setdefault("accounts", [])
    accs.append(fields)
    save(data)
    return fields


def get_accounts(source):
    return load().get(source, {}).get("accounts", [])


def get_api_credentials(source):
    for a in get_accounts(source):
        if a.get("client_id") and a.get("client_secret") and "your_" not in str(a.get("client_id")):
            return a
    return None


def update_account(source, match_field, match_value, **updates):
    data = load()
    changed = False
    for a in data.get(source, {}).get("accounts", []):
        if a.get(match_field) == match_value:
            a.update(updates)
            changed = True
    if changed:
        save(data)
    return changed
