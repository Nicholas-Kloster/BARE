[![Claude Code Friendly](https://img.shields.io/badge/Claude_Code-Friendly-blueviolet?logo=anthropic&logoColor=white)](https://claude.ai/code)

```text
    ____  ___    ____  ______
   / __ )/   |  / __ \/ ____/
  / __  / /| | / /_/ / __/
 / /_/ / ___ |/ _, _/ /___
/_____/_/  |_/_/ |_/_____/

          Offline Semantic Exploit Mapping
          Single-binary BERT encoder for air-gapped vulnerability ranking.
```

# BARE

[![CI](https://github.com/Nicholas-Kloster/BARE/actions/workflows/ci.yml/badge.svg)](https://github.com/Nicholas-Kloster/BARE/actions/workflows/ci.yml)

**BARE** (Binary Anywhere Rust Encoder) maps security scanner findings to Metasploit modules via semantic search. It is a self-contained Rust binary with a BERT encoder and a 3,900+ exploit corpus embedded at compile time.

**No Python. No PyTorch. No Network. Just one binary.**

## The Problem
Semantic search usually requires a massive stack: a Python interpreter, `pip`, `torch`, `transformers`, and a vector database. In air-gapped networks, SCIFs, or restricted endpoints, installing this 5GB+ footprint is often impossible.

**BARE** solves this by compiling the entire pipeline—tokenizer, model weights, and corpus—into a single 101MB artifact.

## How It Works
BARE takes raw findings (via adapters) and ranks Metasploit modules by semantic relevance.

```bash
# Pipe a nuclei scan in, get ranked exploits out:
nuclei -u https://target.com -j | python adapters/nuclei/nuclei_to_bare.py | bare
```

### Why BARE is Different
| Tool                | Offline | Semantic | Single Binary | Security-Specific |
|---------------------|---------|----------|---------------|-------------------|
| SearchSploit        | Yes     | No       | Yes           | Yes               |
| Metasploit `search` | Yes     | No       | Yes           | Yes               |
| rust-bert           | No      | Yes      | No (libtorch) | No                |
| **BARE**            | **Yes** | **Yes**  | **Yes**       | **Yes**           |

While `rust-bert` requires a ~2GB `libtorch` installation, BARE uses [Candle](https://github.com/huggingface/candle) to run inference natively in Rust. The ~101MB size includes the BERT model weights (~87MB) and the pre-encoded Metasploit corpus.

Other tools solve pieces of the problem. BARE is the first to combine all five properties in a single shipping artifact:

| Tool                | Offline | Semantic | Single binary | Security-specific | Complete tool |
|---------------------|---------|----------|---------------|-------------------|---------------|
| EdgeBERT            | Yes     | Yes      | Yes           | No                | No (library)  |
| rust-bert           | No      | Yes      | No (libtorch) | No                | No (library)  |
| SearchSploit        | Yes     | No       | Yes           | Yes               | Yes           |
| Metasploit `search` | Yes     | No       | Yes           | Yes               | Partial       |
| **BARE**            | **Yes** | **Yes**  | **Yes**       | **Yes**           | **Yes**       |

BARE ships as a ~101MB Linux x86_64 binary. That is large for a CLI but small for the constraint set: a self-contained BERT encoder, tokenizer, and 3,904 pre-encoded Metasploit modules with zero external dependencies. In environments where installing Python plus torch requires escalation no one will sign off on, disk is the cheaper resource.

See [PRIOR_ART.md](PRIOR_ART.md) for the full comparison with release dates and architectural detail.

## Install

Download the latest pre-built binary from the Releases page:

```
curl -LO https://github.com/Nicholas-Kloster/BARE/releases/latest/download/bare-linux-x86_64
curl -LO https://github.com/Nicholas-Kloster/BARE/releases/latest/download/bare-linux-x86_64.sha256
sha256sum -c bare-linux-x86_64.sha256
chmod +x bare-linux-x86_64
```

The binary contains everything. BERT encoder, tokenizer, and 3,904 pre-encoded Metasploit exploit and auxiliary module descriptions. No Rust toolchain required.

## Quick Start

### 1. Install
Download the latest pre-built binary from the [Releases](https://github.com/Nicholas-Kloster/BARE/releases) page:

```
git clone https://github.com/Nicholas-Kloster/BARE
cd BARE
curl -L -o assets/model.safetensors \
  https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/model.safetensors
cargo build --release
```

The model weights (`assets/model.safetensors`, ~87MB) are gitignored due to size and must be fetched before the first build. The build embeds them into the binary via `include_bytes!` — once the binary is built, no network access is required.

Try it against the bundled example:

```bash
cat adapters/nuclei/examples/nuclei_sample.jsonl \
  | python adapters/nuclei/nuclei_to_bare.py \
  | ./bare-linux-x86_64 --top 3
```

### 3. Output
BARE produces structured JSON, mapping each finding to the most relevant Metasploit modules:

```json
{
  "id": "CVE-2023-22527",
  "title": "Atlassian Confluence SSTI RCE",
  "matches": [
    { "rank": 1, "module": "exploits/multi/http/atlassian_confluence_rce_cve_2023_22527", "score": 0.8322 },
    { "rank": 2, "module": "exploits/multi/http/atlassian_confluence_rce_cve_2024_21683", "score": 0.7472 }
  ]
}
```

Each finding produces a ranked list of the most semantically similar modules from the embedded Metasploit corpus.

## Usage

```
bare [OPTIONS] [INPUT_PATH]

OPTIONS:
    --top <N>    Number of top matches per finding (default: 3, capped to corpus size)
    --encode     Read text from stdin, print L2-normalized 384-dim vector to stdout
                 (used by the parity check — see Parity Validation below)
    --version    Print version banner and exit
    --help       Print help and exit

INPUT:
    INPUT_PATH may be a path to a findings.json file, or "-" / omitted to read stdin.
```

Status messages and warnings are written to stderr. The output JSON document is the only thing on stdout, so piping into another tool is safe.

## Why This Matters

Every other BERT implementation requires a runtime stack. Python interpreter, pip, torch, transformers, a virtual environment, and enough permissions to install all of it. BARE requires none of that. The model weights, tokenizer, corpus, and search logic are all compiled into one executable at build time.

There is a class of environments where semantic search has never been deployable. Air-gapped networks. Endpoint security tools. Embedded systems. Field-deployed hardware with no internet. Legally-isolated systems. Those environments have been stuck with keyword matching because that is all that compiles down to something portable. BARE gives them semantic understanding without changing their constraints.

A semantic search tool that requires Python and ChromaDB is a lab tool. A semantic search tool that is a single binary is a field tool. That distinction is the entire point.

## Why Rust

The Rust compiler is mechanically a static analyzer that emits binaries only after proving the program is memory-safe. Its type system, ownership model, and borrow checker verify at compile time that the program cannot have dangling pointers, double-frees, use-after-free bugs, data races, null-pointer dereferences, or buffer overflows in safe code. These checks are non-optional. The compiler refuses to produce any output until every rule is satisfied.

For a tool meant to run in environments where you cannot respond to failure, that raises the floor on operational reliability. BARE will not segfault under unexpected input. It will not race itself into corruption under pressure. It will not crash the box it lives on.

What Rust does not give you is correct tokenization, correct cosine math, or correct ranking. Those have to be earned separately. The repository documents the validation step that earned them: Rust output vectors match Python sentence-transformers output to within f32/f64 rounding error (~1e-7 delta).

Memory safety plus parity validation is the deployment promise. Not "if it compiled, it works." Closer to: if it compiled, the failure modes are the ones you can test for, not the ones the OS surprises you with at 3am in a SCIF.

## How It Works

```
   build time                        runtime
+--------------+                 +--------------+
| corpus texts |                 | query text   |
+------+-------+                 +------+-------+
       |                                |
       v                                v
+--------------+                 +--------------+
| Python       |                 | Rust encoder |
| serializer   |                 | (Candle)     |
+------+-------+                 +------+-------+
       |                                |
       v                                v
+--------------+                 +--------------+
| corpus.bin   |----include------> query vector |
+--------------+    bytes!        +------+-------+
                                         |
                                         v
                                  +--------------+
                                  | cosine sim   |
                                  | ranking      |
                                  +--------------+
```

At build time, a Python script encodes a text corpus (currently 3,904 Metasploit exploit and auxiliary module descriptions) into a flat binary file. That file is compiled directly into the Rust binary via `include_bytes!`. The BERT model weights are embedded the same way.

At runtime, BARE reads findings from stdin or a file, encodes each description with the embedded BERT model, and searches the baked-in corpus via cosine similarity. The output is structured JSON. One ranked list of modules per input finding.

## The Adapter Ecosystem
BARE is format-agnostic. It consumes a universal `findings.json` format, allowing it to work with any scanner via a simple adapter script.

| Source | Adapter Status | Best For |
|--------|----------------|----------|
| **Nuclei** | ✅ Available | Confirmed vulnerabilities and CVEs |
| **Nmap**   | ✅ Available | Service fingerprints and version strings |
| **Shodan** | ✅ Available | Bulk banner data and port exports |
| **Trivy**  | 🛠️ Planned   | Container and filesystem scans |

See [adapters/README.md](adapters/README.md) to build your own.

---

## Why Rust?
For a tool designed for restricted environments, operational reliability is non-negotiable.
- **Memory Safety:** The Rust compiler guarantees that BARE will not suffer from buffer overflows or use-after-free bugs when parsing untrusted scanner output.
- **Parity Validation:** We enforce element-wise agreement between BARE's Rust encoder and the Python `sentence-transformers` reference implementation to within `1e-7` delta.
- **Reliability:** If it compiles, the failure modes are predictable. No "3 AM segfaults" in a SCIF.

Writing a new adapter: see [adapters/README.md](adapters/README.md) for the pattern and contract.

### nuclei

Converts nuclei JSONL output (`-j` flag) to `findings.json`. One finding per nuclei result.

```sh
nuclei -u https://target.com -j | python adapters/nuclei/nuclei_to_bare.py | bare --top 5
python adapters/nuclei/nuclei_to_bare.py scan.jsonl | bare
```

The adapter builds a rich description from multiple nuclei fields — name, description, CVE/CWE IDs, matched value, extracted results, and tags — to maximize embedding surface. A finding with only `info.name` and `info.description` still works; those two alone provide enough signal for most queries.

| findings.json field | Source |
|---------------------|--------|
| `id` | `template-id`, fallback to slugified `info.name` |
| `title` | `info.name` |
| `description` | name + description + CVE/CWE IDs + matcher + extracted results + tags |
| `target` | `matched-at`, fallback to `host` |
| `severity` | `info.severity` (normalized lowercase) |
| `metadata` | all remaining nuclei fields (classification, references, request/response) |

Known limitations: `info.severity` value `unknown` is dropped. Extracted results capped at 3 entries × 200 chars; full results in `metadata`. Request/response bodies capped at 1000/500 bytes.

Full docs: [adapters/nuclei/README.md](adapters/nuclei/README.md)

### nmap

Converts nmap XML output (`-oX`) to `findings.json`. One finding per open port. Closed and filtered ports are not emitted.

```sh
nmap -sV -oX - target.com | python adapters/nmap/nmap_to_bare.py | bare --top 5
python adapters/nmap/nmap_to_bare.py scan.xml | bare
```

Run nmap with `-sV` (version detection). Without it, most service elements will be empty and BARE's matches will be less precise. The description is built from service name, product, version, OS type, and extra info — if nmap could not identify the service at all, the description falls back to `"open {protocol} port {portid}"`.

| findings.json field | Source |
|---------------------|--------|
| `id` | `"{protocol}_{portid}_{host_address}"` |
| `title` | `service/@name` + `service/@product` |
| `description` | name + product + version + ostype + extrainfo |
| `target` | `"{host_address}:{portid}/{protocol}"` |
| `severity` | not emitted — nmap produces no severity data |
| `metadata` | NSE script id + output for scripts on the port |

Known limitations: nmap reports running services, not confirmed vulnerabilities — scores will typically be lower than nuclei output. NSE script output is preserved in `metadata.scripts` but not included in the description (adding it buries the core service signal).

Full docs: [adapters/nmap/README.md](adapters/nmap/README.md)

### shodan

Converts Shodan JSONL bulk export (`shodan download`) to `findings.json`. One finding per banner record.

```sh
shodan download --limit 1000 results 'apache country:US'
gunzip results.json.gz
cat results.json | python adapters/shodan/shodan_to_bare.py | bare --top 5
```

The adapter does not call the Shodan API — data collection is the user's responsibility. The description is assembled from product, version, raw banner data, HTTP server header, TLS CN, CPE identifiers, Shodan tags, and CVE IDs. Severity is derived from the highest CVSS score across all reported CVEs.

| findings.json field | Source |
|---------------------|--------|
| `id` | `"{ip}_{port}_{transport}"` |
| `title` | `product`, fallback to `http.title` → `cpe23[0]` → `"port N/proto"` |
| `description` | product + version + banner + HTTP server + TLS CN + tags + CPEs + CVE IDs |
| `target` | `"{ip}:{port}/{transport}"` |
| `severity` | max CVSS across `vulns` dict (≥9.0 critical, ≥7.0 high, ≥4.0 medium, <4.0 low) |
| `metadata` | org, hostnames, location, Shodan scan metadata, full `vulns` dict |

CVE list in description is capped at top-10 by CVSS. Full `vulns` dict is always in `metadata.vulns`. Raw banner truncated at 500 chars.

Known limitations: Shodan data is not real-time — banners may be weeks old. CVE attribution is based on version string matching, not active exploitation; treat findings as leads, not confirmed vulnerabilities. No host-level aggregation — multiple open ports on one host appear as separate findings.

Full docs: [adapters/shodan/README.md](adapters/shodan/README.md)

## Schema Validation

Both input and output formats have machine-readable JSON schemas in `schemas/`:

- `schemas/input.schema.json` — validates `findings.json` before BARE processes it
- `schemas/output.schema.json` — validates BARE's ranked output

The CI pipeline runs schema checks via `ajv-cli` against sample data from each adapter. If you are building a new adapter, validate against `input.schema.json` before running BARE. If you are building a consumer of BARE output, validate against `output.schema.json`.

## Corpus Generation

The corpus baked into the binary was generated in two steps. If you want to rebuild it from a fresh Metasploit snapshot:

```
# Step 1: fetch all Metasploit module descriptions from GitHub
python fetch_modules.py

# Step 2: encode descriptions into 384-dim vectors and write corpus.bin
python serialize.py

# Step 3: rebuild the binary with the new corpus embedded
cargo build --release
```

`fetch_modules.py` scrapes the Metasploit framework repository via the GitHub Trees API and concurrently downloads each `.rb` file to extract the module name and description. The unauthenticated GitHub API has a 60-requests-per-hour rate limit, which the scraper will exhaust well before fetching the full module tree. Set `GITHUB_TOKEN` in the environment, or have `gh auth login` configured — the scraper picks either up automatically.

The scraper currently targets `modules/exploits/` and `modules/auxiliary/`. `post`, `payloads`, `encoders`, `nops`, and `evasion` modules are not included in the shipped corpus. The current corpus contains 2,647 exploits and 1,257 auxiliary modules.

`serialize.py` reads `modules_full.json` (the scraper's output), loads `sentence-transformers/all-MiniLM-L6-v2`, encodes each module's `name + " " + description`, and writes the result as a little-endian binary in the format documented in [FORMAT.md](FORMAT.md).

This step requires Python with `sentence-transformers` installed. Only necessary if you are updating the corpus. End users running a pre-built binary or building from a repo clone with the existing `corpus.bin` do not need Python at all.

## Parity Validation

The Rust encoder must produce vectors that match the Python reference implementation before the binary is trusted. The Rust binary exposes its raw encoder via `bare --encode`, which reads text from stdin and prints the L2-normalized 384-dim vector to stdout — the same shape as `tools/encode_baseline.py`.

The CI pipeline runs the same query through both encoders and asserts element-wise agreement:

```
QUERY="unauthenticated remote code execution in apache struts via OGNL injection"
echo "$QUERY" | python tools/encode_baseline.py > python.vec
echo "$QUERY" | bare --encode > rust.vec
python tools/parity_check.py python.vec rust.vec --threshold 1e-5
```

The threshold is tighter in practice (~1e-7 on most inputs); 1e-5 is the floor that accounts for f32/f64 rounding in edge cases. If `parity_check.py` finds any element-wise delta above the threshold, it prints the top-5 worst offenders and exits non-zero. The CI build fails on parity mismatch.

## Current Status

Single binary (~101MB on Linux x86_64) containing:

- Embedded BERT encoder weights (sentence-transformers/all-MiniLM-L6-v2)
- Embedded tokenizer
- Embedded corpus of 3,904 pre-encoded Metasploit module descriptions (2,647 exploits + 1,257 auxiliary)
- Search logic and output schema enforcement

Reads `findings.json` from stdin or file. Emits structured ranked output per OUTPUT_FORMAT.md.

Rust output vectors match Python sentence-transformers output to within f32/f64 rounding error (~1e-7 delta), enforced as a hard CI gate via `bare --encode` against `tools/encode_baseline.py`. Discrimination is semantic, not keyword-based.

### Known Ranking Behavior

Auxiliary scanner modules tend to outrank exploit modules for queries written in probe-style language (keywords like "unauthenticated", "injection", "traversal"). Scanner descriptions are written more explicitly than exploit descriptions, so their embeddings sit closer to probe-language queries by construction. Both types appear in the top 5 for most queries. This is descriptive-style drift, not a semantic error.

The shallow fix is category-aware ranking. The deeper fix is fine-tuning the encoder on Metasploit, Exploit-DB, and nuclei template text rather than relying on a general-English MiniLM checkpoint. Category-aware ranking ships first because it does not require retraining.

### Corpus Updates

The corpus is baked in at compile time. That is intentional for reproducibility and audit, and it is correct for the SCIF case where every byte should be hash-pinned. It is also a friction point for routine operations, since Metasploit ships modules continuously and BARE will not see them until the next rebuild.

A future variant may support an external `corpus.bin` loaded from disk at runtime, hash-verified against a value baked into the binary. That preserves the "no Python, no network, no package manager" guarantee while letting operators swap corpora without a recompile. The compile-time path stays default for environments where reproducibility is the whole point.

## What's Next

- More adapters (Trivy, Semgrep, aimap, more)
- Category-aware ranking for scanner vs exploit prioritization
- External hash-pinned corpus mode for non-SCIF deployments
- Domain-specific encoder fine-tune (Metasploit + Exploit-DB + nuclei templates)
- Performance benchmarks at full corpus scale

## Build From Source
Requires Rust 1.70+.

Prerequisites: Rust 1.70+ (stable toolchain), and `assets/model.safetensors` in place (gitignored, fetch once — see Quick Start above).

```
cargo build --release
```

The binary is produced at `target/release/bare`. Everything it needs (BERT weights, tokenizer, corpus) is embedded at compile time.

To regenerate the corpus from a newer Metasploit module set:

```
python fetch_modules.py
python serialize.py
cargo build --release
```

This requires `sentence-transformers` installed in Python. Only needed if you are updating the corpus. End users who just want to run BARE do not need any Python dependencies.

## Use with Claude Code

Claude Code can pipe scanner output through BARE adapters and interpret the ranked Metasploit module list against your specific target context.

```
I've run `nuclei -u https://target.com -j | python adapters/nuclei/nuclei_to_bare.py | ./bare --top 5 > bare_results.json`. Read bare_results.json and for each finding tell me: which Metasploit module is the best match, what the module does, and whether it's likely exploitable given a public-facing web server with no WAF.
```

```
Run `nmap -sV -oX scan.xml target.com && python adapters/nmap/nmap_to_bare.py scan.xml | ./bare --top 3 > bare_out.json`, then analyze bare_out.json — identify any module matches with score above 0.7, explain the attack surface they represent, and suggest which to prioritize.
```

---

## License

Dual-licensed under either of:

- MIT License ([LICENSE-MIT](LICENSE-MIT))
- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE))

at your option. This is the standard Rust ecosystem dual license. Pick whichever fits your context — the MIT license for simplicity, or Apache-2.0 if you want the explicit patent grant.

The embedded model weights (`sentence-transformers/all-MiniLM-L6-v2`) are Apache-2.0. The Metasploit module descriptions used to build the corpus are BSD-3-Clause (Rapid7). Both are compatible with this dual license.
