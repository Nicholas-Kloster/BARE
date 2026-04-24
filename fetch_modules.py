"""
fetch_modules.py
────────────────
Fetches the full Metasploit exploits/ and auxiliary/ module set.
Uses the Git Trees API (2 calls) for directory traversal, then
downloads .rb files concurrently for speed.

Saves to modules_full.json.

Usage:
    python fetch_modules.py
    GITHUB_TOKEN=ghp_xxx python fetch_modules.py
"""

import os
import re
import json
import subprocess
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO    = "rapid7/metasploit-framework"
OUTFILE = "modules_full.json"
WORKERS = 20

TARGETS = [
    ("exploits",  "modules/exploits"),
    ("auxiliary", "modules/auxiliary"),
]

NAME_RE     = re.compile(r"'Name'\s*=>\s*['\"](.+?)['\"]")
DESC_QQ_RE  = re.compile(r"'Description'\s*=>\s*%q\{(.+?)\}", re.DOTALL)
DESC_STR_RE = re.compile(r"'Description'\s*=>\s*['\"](.+?)['\"]", re.DOTALL)

# ── Auth ──────────────────────────────────────────────────────────────────────

def get_token():
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        print(f"[~] Using GITHUB_TOKEN from environment")
        return token
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        token = result.stdout.strip()
        if token:
            print(f"[~] Using token from gh CLI")
            return token
    except FileNotFoundError:
        pass
    print("[!] No token found — proceeding unauthenticated (60 req/hour limit)")
    print("[!] If rate-limited, set GITHUB_TOKEN and re-run")
    return ""

def make_headers(token):
    h = {"Accept": "application/vnd.github+json", "User-Agent": "BARE-fetch"}
    if token:
        h["Authorization"] = f"token {token}"
    return h

def api_get(url, token):
    req = urllib.request.Request(url, headers=make_headers(token))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            remaining = r.headers.get("X-RateLimit-Remaining", "?")
            return json.loads(r.read()), int(remaining) if remaining != "?" else None
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError(f"Rate limited or forbidden: {url}\nResponse: {e.read().decode()}")
        raise

def raw_get(url, token):
    req = urllib.request.Request(url, headers=make_headers(token))
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

# ── Extraction ────────────────────────────────────────────────────────────────

def extract(content):
    nm = NAME_RE.search(content)
    if not nm:
        return None, None
    name = nm.group(1).strip()

    dm = DESC_QQ_RE.search(content)
    if dm:
        return name, re.sub(r"\s+", " ", dm.group(1).strip())

    dm = DESC_STR_RE.search(content)
    if dm:
        return name, re.sub(r"\s+", " ", dm.group(1).strip())

    return name, None

def make_id(category, path):
    stem = path.replace(".rb", "").replace("/", "_")
    return f"{category}_{stem}"

# ── Tree fetch ────────────────────────────────────────────────────────────────

def get_rb_paths(category, modules_subdir, token):
    """Return list of (path_relative_to_modules_subdir, raw_url) for all .rb files."""
    # Step 1: get tree SHA for the subdirectory
    contents_url = f"https://api.github.com/repos/{REPO}/contents/{modules_subdir}"
    # We actually need the tree SHA — use the git/trees endpoint on the path
    # First get the ref tree to find the subtree SHA
    ref_url = f"https://api.github.com/repos/{REPO}/git/trees/master?recursive=0"
    # Simpler: use contents API to get directory metadata including SHA
    contents, _ = api_get(
        f"https://api.github.com/repos/{REPO}/contents/{modules_subdir}",
        token
    )
    # contents is a list of directory entries (top-level subdirs)
    # We need to get the SHA of THIS directory as a tree, not its children
    # Use the parent: get modules/ contents and find our subdir
    parent_contents, _ = api_get(
        f"https://api.github.com/repos/{REPO}/contents/modules",
        token
    )
    subdir_name = modules_subdir.split("/")[-1]  # "exploits" or "auxiliary"
    tree_sha = None
    for entry in parent_contents:
        if entry.get("name") == subdir_name and entry.get("type") == "dir":
            tree_sha = entry["sha"]
            break

    if not tree_sha:
        raise RuntimeError(f"Could not find tree SHA for {modules_subdir}")

    print(f"  [~] {category}: tree SHA {tree_sha[:12]}... fetching recursive listing")

    # Step 2: get full recursive tree
    tree_url = f"https://api.github.com/repos/{REPO}/git/trees/{tree_sha}?recursive=1"
    tree_data, remaining = api_get(tree_url, token)

    if tree_data.get("truncated"):
        print(f"  [!] WARNING: tree is truncated for {modules_subdir} — some modules will be missing")

    rb_entries = [
        item for item in tree_data.get("tree", [])
        if item.get("type") == "blob" and item.get("path", "").endswith(".rb")
    ]

    print(f"  [~] {category}: {len(rb_entries)} .rb files found (rate limit remaining: {remaining})")

    results = []
    for item in rb_entries:
        rel_path = item["path"]  # e.g. "multi/http/example.rb"
        raw_url = f"https://raw.githubusercontent.com/{REPO}/master/{modules_subdir}/{rel_path}"
        results.append((rel_path, raw_url))

    return results

# ── Concurrent download + extract ─────────────────────────────────────────────

def process_one(args):
    category, rel_path, raw_url, token = args
    try:
        content = raw_get(raw_url, token)
    except Exception as e:
        return None, f"download failed: {e}"

    name, desc = extract(content)
    if not name or not desc:
        return None, "no name/description"

    return {
        "id":          make_id(category, rel_path),
        "name":        name,
        "description": desc,
        "category":    category,
        "path":        f"modules/{category.replace('exploits','exploits').replace('auxiliary','auxiliary')}/{rel_path}",
    }, None

# ── Main ──────────────────────────────────────────────────────────────────────

token   = get_token()
records = []
counts  = {}
skipped = {}

for category, modules_subdir in TARGETS:
    print(f"\n── {category} ({'─'*40})")
    try:
        rb_paths = get_rb_paths(category, modules_subdir, token)
    except RuntimeError as e:
        print(f"[!] FATAL: {e}")
        raise SystemExit(1)

    cat_records = []
    cat_skipped = 0
    tasks = [(category, rel_path, raw_url, token) for rel_path, raw_url in rb_paths]

    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(process_one, t): t for t in tasks}
        for future in as_completed(futures):
            record, err = future.result()
            done += 1
            if record:
                cat_records.append(record)
            else:
                cat_skipped += 1

            total_so_far = len(records) + len(cat_records)
            if total_so_far % 100 == 0 and total_so_far > 0:
                print(f"  [{total_so_far}] {category} — {len(cat_records)} valid so far")

    counts[category]  = len(cat_records)
    skipped[category] = cat_skipped
    records.extend(cat_records)
    print(f"  [+] {category}: {len(cat_records)} valid, {cat_skipped} skipped")

# Sort for deterministic output: by category then id
records.sort(key=lambda r: (r["category"], r["id"]))

with open(OUTFILE, "w") as f:
    json.dump(records, f, indent=2)

import os as _os
size = _os.path.getsize(OUTFILE)

print(f"\n{'═'*55}")
print(f"  Total records : {len(records)}")
for cat, _ in TARGETS:
    print(f"  {cat:<12} : {counts.get(cat, 0)} valid, {skipped.get(cat, 0)} skipped")
print(f"  Output        : {OUTFILE}  ({size:,} bytes / {size/1024/1024:.1f} MB)")
