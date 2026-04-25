#!/usr/bin/env python3
"""
shodan_to_bare.py
─────────────────
Converts Shodan JSONL output (produced by `shodan download`) to BARE's
findings.json format.

One finding is emitted per Shodan record (one record = one IP:port banner).
Records missing ip_str or port are skipped.

Usage:
    cat scan.jsonl | python shodan_to_bare.py
    python shodan_to_bare.py scan.jsonl
    shodan download results.json.gz apache && gunzip results.json.gz \\
      && cat results.json | python shodan_to_bare.py | bare

Conforms to INPUT_FORMAT.md v1. Does NOT call the Shodan API.
Authentication and data collection are the user's responsibility.
"""

import json
import sys
from typing import Any

__version__ = "1.0.0"
SOURCE = "shodan"

BANNER_MAX = 500
# Cap CVEs included in the description. Shodan often reports 50-100+ CVEs per
# stale-Apache banner; embedding all of them blows past MiniLM's 512-token
# budget and drowns out the actual service signal. Top-N by CVSS preserves
# the high-severity discriminators; full vulns dict still lives in metadata.
CVE_DESC_MAX = 10


def _max_cvss(info: Any) -> float:
    """Return the highest CVSS score across cvss/cvss_v2/cvss_v3 fields, or 0.0."""
    if not isinstance(info, dict):
        return 0.0
    score = 0.0
    for field in ("cvss", "cvss_v2", "cvss_v3"):
        v = info.get(field)
        if isinstance(v, (int, float)):
            score = max(score, float(v))
    return score


def severity_from_vulns(vulns: dict[str, Any]) -> str | None:
    """
    Derive a BARE severity string from a Shodan vulns dict.

    Uses the maximum CVSS score found across all reported CVEs.
    Shodan marks most findings as unverified — the severity reflects
    reported CVSS, not confirmed exploitability.

    Returns None if no vulns are present or no CVSS score is available.
    """
    if not vulns:
        return None

    max_cvss = max((_max_cvss(info) for info in vulns.values()), default=0.0)

    if max_cvss == 0.0:
        return None
    if max_cvss >= 9.0:
        return "critical"
    if max_cvss >= 7.0:
        return "high"
    if max_cvss >= 4.0:
        return "medium"
    return "low"


def build_title(record: dict[str, Any]) -> str:
    """
    Construct a short human-readable title for a Shodan finding.

    Preference order: product → http title → cpe23 → port/transport fallback.
    """
    port = record.get("port", "")
    transport = record.get("transport", "tcp")
    product = (record.get("product") or "").strip()

    if product:
        return f"{product} on port {port}"

    http = record.get("http") or {}
    title = (http.get("title") or "").strip()
    if title:
        return f"http {title}"

    cpe23 = record.get("cpe23") or []
    if cpe23 and isinstance(cpe23, list):
        first = cpe23[0].strip()
        if first:
            return f"{first} on port {port}"

    return f"port {port}/{transport}"


def build_description(record: dict[str, Any]) -> str:
    """
    Construct a rich description by mechanically concatenating Shodan fields.

    Concatenates in order: product+version, banner data, HTTP server/title,
    TLS CN, tags, CPE identifiers, CVE IDs. Only non-empty values are included.
    No vulnerability context is added beyond what Shodan reported.

    Falls back to "open {port}/{transport} on {ip_str}" if nothing else exists.
    """
    ip_str = record.get("ip_str", "")
    port = record.get("port", "")
    transport = record.get("transport", "tcp")

    parts: list[str] = []

    product = (record.get("product") or "").strip()
    version = (record.get("version") or "").strip()
    if product and version:
        parts.append(f"{product} {version}")
    elif product:
        parts.append(product)

    data = (record.get("data") or "").strip()
    if data:
        parts.append(data[:BANNER_MAX].strip())

    http = record.get("http") or {}
    http_server = (http.get("server") or "").strip()
    if http_server:
        parts.append(http_server)
    http_title = (http.get("title") or "").strip()
    if http_title:
        parts.append(http_title)

    ssl = record.get("ssl") or {}
    try:
        cn = (ssl["cert"]["subject"]["CN"] or "").strip()
        if cn:
            parts.append(cn)
    except (KeyError, TypeError):
        pass

    tags = record.get("tags") or []
    if isinstance(tags, list) and tags:
        parts.append(", ".join(str(t) for t in tags if t))

    cpe23 = record.get("cpe23") or []
    if isinstance(cpe23, list) and cpe23:
        parts.append(" ".join(str(c) for c in cpe23 if c))

    vulns = record.get("vulns") or {}
    if isinstance(vulns, dict) and vulns:
        ranked = sorted(
            vulns.items(),
            key=lambda kv: _max_cvss(kv[1]),
            reverse=True,
        )
        top = [cve_id for cve_id, _ in ranked[:CVE_DESC_MAX]]
        overflow = len(vulns) - len(top)
        cve_str = ", ".join(top)
        if overflow > 0:
            cve_str += f" (+{overflow} more in metadata)"
        parts.append(cve_str)

    if not parts:
        return f"open {port}/{transport} on {ip_str}"

    return " ".join(parts)


