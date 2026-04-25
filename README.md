```text
    ____  ___    ____  ______
   / __ )/   |  / __ \/ ____/
  / __  / /| | / /_/ / __/
 / /_/ / ___ |/ _, _/ /___
/_____/_/  |_/_/ |_/_____/

                           by NuClide
```

# BARE

[![CI](https://github.com/Nicholas-Kloster/BARE/actions/workflows/ci.yml/badge.svg)](https://github.com/Nicholas-Kloster/BARE/actions/workflows/ci.yml)

Binary Anywhere Rust Encoder. Semantic search for security scanner output, compiled into a single binary.

## What It Does

BARE takes findings from a security scanner and ranks Metasploit modules by semantic relevance. It runs as one executable. No Python runtime. No external services. No network calls.

Pipe a nuclei scan in, get ranked exploits out:

```
nuclei -u https://target.com -j | nuclei_to_bare.py | bare
```

That is the entire pipeline.

## What Makes BARE Different

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

The binary contains everything. BERT encoder, tokenizer, full Metasploit corpus. No Rust toolchain required.

## Quick Start

To build from source instead (requires Rust 1.70+):

```
git clone https://github.com/Nicholas-Kloster/BARE
cd BARE
cargo build --release
```

Try it against the bundled example:

```
cat adapters/nuclei/examples/nuclei_sample.jsonl \
  | python adapters/nuclei/nuclei_to_bare.py \
  | ./target/release/bare --top 3
```

You should see output like (truncated):

```json
{
  "version": 1,
  "source": "bare",
  "corpus": { "size": 3904, "sha256": "b071d1c9..." },
  "findings": [
    {
      "id": "CVE-2023-22527",
      "title": "Atlassian Confluence SSTI RCE",
      "severity": "critical",
      "matches": [
        { "rank": 1, "module": "exploits_multi_http_atlassian_confluence_rce_cve_2023_22527", "score": 0.8322, "category": "exploits" },
        { "rank": 2, "module": "exploits_multi_http_atlassian_confluence_rce_cve_2024_21683", "score": 0.7472, "category": "exploits" },
        { "rank": 3, "module": "exploits_multi_http_atlassian_confluence_unauth_backup",      "score": 0.7341, "category": "exploits" }
      ]
    }
  ]
}
```

Each finding produces a ranked list of the most semantically similar modules from the embedded Metasploit corpus.

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

At build time, a Python script encodes a text corpus (currently the full Metasploit module set) into a flat binary file. That file is compiled directly into the Rust binary via `include_bytes!`. The BERT model weights are embedded the same way.

At runtime, BARE reads findings from stdin or a file, encodes each description with the embedded BERT model, and searches the baked-in corpus via cosine similarity. The output is structured JSON. One ranked list of modules per input finding.

## The Adapter Ecosystem

BARE does not parse scanner-specific output. Every source tool has its own format, and coupling BARE to any of them would make it a plugin rather than infrastructure.

Instead, BARE speaks a single universal input format: `findings.json`, documented in [INPUT_FORMAT.md](INPUT_FORMAT.md). Anyone can write a small adapter that converts a scanner's native output into this format:

```
nuclei -----+
nmap -------|
aimap ------+--> adapter --> findings.json --> bare --> ranked modules
trivy ------|
your tool --+
```

BARE's output is also structured, documented in [OUTPUT_FORMAT.md](OUTPUT_FORMAT.md), so downstream tools can consume it cleanly.

Currently shipped adapters:

- `adapters/nuclei/` — nuclei JSONL to BARE findings.json
- `adapters/nmap/` — nmap XML with NSE script output to BARE findings.json

Writing a new adapter: see [adapters/README.md](adapters/README.md) for the pattern and contract.

## Current Status

Single binary (~101MB on Linux x86_64) containing:

- Embedded BERT encoder weights (sentence-transformers/all-MiniLM-L6-v2)
- Embedded tokenizer
- Embedded corpus of 3,904 pre-encoded Metasploit module descriptions
- Search logic and output schema enforcement

Reads `findings.json` from stdin or file. Emits structured ranked output per OUTPUT_FORMAT.md.

Rust output vectors match Python sentence-transformers output to within f32/f64 rounding error (~1e-7 delta). Tested across five distinct Metasploit module categories. Discrimination is semantic, not keyword-based.

### Known Ranking Behavior

Auxiliary scanner modules tend to outrank exploit modules for queries written in probe-style language (keywords like "unauthenticated", "injection", "traversal"). Scanner descriptions are written more explicitly than exploit descriptions, so their embeddings sit closer to probe-language queries by construction. Both types appear in the top 5 for most queries. This is descriptive-style drift, not a semantic error.

The shallow fix is category-aware ranking. The deeper fix is fine-tuning the encoder on Metasploit, Exploit-DB, and nuclei template text rather than relying on a general-English MiniLM checkpoint. Category-aware ranking ships first because it does not require retraining.

### Corpus Updates

The corpus is baked in at compile time. That is intentional for reproducibility and audit, and it is correct for the SCIF case where every byte should be hash-pinned. It is also a friction point for routine operations, since Metasploit ships modules continuously and BARE will not see them until the next rebuild.

A future variant may support an external `corpus.bin` loaded from disk at runtime, hash-verified against a value baked into the binary. That preserves the "no Python, no network, no package manager" guarantee while letting operators swap corpora without a recompile. The compile-time path stays default for environments where reproducibility is the whole point.

## What's Next

- More adapters (Trivy, Semgrep, aimap)
- Category-aware ranking for scanner vs exploit prioritization
- External hash-pinned corpus mode for non-SCIF deployments
- Domain-specific encoder fine-tune (Metasploit + Exploit-DB + nuclei templates)
- Performance benchmarks at full corpus scale

## Build From Source

```
cargo build --release
```

The binary is produced at `target/release/bare`. Everything it needs (BERT weights, tokenizer, corpus) is embedded at compile time.

To regenerate the corpus from a newer Metasploit module set:

```
python serialize.py
cargo build --release
```

This requires sentence-transformers installed in Python. Only needed if you are updating the corpus. End users who just want to run BARE do not need any Python dependencies.
