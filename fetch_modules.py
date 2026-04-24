"""
fetch_modules.py
────────────────
Fetches up to 100 modules from each of 4 Metasploit categories.
Saves to modules_400.json with a "category" field.

Usage:
    python fetch_modules.py
"""

import re
import json
import subprocess
import urllib.request

REPO    = "rapid7/metasploit-framework"
OUTFILE = "modules_400.json"
PER_CAT = 100

CATEGORIES = [
    ("multi_http",   "modules/exploits/multi/http"),
    ("linux_local",  "modules/exploits/linux/local"),
    ("windows_smb",  "modules/exploits/windows/smb"),
    ("unix_webapp",  "modules/exploits/unix/webapp"),
]

NAME_RE     = re.compile(r"'Name'\s*=>\s*['\"](.+?)['\"]")
DESC_QQ_RE  = re.compile(r"'Description'\s*=>\s*%q\{(.+?)\}", re.DOTALL)
DESC_STR_RE = re.compile(r"'Description'\s*=>\s*['\"](.+?)['\"]", re.DOTALL)

def gh_token():
    result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    return result.stdout.strip()

def api_get(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "BARE-fetch",
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def raw_get(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {token}",
        "User-Agent": "BARE-fetch",
    })
    with urllib.request.urlopen(req) as r:
        return r.read().decode("utf-8", errors="replace")

def make_id(category, filename):
    return f"{category}_{filename.replace('.rb', '')}"

def extract(content):
    nm = NAME_RE.search(content)
    if not nm:
        return None, None
    name = nm.group(1).strip()

    dm = DESC_QQ_RE.search(content)
    if dm:
        desc = re.sub(r"\s+", " ", dm.group(1).strip())
        return name, desc

    dm = DESC_STR_RE.search(content)
    if dm:
        desc = re.sub(r"\s+", " ", dm.group(1).strip())
        return name, desc

    return name, None

token   = gh_token()
records = []
counts  = {}

for cat_key, subdir in CATEGORIES:
    print(f"\n── {cat_key} ({subdir}) ────────────────────────────")
    cat_records = []

    url = f"https://api.github.com/repos/{REPO}/contents/{subdir}?per_page=300"
    try:
        entries = api_get(url, token)
    except Exception as e:
        print(f"  [!] Failed to list {subdir}: {e}")
        counts[cat_key] = 0
        continue

    rb_files = [e for e in entries if isinstance(e, dict) and e.get("name", "").endswith(".rb")]
    print(f"  [~] {len(rb_files)} .rb files found")

    for entry in rb_files:
        if len(cat_records) >= PER_CAT:
            break

        fid = make_id(cat_key, entry["name"])
        raw_url = entry.get("download_url") or \
                  f"https://raw.githubusercontent.com/{REPO}/master/{subdir}/{entry['name']}"
        try:
            content = raw_get(raw_url, token)
        except Exception as e:
            print(f"  [!] {entry['name']}: {e}")
            continue

        name, desc = extract(content)
        if not name or not desc:
            continue

        cat_records.append({
            "id":          fid,
            "name":        name,
            "description": desc,
            "category":    cat_key,
        })
        print(f"  [{len(cat_records):03d}/{PER_CAT}] {fid}")

    if len(cat_records) < PER_CAT:
        print(f"  [!] WARNING: only {len(cat_records)} valid modules in {subdir} (wanted {PER_CAT})")

    counts[cat_key] = len(cat_records)
    records.extend(cat_records)

with open(OUTFILE, "w") as f:
    json.dump(records, f, indent=2)

import os
size = os.path.getsize(OUTFILE)

print(f"\n{'─'*55}")
print(f"  Count per category:")
for cat_key, _ in CATEGORIES:
    print(f"    {cat_key:<15} {counts.get(cat_key, 0)}")
print(f"  Total: {len(records)}")
print(f"  File:  {OUTFILE}  ({size} bytes / {size/1024:.1f} KB)")

print(f"\nSamples (one each from linux_local, windows_smb, unix_webapp):")
for cat_key in ("linux_local", "windows_smb", "unix_webapp"):
    sample = next((r for r in records if r["category"] == cat_key), None)
    if sample:
        print(json.dumps(sample, indent=2))
