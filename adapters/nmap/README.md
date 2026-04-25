# nmap_to_bare

Converts [nmap](https://nmap.org/) XML output (`-oX`) to BARE's `findings.json` format. One finding is emitted per open port. Closed and filtered ports are not emitted.

## Usage

```sh
# Pipe directly from nmap
nmap -sV -oX - target.com | python nmap_to_bare.py

# File mode
python nmap_to_bare.py scan.xml

# Full pipeline
nmap -sV -oX - 192.168.1.0/24 | python nmap_to_bare.py | bare --top 5
```

Reads from `stdin` if no argument is given (or argument is `-`). Outputs valid `findings.json` to stdout. Skip and error events go to stderr.

## Requirements

Standard library only. Requires Python 3.10+. Nothing to install.

## Field Mapping

| findings.json field | Source in nmap XML                                                             |
|---------------------|--------------------------------------------------------------------------------|
| `id`                | `"{protocol}_{portid}_{host_address}"` — e.g. `tcp_80_192.168.1.10`           |
| `title`             | `service/@name` + `service/@product` — e.g. `http (Apache httpd)`             |
| `description`       | Concatenated (see below)                                                       |
| `target`            | `"{host_address}:{portid}/{protocol}"` — e.g. `192.168.1.10:80/tcp`           |
| `severity`          | **Not emitted.** nmap does not produce severity data.                          |
| `metadata`          | `script/@id` + `script/@output` for any NSE scripts present on the port       |

### Description construction

BARE encodes `description` for semantic search — this is where quality matters.

The adapter concatenates in order, skipping empty values:
1. `service/@name`
2. `service/@product`
3. `service/@version`
4. `service/@ostype`
5. `service/@extrainfo`

Examples:
- `"ssh OpenSSH 8.9p1 Ubuntu 3ubuntu0.7 Linux Ubuntu Linux; protocol 2.0"`
- `"http Apache httpd 2.4.49"`
- `"postgresql PostgreSQL DB 9.6.0 or later"`

If nmap could not identify the service at all: `"open {protocol} port {portid}"`.

**Design constraint:** no vulnerability context is added beyond what nmap reported. If nmap sees `Apache httpd 2.4.49`, the description says `Apache httpd 2.4.49` — not `Apache httpd 2.4.49 known to be vulnerable to CVE-...`. Mechanical translation only.

## Supported nmap Versions

Tested against nmap 7.x XML output (`xmloutputversion="1.05"`). The adapter uses the standard nmap XML DTD structure: `nmaprun → host → ports → port → service/script`.

Requires nmap to be run with version detection (`-sV`) to get useful `product` and `version` fields. Without `-sV`, most service elements will be empty and BARE's semantic matches will be less precise.

## Examples

Input and output examples are in the `examples/` directory:
- `nmap_sample.xml` — 3 hosts, 11 open ports across HTTP/SSH/DB/RDP/SMB
- `findings.json` — adapter output, valid against `schemas/input.schema.json` (this is BARE's *input*, not its output)

```sh
python nmap_to_bare.py examples/nmap_sample.xml
# → 11 findings across 3 hosts
```

## Known Limitations

- **Service discovery, not vulnerability findings.** nmap reports what is running — not whether it is exploitable. BARE will return best-effort semantic matches (Metasploit modules related to the detected service), but scores will typically be lower than with a vulnerability scanner like nuclei, which anchors findings to specific CVEs.

- **No severity field.** nmap produces no severity data. The `severity` field is never emitted by this adapter.

- **Closed and filtered ports are not emitted.** Only `state="open"` ports produce findings. This is intentional — closed and filtered ports convey no actionable service information.

- **Script output is metadata, not description.** NSE script results (e.g. `http-title`, `ssl-cert`) are preserved in `metadata.scripts` but not incorporated into the description. Including them would add noise that dilutes the core service signal for semantic search.
