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

Corpus search working end-to-end. A single 12MB binary encodes queries 
with BERT, searches an embedded corpus of vectors, and returns ranked 
matches by cosine similarity. No Python. No VDB. No network.

Test query "ollama exposed no authentication" correctly ranks the 
semantically related ollama_rce corpus entry first with zero shared 
tokens — proving the match is semantic, not keyword-based.

## What's Next

Scale the corpus from 5 handcrafted records to the full Metasploit 
module set (~2,000 modules). Pull from GitHub, encode in the build 
step, ship in the binary.
