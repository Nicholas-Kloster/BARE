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

Quality validated at scale. A single 12MB binary:

- Loads a BERT encoder (sentence-transformers/all-MiniLM-L6-v2)
- Loads an embedded corpus of pre-encoded vectors (via `include_bytes!`)
- Encodes a query at runtime
- Searches the corpus via cosine similarity
- Returns ranked matches

Rust output vectors match Python sentence-transformers output to within 
f32/f64 rounding error (~1e-7 delta). Stability test across 50 and 250 
real Metasploit module descriptions confirms the model discriminates 
correctly — queries with ground-truth matches in the corpus return them 
as the top result consistently.
