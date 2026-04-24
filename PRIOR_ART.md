# Prior Art

BARE is not the first tool to embed BERT, search security databases, or target offline environments. It is the first to combine all of these in a single deployable binary. This document surveys the closest prior work honestly.

---

## EdgeBERT (2021)

**What it is:** A research project from Harvard SEAS and MIT exploring adaptive computation for efficient BERT inference on edge hardware. Published at NeurIPS 2021.

**What it does well:** Reduces BERT inference cost on constrained hardware through techniques like adaptive attention spans, early exit, and dynamic voltage/frequency scaling. Offline, semantic, and designed for resource-constrained environments.

**Why it is not BARE:** EdgeBERT is a research artifact, not a deployable tool. It targets hardware-level optimization (FPGAs, custom ASIC designs) rather than producing a general-purpose binary. There is no finding-ingestion pipeline, no security corpus, and no output format. A security practitioner cannot run EdgeBERT — they would need to build inference infrastructure on top of it.

**Relationship to BARE:** Confirms the problem is real (BERT on constrained hardware is worth solving). BARE takes a different path — static compilation rather than hardware optimization — to arrive at a deployable artifact rather than a research result.

---

## rust-bert (2020 – present)

**What it is:** A Rust NLP library by Guillaume Becquin that wraps PyTorch's C++ library (libtorch) with a Rust API. Supports BERT, RoBERTa, GPT-2, and other models.

**What it does well:** Rust interface to a wide range of transformer models. Handles tokenization, model loading, and inference without writing Python. Good ecosystem of model support.

**Why it is not BARE:** rust-bert requires libtorch to be installed as a system dependency — a C++ shared library of ~2.5GB. The resulting binary is not self-contained; it will not run on a system where libtorch is absent. Deployment requires shipping the library alongside the binary, which reintroduces the dependency management problem BARE is designed to eliminate.

Additionally, rust-bert is a library, not a complete tool. It does not include a security corpus, a finding ingestion format, or a ranking output format. A practitioner would need to build all of that on top of it.

**Relationship to BARE:** BARE uses [Candle](https://github.com/huggingface/candle) instead of libtorch for exactly this reason — Candle is pure Rust with no C++ runtime dependency, which is what makes the single-binary deployment model possible.

---

## Candle (2023 – present)

**What it is:** Hugging Face's pure-Rust ML framework. Replaces Python torch/transformers for inference workloads. No C++ runtime dependency. WASM-compatible.

**What it does well:** The building block BARE is built on. Pure Rust, no libtorch, designed for embedding in other applications. Fast and actively maintained.

**Why it is not BARE:** Candle is a library. It provides tensor operations and model loading primitives — the same relationship as torch to a Python application. A practitioner cannot run Candle; they use it to build something runnable.

**Relationship to BARE:** Candle is BARE's ML backend. BARE is what Candle looks like when you add a corpus, a findings ingestion format, a ranking output format, and compile it to a single binary. The Candle project has a BERT example in its repository; BARE extends that pattern into a complete, opinionated security tool.

---

## SearchSploit (2011 – present)

**What it is:** The command-line search interface to ExploitDB, maintained by Offensive Security. Ships as a shell script bundled with a local copy of the ExploitDB database.

**What it does well:** Offline. Security-specific. Ships as a self-contained package that works without network access. The standard tool for searching known exploits from a terminal.

**Why it is not BARE:** SearchSploit uses keyword matching. A query for "confluence template injection" will miss any ExploitDB entry that does not contain those exact words. BARE uses semantic similarity — a query for "unauthenticated RCE in a Java enterprise wiki" can surface the same result. Keyword matching works well when you know the exact product name and vulnerability class; semantic search works when you are starting from a scanner finding and do not.

**Relationship to BARE:** SearchSploit is the closest complete-tool prior art. BARE is SearchSploit with semantic matching substituted for keyword matching, Metasploit modules substituted for ExploitDB entries, and a structured findings.json ingestion format added so scanner output can drive queries without manual reformulation.

---

## Metasploit `search` (2003 – present)

**What it is:** The built-in search command in Metasploit Framework. Searches the loaded module set by name, platform, CVE, and other metadata fields.

**What it does well:** Offline. Security-specific. No separate tool to install — if Metasploit is present, `search` is present. Supports structured filters (type:exploit, cve:2023-22527, platform:linux).

**Why it is not BARE:** Metasploit `search` requires a running Metasploit installation — Ruby runtime, bundler, gem dependencies, and the full module tree. It is not a standalone binary. It also uses keyword and metadata matching rather than semantic similarity. A finding from nuclei cannot be piped into Metasploit `search` without manual reformulation of the query.

**Relationship to BARE:** BARE's corpus is the Metasploit module set. BARE can be thought of as Metasploit `search` extracted into a self-contained binary, upgraded from keyword to semantic matching, and given a structured input interface so security scanner output can drive it directly.

---

## Honest Caveats

**BARE's corpus is frozen at compile time.** New Metasploit modules require regenerating corpus.bin and rebuilding the binary. SearchSploit and Metasploit `search` update when their module databases update.

**BARE's semantic model is general-purpose.** The all-MiniLM-L6-v2 model was not fine-tuned on security text. Rankings reflect semantic proximity in general English, not security-domain expertise. A model fine-tuned on CVE descriptions, exploit writeups, and vulnerability reports would produce sharper results.

**BARE returns Metasploit modules, not a full attack chain.** It narrows the search space; a practitioner still needs to select, configure, and execute the relevant module. This is the same limitation as SearchSploit and Metasploit `search`.

**No tool does all five.** The comparison table in the README represents the current state honestly. If a tool appears that combines offline deployment, semantic matching, single-binary distribution, security specificity, and end-to-end usability, this document should be updated.
