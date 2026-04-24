# Shodan Adapter

Converts Shodan JSONL output (produced by `shodan download`) to BARE's `findings.json` format.

One finding is emitted per Shodan banner record. Each record in Shodan's bulk export represents one IP:port:banner tuple. Records missing `ip_str` or `port` are skipped with a stderr message.

## Usage

**Stdin:**

```sh
cat scan_results.json | python shodan_to_bare.py | bare
```

**File argument:**

```sh
python shodan_to_bare.py scan_results.json | bare --top 5
```

**`-` reads stdin explicitly:**

```sh
gunzip -c results.json.gz | python shodan_to_bare.py - | bare
```

## Obtaining Shodan Data

This adapter does not call the Shodan API. Data collection is the user's responsibility.

Bulk export requires a Shodan account with download credits:

```sh
# Authenticate once
shodan init YOUR_API_KEY

# Download a query result (produces a .json.gz file)
shodan download --limit 1000 results_apache 'apache country:US'

# Decompress
gunzip results_apache.json.gz

# Run through the pipeline
cat results_apache.json | python adapters/shodan/shodan_to_bare.py | ./target/release/bare --top 3
```

The `shodan download` command produces one JSON object per line (JSONL). The file is gzip-compressed by default; decompress it before piping.

Alternative: `shodan host IP` for single-host banner data, `shodan search --fields ...` for filtered exports. Any Shodan output that is one JSON record per line works.

## Field Mapping

| Shodan Field | BARE Field | Notes |
|---|---|---|
| `ip_str` + `port` + `transport` | `id` | `"{ip}_{port}_{transport}"` |
| `ip_str` + `port` + `transport` | `target` | `"{ip}:{port}/{transport}"` |
| `product` | `title` (primary) | Falls back to `http.title`, then `cpe23[0]`, then `"port N/proto"` |
| `product` + `version` | `description` (lead) | Combined if both present |
| `data` | `description` | Raw banner, truncated at 500 chars |
| `http.server` | `description` | HTTP `Server:` header value |
| `http.title` | `description` | HTML page title |
| `ssl.cert.subject.CN` | `description` | TLS certificate common name |
| `tags` | `description` + `metadata.tags` | Shodan tag strings |
| `cpe23` | `description` + (metadata via `vulns`) | CPE 2.3 identifiers |
| `vulns` keys | `description` | CVE IDs appended to description |
| `vulns` CVSS scores | `severity` | Derived from max CVSS across all reported CVEs |
| `org` | `metadata.org` | Organization name |
| `hostnames` | `metadata.hostnames` | Reverse DNS entries |
| `location` | `metadata.location` | country\_name, country\_code, city |
| `_shodan.id` / `_shodan.module` | `metadata._shodan` | Shodan scan metadata |

## Severity Derivation

Severity is derived from the highest CVSS score across all CVEs in the `vulns` dict:

| CVSS Range | Severity |
|---|---|
| ≥ 9.0 | `critical` |
| ≥ 7.0 | `high` |
| ≥ 4.0 | `medium` |
| < 4.0 | `low` |

The adapter checks `cvss`, `cvss_v2`, and `cvss_v3` fields for each CVE entry and uses the maximum value found. If `vulns` is absent or contains no CVSS scores, no `severity` field is emitted.

Shodan marks most findings as `verified: false` — CVE detection is based on banner fingerprinting, not active exploitation. The derived severity reflects reported CVSS, not confirmed exploitability.

## Known Limitations

**Data staleness.** Shodan crawls the internet on a rolling basis. A banner captured weeks ago may no longer reflect the current service state. Treat findings as leads, not confirmed vulnerabilities.

**Vuln detection is not authoritative.** Shodan's CVE attribution is based on version strings extracted from banners. It produces false positives when version strings are non-standard or backported. It produces false negatives when services suppress version information. Do not treat Shodan CVE matches as confirmed exploitability.

**No API calls.** The adapter reads files only. Authentication, query execution, and download management are outside its scope.

**One finding per banner record.** If a host has multiple open ports, each appears as a separate finding. BARE ranks them independently — there is no host-level aggregation.

**Banner truncation.** Raw banner data (`data` field) is truncated at 500 characters to keep descriptions at a reasonable embedding length. Full banner content is not preserved in `metadata`.
