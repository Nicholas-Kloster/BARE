# nuclei_to_bare

Converts [Nuclei](https://github.com/projectdiscovery/nuclei) JSONL output to BARE's `findings.json` format.

## Usage

```sh
# Pipe directly from nuclei
nuclei -u https://target.com -j | python nuclei_to_bare.py

# File mode
python nuclei_to_bare.py scan.jsonl

# Full pipeline
nuclei -u https://target.com -j | python nuclei_to_bare.py | bare "unauthenticated RCE"
```

Reads from `stdin` if no argument is given (or argument is `-`). Outputs valid `findings.json` to stdout. Skip/error events go to stderr.

## Field Mapping

| findings.json field | Source in nuclei JSONL                                                             |
|---------------------|------------------------------------------------------------------------------------|
| `id`                | `template-id` → slugified `info.name` fallback                                    |
| `title`             | `info.name`                                                                        |
| `description`       | Concatenated (see below)                                                           |
| `target`            | `matched-at` → `host` fallback                                                     |
| `severity`          | `info.severity` (normalized to lowercase; dropped if not in allowed set)           |
| `metadata`          | All remaining nuclei fields (classification, references, request/response, etc.)   |

### Description construction

BARE encodes `description` for semantic search — this is where quality matters.

The adapter concatenates in order:
1. `info.name`
2. `info.description`
3. `info.classification.cve-id` entries (prefixed `CVE:`)
4. `info.classification.cwe-id` entries (prefixed `CWE:`)
5. `matcher-name` (prefixed `Matched:`)
6. First 3 `extracted-results` entries, truncated to 200 chars (prefixed `Extracted:`)
7. `info.tags` (prefixed `Tags:`)

A finding with all fields produces a description with ~8 sentences of semantic signal. A finding with only `info.name` and `info.description` still passes — those two alone provide enough embedding surface for most queries.

## Examples

Input (`nuclei_sample.jsonl`) and adapter output (`findings.json` — conforms to BARE input schema) are in the `examples/` directory.

```sh
python nuclei_to_bare.py examples/nuclei_sample.jsonl
# → 5 findings, severities: critical, critical, high, medium, low
```

## Known Limitations

- `info.tags` on some older Nuclei versions is a comma-separated string rather than an array. The adapter handles both.
- `extracted-results` is capped at 3 entries, each truncated to 200 characters, to keep descriptions focused. Full results are preserved in `metadata.extracted-results`.
- Nuclei's `info` severity `unknown` is dropped (not in the BARE allowed set). Log a warning if you see this.
- Request/response bodies in `metadata` are capped at 1000 and 500 bytes respectively.

## Requirements

Standard library only. Requires Python 3.10+ (uses `str | None` union syntax in type hints).
