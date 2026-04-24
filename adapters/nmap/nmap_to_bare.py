#!/usr/bin/env python3
"""
nmap_to_bare.py
───────────────
Converts nmap XML output to BARE's findings.json format.

One finding is emitted per open port. Closed and filtered ports are skipped.

Usage:
    cat scan.xml | python nmap_to_bare.py
    python nmap_to_bare.py scan.xml
    nmap -sV -oX - target.com | python nmap_to_bare.py | bare

Conforms to INPUT_FORMAT.md v1.
Design constraint: mechanical translation only. No vulnerability context
is added beyond what nmap actually reported.
"""

import io
import json
import sys
import xml.etree.ElementTree as ET
from typing import Any

__version__ = "1.0.0"
SOURCE = "nmap"


def build_title(service: ET.Element | None, protocol: str, portid: str) -> str:
    """
    Construct a short human-readable title for a port finding.

    Combines service name and product when available. Falls back to
    protocol/portid if nmap could not identify the service.
    """
    if service is None:
        return f"{protocol}/{portid}"

    name = service.get("name", "").strip()
    product = service.get("product", "").strip()

    if name and product:
        return f"{name} ({product})"
    if name:
        return name
    if product:
        return product
    return f"{protocol}/{portid}"


def build_description(service: ET.Element | None, protocol: str, portid: str) -> str:
    """
    Construct a description by mechanically concatenating available nmap fields.

    Concatenates in order: name, product, version, ostype, extrainfo.
    Only non-empty values are included. No vulnerability context is added —
    only what nmap actually reported.

    Falls back to "open {protocol} port {portid}" if no service data exists.
    """
    if service is None:
        return f"open {protocol} port {portid}"

    parts: list[str] = []
    for attr in ("name", "product", "version", "ostype", "extrainfo"):
        val = service.get(attr, "").strip()
        if val:
            parts.append(val)

    if not parts:
        return f"open {protocol} port {portid}"

    return " ".join(parts)


def build_metadata(port: ET.Element) -> dict[str, Any] | None:
    """
    Extract NSE script results from a <port> element into the metadata field.

    Returns None if no <script> child elements are present, so the caller
    can omit the metadata key entirely per INPUT_FORMAT.md.
    """
    scripts = port.findall("script")
    if not scripts:
        return None

    entries = [
        {"id": s.get("id", ""), "output": s.get("output", "")}
        for s in scripts
        if s.get("id")
    ]
    return {"scripts": entries} if entries else None


def finding_id(protocol: str, portid: str, host_addr: str) -> str:
    """Return a stable, unique identifier for this open port on this host."""
    return f"{protocol}_{portid}_{host_addr}"


def convert_port(port: ET.Element, host_addr: str) -> dict[str, Any] | None:
    """
    Convert one nmap <port> element to a finding object.

    Returns None for any non-open port or any port missing required data.
    Logs skip events to stderr.
    """
    state_el = port.find("state")
    if state_el is None or state_el.get("state") != "open":
        return None

    protocol = port.get("protocol", "tcp").strip()
    portid = port.get("portid", "").strip()

    if not portid:
        print(f"[skip] host {host_addr}: port element missing portid", file=sys.stderr)
        return None

    service = port.find("service")

    fid = finding_id(protocol, portid, host_addr)
    title = build_title(service, protocol, portid)
    description = build_description(service, protocol, portid)
    target = f"{host_addr}:{portid}/{protocol}"

    finding: dict[str, Any] = {
        "id": fid,
        "title": title,
        "description": description,
        "target": target,
    }

    meta = build_metadata(port)
    if meta:
        finding["metadata"] = meta

    return finding


def convert_host(host: ET.Element) -> list[dict[str, Any]]:
    """
    Convert all open ports on one nmap <host> element to findings.

    Skips hosts that are not up. Returns an empty list if the host has no
    open ports or is missing required address information.
    """
    status = host.find("status")
    if status is None or status.get("state") != "up":
        return []

    host_addr: str | None = None
    for addr in host.findall("address"):
        if addr.get("addrtype") == "ipv4":
            host_addr = addr.get("addr", "").strip()
            break
    if not host_addr:
        for addr in host.findall("address"):
            if addr.get("addrtype") == "ipv6":
                host_addr = addr.get("addr", "").strip()
                break

    if not host_addr:
        print("[skip] host element has no usable address", file=sys.stderr)
        return []

    ports_el = host.find("ports")
    if ports_el is None:
        return []

    findings: list[dict[str, Any]] = []
    for port in ports_el.findall("port"):
        result = convert_port(port, host_addr)
        if result is not None:
            findings.append(result)

    return findings


def convert(source: Any) -> dict[str, Any]:
    """
    Parse nmap XML from a file path string or file-like object.

    Returns a complete findings.json document. Exits non-zero on XML parse
    failure — malformed input is unrecoverable for an XML-only format.
    """
    try:
        tree = ET.parse(source)
    except ET.ParseError as exc:
        print(f"[error] XML parse failed: {exc}", file=sys.stderr)
        sys.exit(1)

    root = tree.getroot()
    if root.tag != "nmaprun":
        print(
            f"[warn] root element is '{root.tag}', expected 'nmaprun' — proceeding anyway",
            file=sys.stderr,
        )

    findings: list[dict[str, Any]] = []
    for host in root.findall("host"):
        findings.extend(convert_host(host))

    if not findings:
        print(
            "[warn] no open ports found — output document will have empty findings",
            file=sys.stderr,
        )

    return {
        "version": 1,
        "source": SOURCE,
        "findings": findings,
    }


def main() -> None:
    """Entry point — reads from a file argument or stdin."""
    if "--version" in sys.argv:
        print(f"nmap-to-bare v{__version__} (BARE input spec v1)")
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] != "-":
        path = sys.argv[1]
        try:
            doc = convert(path)
        except OSError as exc:
            print(f"[error] cannot open {path!r}: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        doc = convert(io.BytesIO(sys.stdin.buffer.read()))

    json.dump(doc, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
