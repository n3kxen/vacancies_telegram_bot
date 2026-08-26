#!/usr/bin/env python3
"""
Transfer `expires` field value into `expiry_date` for all vacancies
that have an `expires` date but empty `expiry_date`.

Usage:
    1. Upload to server:
        scp fix_expiry.py user@host:/path/to/bot/
    2. Run inside Docker container:
        docker cp fix_expiry.py bot_container:/tmp/
        docker exec bot_container python /tmp/fix_expiry.py
    3. Or run locally (if file accessible):
        python fix_expiry.py [path/to/vacancies.json]

After running, `expires` is cleared in records that had it moved.
"""
import json
import sys
from pathlib import Path

DEFAULT = "data/vacancies.json"

def fix(path_str: str = DEFAULT):
    path = Path(path_str)
    if not path.exists():
        print(f"[ERROR] File not found: {path}")
        return

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    moved = 0
    for v in data:
        exp = v.get("expires", "").strip()
        exd = v.get("expiry_date", "").strip()
        if exp and not exd:
            # crude extraction: take the last token that looks like DD.MM.YYYY
            tokens = exp.split()
            val = None
            for tok in reversed(tokens):
                if len(tok) == 10 and tok[2] == "." and tok[5] == ".":
                    val = tok
                    break
            if val:
                v["expiry_date"] = val
                v["expires"] = ""
                moved += 1
                print(f"  Moved {exp} -> expiry_date={val}  ({v.get('title','?')})")

    if moved:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[DONE] {moved} records updated in {path}")
    else:
        print("[OK] Nothing to transfer.")

if __name__ == "__main__":
    fix(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
