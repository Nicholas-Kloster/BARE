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

## Current Status

Production corpus embedded. A single 18MB binary:

- Loads a BERT encoder (sentence-transformers/all-MiniLM-L6-v2)
- Loads an embedded corpus of 3,904 pre-encoded vectors covering the 
  full Metasploit exploits/ and auxiliary/ module set (via `include_bytes!`)
- Encodes a query at runtime
- Searches the corpus via cosine similarity
- Returns ranked matches

Rust output vectors match Python sentence-transformers output to within 
f32/f64 rounding error (~1e-7 delta). The binary contains everything 
required — no Python runtime, no network calls, no external index.

### Known Ranking Behavior

Auxiliary scanner modules tend to outrank exploit modules for queries 
written in probe-style language (keywords like "unauthenticated", 
"injection", "traversal") because scanner descriptions are written 
more explicitly than exploit descriptions. This is descriptive style, 
not a semantic error — both types are in the top 5 for most queries.
