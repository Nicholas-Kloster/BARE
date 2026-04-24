# BARE Input Format v1

BARE reads a normalized JSON document describing security findings from any source — a scanner, a manual pentest, a threat intel feed, or any other tool that can describe what it found in natural language.

BARE itself does not parse tool-specific formats. Adapters convert from source formats (nuclei JSON, nmap XML, aimap JSON, etc.) into this format. This keeps BARE decoupled from any single upstream tool and makes the ecosystem composable.

## Schema

```json
{
  "version": 1,
  "source": "string",
  "findings": [
    {
      "id": "string",
      "title": "string",
      "description": "string",
      "target": "string (optional)",
      "severity": "string (optional)",
      "metadata": {}
    }
  ]
}
```

## Fields

### Top level

| Field      | Required | Type   | Description                                             |
|------------|----------|--------|---------------------------------------------------------|
| version    | yes      | int    | Schema version. Currently `1`.                          |
| source     | yes      | string | Identifier for the tool that produced this file.        |
| findings   | yes      | array  | One or more finding objects.                            |

### Finding object

| Field       | Required | Type   | Description                                                          |
|-------------|----------|--------|----------------------------------------------------------------------|
| id          | yes      | string | Stable identifier from the source tool.                              |
| title       | yes      | string | Short human-readable name of the finding.                            |
| description | yes      | string | Natural-language text BARE encodes and searches against.             |
| target      | no       | string | URL, hostname, or IP where finding was observed.                     |
| severity    | no       | string | One of: `info`, `low`, `medium`, `high`, `critical`.                 |
| metadata    | no       | object | Free-form structured data. BARE ignores this; downstream may use it. |

## Design Decisions

### Why `description` is the only required content field

BARE's job is semantic matching. The only thing it needs is text to encode. Adapters must produce rich, descriptive text that captures what the finding actually is — vague or empty descriptions produce poor rankings.

A good description includes:
- What the vulnerability is
- What the affected service or component is
- How it can be exploited

Adapters should concatenate relevant fields from the source tool to build a useful description rather than dropping any single sparse field in.

### Why `metadata` exists

Source tools often carry data BARE doesn't need but downstream consumers might — CVE references, CVSS scores, affected versions, raw HTTP response bodies. The `metadata` field lets adapters pass this through without polluting the core schema. BARE itself never reads it.

### Why we version from 1, not 0

Version byte mirrors the BARE corpus binary format (see FORMAT.md). v1 is the shipping format. Future changes increment the version; BARE may support multiple versions concurrently or reject unknown versions explicitly.

## Example

```json
{
  "version": 1,
  "source": "nuclei",
  "findings": [
    {
      "id": "CVE-2023-22527",
      "title": "Atlassian Confluence RCE via template injection",
      "description": "Unauthenticated remote code execution in Atlassian Confluence Server and Data Center via OGNL template injection. Affects versions 8.0.x through 8.5.3. Attacker sends a crafted POST request to trigger arbitrary command execution as the Confluence process user.",
      "target": "https://confluence.example.com",
      "severity": "critical",
      "metadata": {
        "cvss": 9.8,
        "cve": "CVE-2023-22527",
        "template_id": "CVE-2023-22527"
      }
    }
  ]
}
```

## Validation

Readers should verify:
1. `version` is present and equals `1`
2. `source` is a non-empty string
3. `findings` is a non-empty array
4. Each finding has non-empty `id`, `title`, and `description` strings
5. If present, `severity` is one of the five allowed values (case-insensitive)

Readers should reject malformed input with a clear error rather than silently degrading.
