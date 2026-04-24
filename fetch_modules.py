"""
fetch_modules.py
────────────────
Fetches up to 250 real Metasploit modules from multi/http/ only.
Saves to modules_250.json.

Metasploit modules use %q{...} heredoc for descriptions, not simple quoted
strings. This script handles both forms.

Usage:
    python fetch_modules.py
"""

import re
import json
import subprocess
import urllib.request

TARGET  = 250
SUBDIR  = "modules/exploits/multi/http"
REPO    = "rapid7/metasploit-framework"
OUTFILE = "modules_250.json"

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

def make_id(filename):
    return "multi_http_" + filename.replace(".rb", "")

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
seen    = set()

url = f"https://api.github.com/repos/{REPO}/contents/{SUBDIR}?per_page=300"
try:
    entries = api_get(url, token)
except Exception as e:
    print(f"[!] Failed to list {SUBDIR}: {e}")
    raise

rb_files = [e for e in entries if isinstance(e, dict) and e.get("name", "").endswith(".rb")]
print(f"[~] {SUBDIR}: {len(rb_files)} .rb files found")
print(f"[~] Fetching up to {TARGET} with valid Name+Description...\n")

for entry in rb_files:
    if len(records) >= TARGET:
        break

    fid = make_id(entry["name"])
    if fid in seen:
        continue

    raw_url = entry.get("download_url") or \
              f"https://raw.githubusercontent.com/{REPO}/master/{SUBDIR}/{entry['name']}"
    try:
        content = raw_get(raw_url, token)
    except Exception as e:
        print(f"  [!] {entry['name']}: {e}")
        continue

    name, desc = extract(content)
    if not name or not desc:
        continue

    seen.add(fid)
    records.append({"id": fid, "name": name, "description": desc})
    print(f"  [{len(records):03d}/{TARGET}] {fid}")

with open(OUTFILE, "w") as f:
    json.dump(records, f, indent=2)

import os
size = os.path.getsize(OUTFILE)
print(f"\n[+] Done. {len(records)} records saved to {OUTFILE}")
print(f"    File size: {size} bytes ({size/1024:.1f} KB)")
print(f"\nFirst 3 entries:")
for r in records[:3]:
    print(json.dumps(r, indent=2))