def build_metadata(record: dict[str, Any]) -> dict[str, Any] | None:
    """
    Preserve Shodan-specific fields in metadata for downstream consumers.

    BARE ignores this field. Downstream tools (reporting, ticketing) may use it.
    Returns None if none of the target fields are present.
    """
    meta: dict[str, Any] = {}

    vulns = record.get("vulns")
    if vulns:
        meta["vulns"] = vulns

    tags = record.get("tags")
    if tags:
        meta["tags"] = tags

    org = record.get("org")
    if org:
        meta["org"] = org

    hostnames = record.get("hostnames")
    if hostnames:
        meta["hostnames"] = hostnames

    location = record.get("location") or {}
    loc_out: dict[str, Any] = {}
    for key in ("country_name", "country_code", "city"):
        val = location.get(key)
        if val:
            loc_out[key] = val
    if loc_out:
        meta["location"] = loc_out

    shodan_meta = record.get("_shodan") or {}
    shodan_out: dict[str, Any] = {}
    for key in ("id", "module"):
        val = shodan_meta.get(key)
        if val:
            shodan_out[key] = val
    if shodan_out:
        meta["_shodan"] = shodan_out

    return meta if meta else None


def convert_record(record: dict[str, Any], line_num: int) -> dict[str, Any] | None:
    """
    Convert one Shodan JSONL record to a finding object.

    Returns None and logs to stderr if required fields are missing.
    """
    ip_str = (record.get("ip_str") or "").strip()
    if not ip_str:
        print(f"[skip] line {line_num}: missing ip_str", file=sys.stderr)
        return None

    port = record.get("port")
    if port is None:
        print(f"[skip] line {line_num}: missing port ({ip_str})", file=sys.stderr)
        return None

    transport = (record.get("transport") or "tcp").strip()

    fid = f"{ip_str}_{port}_{transport}"
    title = build_title(record)
    description = build_description(record)
    target = f"{ip_str}:{port}/{transport}"

    finding: dict[str, Any] = {
        "id": fid,
        "title": title,
        "description": description,
        "target": target,
    }

    severity = severity_from_vulns(record.get("vulns") or {})
    if severity:
        finding["severity"] = severity

    meta = build_metadata(record)
    if meta:
        finding["metadata"] = meta

    return finding


def convert(stream: Any) -> dict[str, Any]:
    """
    Read Shodan JSONL from a file-like object and return a findings.json document.

    Skips malformed lines after logging to stderr. Never crashes on bad input.
    """
    findings: list[dict[str, Any]] = []

    for line_num, line in enumerate(stream, start=1):
        line = line.strip() if isinstance(line, str) else line.strip()
        if not line:
            continue

        try:
            record = json.loads(line)
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"[skip] line {line_num}: JSON parse error — {exc}", file=sys.stderr)
            continue

        if not isinstance(record, dict):
            print(
                f"[skip] line {line_num}: expected JSON object, got {type(record).__name__}",
                file=sys.stderr,
            )
            continue

        result = convert_record(record, line_num)
        if result is not None:
            findings.append(result)

    if not findings:
        print("[warn] no findings produced — output document will be empty", file=sys.stderr)

    return {
        "version": 1,
        "source": SOURCE,
        "findings": findings,
    }


def main() -> None:
    """Entry point — reads from a file argument or stdin."""
    if "--version" in sys.argv:
        print(f"shodan-to-bare v{__version__} (BARE input spec v1)")
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] != "-":
        path = sys.argv[1]
        try:
            with open(path, encoding="utf-8") as fh:
                doc = convert(fh)
        except OSError as exc:
            print(f"[error] cannot open {path!r}: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        doc = convert(sys.stdin)

    json.dump(doc, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
