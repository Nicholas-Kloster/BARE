"""
serialize.py
────────────
Encodes a corpus and writes corpus.bin per FORMAT.md.

Now reads from modules_50.json (50 real Metasploit modules).
Encode field: name + " " + description (concatenated for richer signal).

Usage:
    python serialize.py

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
import struct
from sentence_transformers import SentenceTransformer

DIMS = 384
VERSION = 0x01

import sys
INFILE = sys.argv[1] if len(sys.argv) > 1 else "modules_400.json"

with open(INFILE) as f:
    modules = json.load(f)

# (id, encode_text) pairs — name prepended to description for richer signal
CORPUS = [
    (m["id"], m["name"] + " " + m["description"])
    for m in modules
]

print("[*] Loading model...")
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

print(f"[*] Encoding {len(CORPUS)} records...")
names = [name for name, _ in CORPUS]
descs = [desc for _, desc in CORPUS]
vectors = model.encode(descs, normalize_embeddings=True)

out = open("corpus.bin", "wb")

# Header: magic(4s) + version(B) + dims(H) + count(I)
out.write(struct.pack("<4sBHI", b"BARE", VERSION, DIMS, len(CORPUS)))

for name, vec in zip(names, vectors):
    name_bytes = name.encode("utf-8")
    out.write(struct.pack("<H", len(name_bytes)))
    out.write(name_bytes)
    out.write(struct.pack(f"<{DIMS}f", *vec.tolist()))

out.close()

import os
size = os.path.getsize("corpus.bin")
print(f"\n[+] corpus.bin written")
print(f"    Records : {len(CORPUS)}")
print(f"    Size    : {size} bytes ({size / 1024:.2f} KB)")

expected = 11 + sum(2 + len(n.encode()) + DIMS * 4 for n in names)
print(f"    Expected: {expected} bytes")
print(f"    Match   : {'YES' if size == expected else 'NO — MISMATCH'}")
