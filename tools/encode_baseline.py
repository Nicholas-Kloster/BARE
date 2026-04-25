#!/usr/bin/env python3
"""
encode_baseline.py
──────────────────
Reads text from stdin, prints the L2-normalized 384-dim sentence-transformers
vector to stdout as space-separated f32. Format mirrors `bare --encode`.

Used by the CI parity check to verify the Rust encoder agrees with Python
sentence-transformers element-wise — turns the README's "~1e-7 delta" claim
into something a CI run can fail on.

Usage:
    echo "your text" | python tools/encode_baseline.py
    cat findings_query.txt | python tools/encode_baseline.py > python.vec
"""

import sys

from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def main() -> int:
    text = sys.stdin.read().strip()
    if not text:
        print("encode_baseline.py: empty stdin", file=sys.stderr)
        return 1

    model = SentenceTransformer(MODEL_NAME)
    vec = model.encode(text, normalize_embeddings=True)

    print(" ".join(f"{x:.10f}" for x in vec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
