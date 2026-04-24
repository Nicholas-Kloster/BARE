"""
serialize.py
────────────
Encodes a corpus and writes corpus.bin per FORMAT.md.

Default input: modules_full.json
Override:      python serialize.py <path-to-json>

Encode field: name + " " + description (concatenated for richer signal).

# ── Original hardcoded 5-record corpus (kept for reference) ──────────────────
# CORPUS = [
#     ("ollama_rce",
#      "Unauthenticated Ollama API exploit via /api/generate endpoint for model inference theft and malicious model injection"),
#     ("jupyter_rce",
#      "Jupyter notebook unauthenticated kernel API allowing arbitrary Python code execution via /api/kernels"),
#     ("flowise_creds",
#      "Flowise credentials dump from /api/v1/credentials exposing OpenAI and Anthropic API keys stored in agent flows"),
#     ("chromadb_dump",
#      "ChromaDB collection enumeration revealing PII vectors and customer records from unauthenticated instance"),
#     ("mlflow_traversal",
#      "MLflow artifact path traversal for reading arbitrary files from model server filesystem"),
# ]
# ─────────────────────────────────────────────────────────────────────────────
"""

import json
import os
import struct
import sys

from sentence_transformers import SentenceTransformer

DIMS    = 384
VERSION = 0x01
INFILE  = sys.argv[1] if len(sys.argv) > 1 else "modules_full.json"

print(f"[*] Reading {INFILE}...")
with open(INFILE) as f:
    modules = json.load(f)

names = [m["id"] for m in modules]
descs = [m["name"] + " " + m["description"] for m in modules]

print(f"[*] Loading model...")
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

print(f"[*] Encoding {len(names)} records (this will take a while on CPU)...")
vectors = model.encode(
    descs,
    normalize_embeddings=True,
    batch_size=64,
    show_progress_bar=True,
)

print(f"[*] Writing corpus.bin...")
out = open("corpus.bin", "wb")
out.write(struct.pack("<4sBHI", b"BARE", VERSION, DIMS, len(names)))

for name, vec in zip(names, vectors):
    name_bytes = name.encode("utf-8")
    out.write(struct.pack("<H", len(name_bytes)))
    out.write(name_bytes)
    out.write(struct.pack(f"<{DIMS}f", *vec.tolist()))

out.close()

size     = os.path.getsize("corpus.bin")
expected = 11 + sum(2 + len(n.encode()) + DIMS * 4 for n in names)

print(f"\n[+] corpus.bin written")
print(f"    Records  : {len(names)}")
print(f"    Size     : {size:,} bytes ({size / 1024 / 1024:.2f} MB)")
print(f"    Expected : {expected:,} bytes")
print(f"    Match    : {'YES' if size == expected else 'NO — MISMATCH'}")
