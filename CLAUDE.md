# BARE

**B**inary **A**nywhere **R**ust **E**ncoder — offline semantic exploit mapping. A self-contained Rust binary with a BERT encoder + 3,904 pre-encoded Metasploit modules baked in at compile time. Pipe scanner findings (nuclei / nmap / shodan via adapters) in, get semantically-ranked Metasploit modules out. ~101 MB single binary, no Python, no PyTorch, no network. Designed for SCIFs, air-gapped networks, and restricted endpoints.

## Language
Rust (Candle for inference; sentence-transformers all-MiniLM-L6-v2 embedded as model weights)

## Build & Run
```
# Pre-built binary (recommended)
curl -LO https://github.com/Nicholas-Kloster/BARE/releases/latest/download/bare-linux-x86_64
chmod +x bare-linux-x86_64

# Or build from source (requires Rust toolchain + downloaded model weights)
git clone https://github.com/Nicholas-Kloster/BARE
cd BARE
curl -L -o assets/model.safetensors <release-model-URL>
cargo build --release

# Use
nuclei -u https://target.com -j | python adapters/nuclei/nuclei_to_bare.py | bare
nmap -sV -oX scan.xml target.com && python adapters/nmap/nmap_to_bare.py scan.xml | bare --top 5

# tests
cargo test
```

## Layout
```
src/                    # Rust source — encoder, CLI, ranker
Cargo.toml              # Rust dependencies (candle-core, candle-transformers, tokenizers)
corpus.bin              # 3,904 pre-encoded Metasploit module embeddings (~6 MB)
assets/                 # model.safetensors (BERT weights, downloaded at build time)
adapters/               # input format converters (Python helpers — NOT the runtime)
  nuclei/               # nuclei JSON -> BARE input
  nmap/                 # nmap XML -> BARE input
  shodan/               # Shodan API -> BARE input
schemas/                # input/output JSON schemas
tools/                  # corpus-rebuild + maintenance scripts
baseline.py             # Python baseline implementation for benchmarking
fetch_modules.py        # one-time Metasploit module ingest
serialize.py            # corpus serialization helper
FORMAT.md / INPUT_FORMAT.md / OUTPUT_FORMAT.md  # interface contracts
PRIOR_ART.md            # academic-style comparison vs SearchSploit / Metasploit-search / rust-bert / EdgeBERT
LICENSE-APACHE + LICENSE-MIT  # dual-licensed (Rust convention)
```

**Note:** the Python files at the repo root (`baseline.py`, `fetch_modules.py`, `serialize.py`) are corpus-rebuild and benchmarking helpers, not part of the runtime. The binary itself is pure Rust.

## Claude Code Notes
- The README's comparison table vs other tools is the load-bearing positioning; PRIOR_ART.md is the deeper version
- Adding a new scanner adapter: drop a script under `adapters/<scanner>/` that emits the input JSON shape documented in `INPUT_FORMAT.md`
- Output JSON shape is in `OUTPUT_FORMAT.md` — consumable by any downstream finding-ranker (e.g., visorlog ingest)
- BARE pairs with VisorPlus's `assess` chain — VisorPlus pipes scanner output through BARE for exploit ranking
- Built with [Claude Code](https://claude.ai/code)
