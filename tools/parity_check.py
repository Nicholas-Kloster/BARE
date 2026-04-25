#!/usr/bin/env python3
"""
parity_check.py
───────────────
Compares two space-separated f32 vector files element-wise and asserts
the maximum absolute delta is below a threshold. Exits non-zero on
mismatch with a diagnostic table of the worst offenders.

Used by CI to enforce the Rust-vs-Python encoder parity claim.

Usage:
    python tools/parity_check.py python.vec rust.vec [--threshold 1e-5]

Exits 0 on parity, 1 on mismatch, 2 on input error.
"""

import sys


DEFAULT_THRESHOLD = 1e-5
EXPECTED_DIMS = 384


def load_vec(path: str) -> list[float]:
    with open(path, encoding="utf-8") as fh:
        tokens = fh.read().split()
    if len(tokens) != EXPECTED_DIMS:
        print(
            f"parity_check: {path} has {len(tokens)} dims, expected {EXPECTED_DIMS}",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        return [float(t) for t in tokens]
    except ValueError as exc:
        print(f"parity_check: {path} contains non-numeric token: {exc}", file=sys.stderr)
        sys.exit(2)


def main() -> int:
    args = sys.argv[1:]
    threshold = DEFAULT_THRESHOLD
    if "--threshold" in args:
        idx = args.index("--threshold")
        threshold = float(args[idx + 1])
        args = args[:idx] + args[idx + 2 :]

    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    a = load_vec(args[0])
    b = load_vec(args[1])

    deltas = [(i, abs(a[i] - b[i])) for i in range(EXPECTED_DIMS)]
    deltas.sort(key=lambda x: x[1], reverse=True)
    max_delta = deltas[0][1]

    print(f"max delta: {max_delta:.2e}  (threshold: {threshold:.2e})")
    print(f"top-5 element-wise deltas:")
    for idx, d in deltas[:5]:
        print(f"  [{idx:3d}]  python={a[idx]:+.8f}  rust={b[idx]:+.8f}  delta={d:.2e}")

    if max_delta > threshold:
        print(f"\nFAIL: max delta {max_delta:.2e} exceeds threshold {threshold:.2e}", file=sys.stderr)
        return 1

    print(f"\nPASS: encoders agree within {threshold:.2e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
