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

---

## Quick Start

### 1. Install
Download the latest pre-built binary from the [Releases](https://github.com/Nicholas-Kloster/BARE/releases) page:

```bash
chmod +x bare-linux-x86_64
./bare-linux-x86_64 --help
```

### 2. Run an Example
Try it against the bundled sample findings:

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

---

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

## Technical Details
- **Model:** `sentence-transformers/all-MiniLM-L6-v2` (L2-normalized 384-dim vectors).
- **Corpus:** 3,904 Metasploit modules (2,647 exploits + 1,257 auxiliary).
- **Inference:** Powered by HuggingFace's Candle framework.
- **Parity:** Validated against Python reference vectors in CI.

## Build From Source
Requires Rust 1.70+.

```bash
git clone https://github.com/Nicholas-Kloster/BARE
cd BARE
# Fetch model weights (once)
curl -L -o assets/model.safetensors https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/model.safetensors
cargo build --release
```

---
*License: Dual-licensed under MIT and Apache 2.0.*
