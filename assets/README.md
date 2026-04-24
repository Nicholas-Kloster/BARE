# assets/

This directory holds the three files that get compiled into the BARE binary at build time. Two are committed to the repo; one is gitignored due to size.

## Files

| File | Size | Committed | Purpose |
|------|------|-----------|---------|
| `config.json` | ~600B | yes | BERT architecture config (hidden size, layer count, etc.) |
| `tokenizer.json` | ~456KB | yes | WordPiece tokenizer vocabulary and rules |
| `model.safetensors` | ~87MB | **no** | BERT model weights — gitignored, must be fetched before building |

## Fetching model.safetensors

`model.safetensors` is excluded from git because at 87MB it exceeds reasonable repo size limits. Anyone cloning the repo needs to download it once before building:

    curl -L -o assets/model.safetensors \
      https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/model.safetensors

This is a **compile-time** dependency, not a runtime one. Once `cargo build --release` completes, the resulting binary contains everything it needs and requires no network access to run.

## Why embed at compile time?

BARE's design goal is to run in environments where network access is unavailable or restricted: air-gapped networks, embedded systems, legally-isolated machines. Downloading model files at runtime would break that guarantee. All three files are baked into the binary via `include_bytes!` — the binary is self-contained after the build.
