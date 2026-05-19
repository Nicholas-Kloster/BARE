# BARE Output Format v1

BARE emits a structured JSON document describing ranked module matches for each input finding. This document is designed to be both human-readable when pretty-printed and machine-parseable for downstream tooling.

The format mirrors the input format (`INPUT_FORMAT.md`) so BARE's output can be fed into other tools in the same ecosystem — a report generator, a ticket creator, a human-review queue, or another semantic layer.

## Schema

```json
{
  "version": 1,
  "source": "bare",
  "corpus": {
    "size": 3904,
    "sha256": "string"
  },
  "findings": [
    {
      "id": "string",
      "title": "string",
      "target": "string (optional)",
      "severity": "string (optional)",
      "matches": [
        {
          "rank": 1,
          "module": "string",
          "score": 0.78,
          "category": "string"
        }
      ]
    }
  ]
}
```

## Fields

### Top level

| Field     | Required | Type   | Description                                          |
|-----------|----------|--------|------------------------------------------------------|
| version   | yes      | int    | Output schema version. Currently `1`.                |
| source    | yes      | string | Always `"bare"`. Identifies this tool as the origin. |
| corpus    | yes      | object | Metadata about the embedded corpus used for search.  |
| findings  | yes      | array  | One entry per input finding, preserving input order. |

### Corpus object

| Field  | Required | Type   | Description                                              |
|--------|----------|--------|----------------------------------------------------------|
| size   | yes      | int    | Number of records in the embedded corpus.                |
| sha256 | yes      | string | SHA-256 hash of the corpus.bin, for reproducibility.     |

The `corpus` object exists so downstream tooling can verify which corpus produced a given result — important when BARE is versioned and the embedded corpus changes between releases.

### Finding object

| Field                    | Required | Type   | Description                                                                 |
|--------------------------|----------|--------|-----------------------------------------------------------------------------|
| id                       | yes      | string | Echoed from input finding.                                                  |
| title                    | yes      | string | Echoed from input finding.                                                  |
| target                   | no       | string | Echoed from input finding if present.                                       |
| severity                 | no       | string | Echoed from input finding if present.                                       |
| matches                  | yes      | array  | Ranked module matches. Always present; empty when sentinel fires.           |
| no_high_confidence_match | no       | bool   | `true` when `--no-match-threshold` fires. Signals the corpus has no coverage for this finding class. |
| no_match_reason          | no       | string | Human-readable explanation including top score seen and threshold applied.  |
| top_score_seen           | no       | float  | Raw top cosine score from the corpus for this finding (even if below threshold). Useful for tuning. |

**Sentinel fields** (`no_high_confidence_match`, `no_match_reason`, `top_score_seen`) are omitted from the JSON entirely when not triggered (`skip_serializing_if = "Option::is_none"`). When present, `matches` will always be an empty array — the sentinel replaces, not supplements, the matches. Downstream consumers should check for `no_high_confidence_match: true` before treating an empty `matches` array as "no exploits exist" vs "corpus doesn't cover this class."

### Match object

| Field    | Required | Type   | Description                                                     |
|----------|----------|--------|-----------------------------------------------------------------|
| rank     | yes      | int    | 1-indexed rank within this finding's matches array.             |
| module   | yes      | string | Module identifier from the corpus.                              |
| score    | yes      | float  | Cosine similarity, range 0.0 to 1.0. Higher is better match.    |
| category | yes      | string | Module category (e.g. `exploits`, `auxiliary`, `post`).         |

## Stream Contract

BARE writes exactly two streams:

| Stream | Content |
|--------|---------|
| **stdout** | The JSON output document. Nothing else. Parseable directly with `jq`, `python -m json.tool`, etc. |
| **stderr** | Progress lines (`[1/3] Loading tokenizer...`), informational markers (`[*] Encoding: <id>`), warnings (`[warn]`), and error messages. Never mixed into stdout. |

This split means the canonical pipeline — `bare < findings.json | jq .` — works without filtering. Shell redirection (`2>/dev/null`) suppresses all progress output for quiet operation.

## Design Decisions

### Why the output mirrors the input

An output format that doesn't look like the input format creates a translation tax for every downstream consumer. By keeping the shape identical — same top-level `version`, `source`, `findings` keys — any tool that already parses BARE's input can parse its output with minimal changes.

### Why score is cosine similarity, not a 0-100 confidence

Cosine similarity is the raw measurement BARE makes. Scaling it into a "confidence percentage" would be imposing a judgment the tool can't actually make — a 0.5 cosine similarity means different things for different queries and corpora. Downstream tools can normalize or threshold however they want; BARE emits the honest number.

### Why matches is always present

An empty `matches` array means BARE ran but found nothing meaningful. A missing `matches` key would be ambiguous — did BARE skip this finding? Did it crash? Did the input get malformed in transit? Always-present keys make errors explicit.

### Why corpus metadata matters

The embedded corpus defines what BARE can find. Two BARE binaries with different corpuses will produce different results for the same input. Shipping the corpus size and hash in every output means results are reproducible and auditable — critical for any environment where BARE's recommendations inform real decisions.

## Example

Input (`findings.json`):

```json
{
  "version": 1,
  "source": "nuclei",
  "findings": [
    {
      "id": "CVE-2023-22527",
      "title": "Atlassian Confluence RCE via template injection",
      "description": "Unauthenticated RCE in Confluence via OGNL template injection...",
      "target": "https://confluence.example.com",
      "severity": "critical"
    }
  ]
}
```

Output:

```json
{
  "version": 1,
  "source": "bare",
  "corpus": {
    "size": 3904,
    "sha256": "a3f2c1b8..."
  },
  "findings": [
    {
      "id": "CVE-2023-22527",
      "title": "Atlassian Confluence RCE via template injection",
      "target": "https://confluence.example.com",
      "severity": "critical",
      "matches": [
        {
          "rank": 1,
          "module": "exploits_multi_http_atlassian_confluence_namespace_ognl_injection",
          "score": 0.7823,
          "category": "exploits"
        },
        {
          "rank": 2,
          "module": "exploits_multi_http_atlassian_confluence_webwork_ognl_injection",
          "score": 0.7641,
          "category": "exploits"
        },
        {
          "rank": 3,
          "module": "exploits_multi_http_confluence_widget_connector",
          "score": 0.6982,
          "category": "exploits"
        }
      ]
    }
  ]
}
```

## Validation

Consumers should verify:
1. `version` is present and equals `1`
2. `source` is present and equals `"bare"`
3. `corpus` object contains both `size` (int) and `sha256` (string)
4. `findings` is an array (may be empty if input had no findings)
5. Each finding has non-empty `id`, `title`, and a `matches` array (may be empty)
6. Each match has `rank`, `module`, `score` (0.0-1.0), and `category`
7. Matches within a finding are sorted by `rank` ascending (rank 1 first)
