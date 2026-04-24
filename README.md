# BARE

Binary Anywhere Rust Encoder — semantic search for security scanner output, compiled into a single binary.

## What It Does

Takes findings from a security scanner. Ranks Metasploit modules by semantic relevance. Runs as one executable with no Python runtime, no external services, no network calls.

Pipe a nuclei scan in, get ranked exploits out:

    nuclei -u https://target.com -j | nuclei_to_bare.py | bare

That is the entire pipeline.

## Quick Start

Requirements: Rust toolchain (1.70+), Python 3 (for the adapter only — not for running BARE itself).

    git clone https://github.com/Nicholas-Kloster/BARE
    cd BARE
    cargo build --release

Try it against the bundled example:

    cat adapters/nuclei/examples/nuclei_sample.jsonl \
      | python adapters/nuclei/nuclei_to_bare.py \
      | ./target/release/bare --top 3

You should see output like (truncated):

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
        },
        ...
      ]
    }

Each finding in the input produces a ranked list of the most semantically similar modules from the embedded Metasploit corpus.

## Why This Matters

Every other BERT implementation requires a runtime stack: Python interpreter, pip, torch, transformers, a virtual environment, and enough permissions to install all of it. BARE requires none of that. The model, tokenizer, corpus, and search logic are all compiled into one executable at build time.

There is a class of environments where semantic search has never been deployable: air-gapped networks, endpoint security tools, embedded systems, field-deployed hardware with no internet, legally-isolated systems. Those environments have been stuck with keyword matching because that is all that compiles down to something portable. BARE gives them semantic understanding without changing their constraints.

A semantic search tool that requires Python and ChromaDB is a lab tool. A semantic search tool that is a single binary is a field tool. That distinction is the entire point.

## Why Rust

Rust is mechanically a static analyzer that emits binaries only after proving the program is safe. Its type system, ownership model, and borrow checker verify at compile time that the program cannot have dangling pointers, double-frees, use-after-free bugs, data races, null-pointer dereferences, or buffer overflows in safe code. These checks are non-optional — the compiler refuses to produce any output until every rule is satisfied.

For a tool meant to run in environments where you cannot respond to failure, this changes the deployment promise from "probably works" to:

> If this compiled, it works.

That statement is stronger than it sounds. Most languages separate "does it work" from "is it correct" — a Python program can run for years and still have latent bugs waiting for the right input. Rust collapses those two things. Running and safe are the same statement. The compiled binary carries the compiler's original safety proof with it, executing that proof every time it runs.

## How It Works

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

At build time, a Python script encodes a text corpus (currently the full Metasploit module set) into a flat binary file. That file is compiled directly into the Rust binary via include_bytes!.

At runtime, BARE reads findings from stdin or a file, encodes each description with an embedded BERT model, and searches the baked-in corpus via cosine similarity. The output is structured JSON — one ranked list of modules per input finding.

## The Adapter Ecosystem

BARE does not parse scanner-specific output. Every source tool has its own format, and coupling BARE to any of them would make it a plugin rather than infrastructure.

Instead, BARE speaks a single universal input format — findings.json, documented in INPUT_FORMAT.md. Anyone can write a small adapter that converts a scanner's native output into this format:

    nuclei -----+
    nmap -------|
    aimap ------+--> adapter --> findings.json --> bare --> ranked modules
    trivy ------|
    your tool --+

BARE's output is also structured — documented in OUTPUT_FORMAT.md — so downstream tools can consume it cleanly.

Currently shipped adapters:
- adapters/nuclei/ — nuclei JSONL to BARE findings.json

Writing a new adapter: see adapters/README.md for the pattern and contract.

## Current Status

A single binary (~18MB on Linux x86_64):

- Embedded BERT encoder (sentence-transformers/all-MiniLM-L6-v2)
- Embedded corpus of 3,904 pre-encoded Metasploit module descriptions
- Reads findings.json from stdin or file
- Emits structured ranked output per OUTPUT_FORMAT.md

Rust output vectors match Python sentence-transformers output to within f32/f64 rounding error (~1e-7 delta). Tested across 5 distinct Metasploit module categories — discrimination is semantic, not keyword-based.

### Known Ranking Behavior

Auxiliary scanner modules tend to outrank exploit modules for queries written in probe-style language (keywords like "unauthenticated", "injection", "traversal") because scanner descriptions are written more explicitly than exploit descriptions. This is descriptive style, not a semantic error — both types appear in the top 5 for most queries.

## What's Next

- More adapters (nmap, Trivy, Semgrep)
- Category-aware ranking to address scanner-vs-exploit prioritization
- Pre-built release binaries on GitHub Releases
- Performance benchmarks at full corpus scale

## Build From Source

    cargo build --release

The binary is produced at target/release/bare. Everything it needs — the BERT encoder, the tokenizer, the corpus — is embedded at compile time.

To regenerate the corpus from a newer Metasploit module set:

    python serialize.py
    cargo build --release

This requires sentence-transformers installed in Python. Only needed if you are updating the corpus — end users who just want to run BARE do not need any Python dependencies.
