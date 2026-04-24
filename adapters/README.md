# BARE Adapters

Adapters are small programs that convert source-specific scanner output into [BARE's universal findings format](../INPUT_FORMAT.md). BARE itself speaks one language: `findings.json`. Adapters do the translation.

## Why adapters exist

BARE's job is semantic matching — encoding text and ranking it against a corpus. It has no interest in the specifics of how nuclei formats a CVE finding, how nmap represents an open port, or how aimap describes an exposed inference endpoint. If BARE had to understand every scanner's output format, it would become a parser first and a search engine second.

Adapters keep these concerns separate. Each adapter is a small, purpose-built converter that knows one source format deeply and produces output that BARE can consume without modification. The result is a composable ecosystem: new scanners get adapters, not patches to BARE.

## The adapter contract

Every adapter must:

1. **Read** source-tool output from stdin or a file path argument
2. **Emit** a valid `findings.json` document to stdout, conforming to [INPUT_FORMAT.md](../INPUT_FORMAT.md)
3. **Log** skip/error events to stderr — never to stdout, which is reserved for the output document
4. **Not crash** on malformed input — log the bad line and continue

The interface is Unix-composable by design:

```sh
# File mode
python nuclei_to_bare.py scan.jsonl > findings.json

# Pipe mode
nuclei -u https://target.com -j | python nuclei_to_bare.py | bare
```

## Writing a new adapter

**1. Study the source format.** Read the tool's output documentation. Run it against a real target and inspect the actual JSON. Don't assume field names match the docs.

**2. Map fields to findings.json.** Reference [INPUT_FORMAT.md](../INPUT_FORMAT.md) for the authoritative schema. Every adapter must produce `id`, `title`, and `description` for each finding.

**3. Invest in `description`.** This is the field BARE encodes and searches against. Sparse descriptions produce poor rankings. Concatenate everything useful: the finding name, technical description, affected component, CVE identifiers, matched patterns. A one-line description wastes the embedding.

**4. Preserve source data in `metadata`.** CVE references, CVSS scores, raw response snippets, affected versions — put them in `metadata`. BARE ignores this field; downstream consumers (reporting tools, ticketing systems) may not.

**5. Validate before releasing.** Run your adapter against the sample files in this directory and verify the output passes the checks in INPUT_FORMAT.md:
- `version` == 1
- `source` is non-empty
- `findings` is a non-empty array
- Every finding has non-empty `id`, `title`, `description`
- `severity` values are one of: `info`, `low`, `medium`, `high`, `critical`

**6. No dependencies.** Adapters should run with the standard library of their host language. A scanner adapter that requires a pip install is a friction point; a single `.py` file that works anywhere Python runs is not.

## Maintained adapters

| Adapter | Source | Language | Location |
|---------|--------|----------|----------|
| nuclei  | [Nuclei](https://github.com/projectdiscovery/nuclei) JSONL | Python | `adapters/nuclei/` |
| nmap    | [nmap](https://nmap.org/) XML (`-oX`) | Python | `adapters/nmap/` |
