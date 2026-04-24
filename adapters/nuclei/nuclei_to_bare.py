#!/usr/bin/env python3
"""
nuclei_to_bare.py
─────────────────
Converts Nuclei JSONL output to BARE's findings.json format.

Usage:
    nuclei -u https://target.com -j | python nuclei_to_bare.py
    python nuclei_to_bare.py scan.jsonl
    python nuclei_to_bare.py scan.jsonl > findings.json

Conforms to INPUT_FORMAT.md v1.
"""

import json
import sys
from typing import Any

__version__ = "1.0.0"
SOURCE = "nuclei"
SEVERITY_VALID = {"info", "low", "medium", "high", "critical"}


def build_description(finding: dict[str, Any]) -> str:
    """
    Construct a rich description string from a nuclei finding.

    BARE encodes this field for semantic search — sparse descriptions produce
    poor rankings. Pull everything useful into a single paragraph.
    """
    info = finding.get("info", {})
    parts: list[str] = []

    name = info.get("name", "").strip()
    if name:
        parts.append(name)

    description = info.get("description", "").strip()
    if description:
        parts.append(description)

    # CVE and classification identifiers
    classification = info.get("classification", {})
    cve_ids = classification.get("cve-id", [])
    if isinstance(cve_ids, str):
        cve_ids = [cve_ids]
    for cve in cve_ids:
        if cve and cve.strip():
            parts.append(f"CVE: {cve.strip()}")

    cwe_ids = classification.get("cwe-id", [])
    if isinstance(cwe_ids, str):
        cwe_ids = [cwe_ids]
    for cwe in cwe_ids:
        if cwe and cwe.strip():
            parts.append(f"CWE: {cwe.strip()}")

    # Template/matcher context
    matcher_name = finding.get("matcher-name", "").strip()
    if matcher_name:
        parts.append(f"Matched: {matcher_name}")

    # Extracted evidence — truncate to keep description focused
    extracted = finding.get("extracted-results", [])
    if extracted and isinstance(extracted, list):
        snippet = "; ".join(str(r) for r in extracted[:3]).strip()
        if snippet:
            parts.append(f"Extracted: {snippet[:200]}")

    # Tags add searchable context
    tags = info.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")

    return ". ".join(p.rstrip(".") for p in parts if p) + "."


def build_metadata(finding: dict[str, Any]) -> dict[str, Any]:
    """
    Pack source-specific fields into metadata for downstream consumers.
    BARE itself ignores this field.
    """
    info = finding.get("info", {})
    meta: dict[str, Any] = {}

    for key in ("name", "severity", "tags", "reference", "classification"):
        val = info.get(key)
        if val is not None:
            meta[key] = val

    for key in ("template-id", "template-url", "matcher-name", "extracted-results",
                 "curl-command", "ip", "timestamp", "host"):
        val = finding.get(key)
        if val is not None:
            meta[key] = val

    request = finding.get("request", "").strip()
    if request:
        meta["request"] = request[:1000]

    response = finding.get("response", "").strip()
    if response:
        meta["response"] = response[:500]

    return meta


def normalize_severity(raw: str | None) -> str | None:
    """Return a valid BARE severity string or None."""
    if not raw:
        return None
    normalized = raw.strip().lower()
    return normalized if normalized in SEVERITY_VALID else None


def finding_id(finding: dict[str, Any]) -> str:
    """
    Derive a stable identifier from the nuclei finding.

    Prefer template-id. Fall back to info.name slug. Never return empty.
    """
    template_id = finding.get("template-id", "").strip()
    if template_id:
        return template_id

    name = finding.get("info", {}).get("name", "").strip()
    if name:
        slug = name.lower().replace(" ", "-")
        return "".join(c for c in slug if c.isalnum() or c == "-")

    return "unknown"


def convert_line(line: str, line_num: int) -> dict[str, Any] | None:
    """
    Parse one nuclei JSONL line and return a findings.json finding object.

    Returns None and logs to stderr on parse error or missing required fields.
    """
    line = line.strip()
    if not line:
        return None

    try:
        raw = json.loads(line)
    except json.JSONDecodeError as exc:
        print(f"[skip] line {line_num}: JSON parse error — {exc}", file=sys.stderr)
        return None

    if not isinstance(raw, dict):
        print(f"[skip] line {line_num}: expected JSON object, got {type(raw).__name__}", file=sys.stderr)
        return None

    fid = finding_id(raw)
    title = raw.get("info", {}).get("name", "").strip() or fid
    description = build_description(raw)

    if not description.strip().rstrip("."):
        print(f"[skip] line {line_num}: empty description for finding '{fid}'", file=sys.stderr)
        return None

    out: dict[str, Any] = {
        "id": fid,
        "title": title,
        "description": description,
    }

    target = (raw.get("matched-at") or raw.get("host") or "").strip()
    if target:
        out["target"] = target

    severity = normalize_severity(raw.get("info", {}).get("severity"))
    if severity:
        out["severity"] = severity

    meta = build_metadata(raw)
    if meta:
        out["metadata"] = meta

    return out


def convert(stream) -> dict[str, Any]:
    """
    Read nuclei JSONL from a file-like object and return a complete findings.json document.
    """
    findings: list[dict[str, Any]] = []

    for line_num, line in enumerate(stream, start=1):
        result = convert_line(line, line_num)
        if result is not None:
            findings.append(result)

    return {
        "version": 1,
        "source": SOURCE,
        "findings": findings,
    }


def main() -> None:
    """Entry point — file argument or stdin."""
    if "--version" in sys.argv:
        print(f"nuclei_to_bare {__version__}")
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

    if not doc["findings"]:
        print("[warn] no findings produced — output document will be empty", file=sys.stderr)

    json.dump(doc, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
