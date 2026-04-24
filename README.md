# BARE
**B**inary **A**nywhere **R**ust **E**ncoder

A BERT encoder that runs in Rust as a single binary with no dependencies.

## What It Does

Takes a sentence. Produces a vector. In Rust. With no Python runtime.

## Why It Exists

Every other BERT implementation requires:
- Python runtime
- pip packages
- torch + transformers + sentence-transformers
- A virtual environment

This requires one binary.

## Why That Matters

A semantic search tool that requires Python and ChromaDB is a lab tool.
A semantic search tool that's a single binary is a field tool.

That distinction is the entire point.

## Status

Proof of concept complete. Rust vectors match Python sentence-transformers
output to within f32/f64 rounding error (~1e-7 delta).

## What's Next

Semantic search with the corpus baked into the binary at compile time
via `include_bytes!`. No VDB. No server. No network.
