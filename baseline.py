"""
baseline.py
───────────
Run this first. It generates the ground truth.
The Rust binary has to match these numbers.

Usage:
    pip install sentence-transformers --break-system-packages
    python baseline.py
"""

from sentence_transformers import SentenceTransformer

QUERY = "unauthenticated ollama api endpoint"

print(f"[*] Loading model...")
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

print(f"[*] Encoding: \"{QUERY}\"")
vec = model.encode(QUERY, normalize_embeddings=True)

print(f"\n── Ground Truth ─────────────────────────────────")
print(f"   Vector length : {len(vec)}")
print(f"   First 5 floats: {vec[:5].tolist()}")
print(f"   Last 5 floats : {vec[-5:].tolist()}")
print(f"   L2 norm       : {(vec ** 2).sum() ** 0.5:.6f}  (should be ~1.0)")
print(f"─────────────────────────────────────────────────")
print(f"\n   Paste these into the Rust output comparison.")
