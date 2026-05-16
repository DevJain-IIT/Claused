"""
Merge the four uploaded IS 456 chunk files into a single chunks.json.

The four files overlap: section38_batch1 and section39_batch2 are subsets of
section_38_41_all. Duplicate ids resolve to byte-identical content, so
last-wins is safe.

Final output: 74 unique chunks covering IS 456:2000 Sections 26, 38, 39, 40, 41.
"""
import json
from pathlib import Path
from collections import Counter

DATA = Path(__file__).parent / "data"
DATA.mkdir(exist_ok=True)

INPUTS = [
    "/mnt/user-data/uploads/section26_all__1_.json",
    "/mnt/user-data/uploads/section38_batch1__1_.json",
    "/mnt/user-data/uploads/section39_batch2.json",
    "/mnt/user-data/uploads/section_38_41_all.json",
]


def clause_sort_key(c):
    """Sort by section, then sub-clause numerically when possible."""
    parts = c["clause"].split(".")
    out = []
    for p in parts:
        try:
            out.append((0, int(p)))
        except ValueError:
            out.append((1, p))
    return (out, c["id"])


def main():
    merged = {}
    per_file = {}
    for path in INPUTS:
        items = json.load(open(path))
        per_file[Path(path).name] = len(items)
        for c in items:
            merged[c["id"]] = c

    chunks = sorted(merged.values(), key=clause_sort_key)

    print("=== Per-file counts (before dedup) ===")
    for f, n in per_file.items():
        print(f"  {n:>3}  {f}")
    print(f"\n=== After dedup: {len(chunks)} unique chunks ===")
    print(f"  By type:    {dict(Counter(c['content_type'] for c in chunks))}")
    print(f"  By section: {dict(Counter(c['clause'].split('.')[0] for c in chunks))}")
    print(f"  By status:  {dict(Counter(c.get('status', '?') for c in chunks))}")

    out_path = DATA / "chunks.json"
    out_path.write_text(json.dumps(chunks, indent=2, ensure_ascii=False))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
