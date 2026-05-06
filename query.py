"""
CLI for the IS 6403 RAG.

Usage:
    python3 query.py "your question here"

Prints:
  - Top-4 retrieval results (chunk id, type, clause, page, score)
  - Full content of the top-1 chunk (the form an LLM would consume)
  - Numeric lookup output if the question references Table 1 / Fig 1 / Fig 3
    with extractable parameters (phi value, c1/c2 ratio, etc.)
"""

import re
import sys
from pathlib import Path

# Make local imports work
sys.path.insert(0, str(Path(__file__).parent))
from importlib import import_module
rag = import_module("02_rag")


def maybe_numeric_lookups(query: str):
    """Heuristically extract numeric parameters and run the matching lookups."""
    out = []
    ql = query.lower()

    # Table 1 lookup: "phi = X" / "phi=X degrees" with mention of Nc/Nq/Ngamma/factor
    phi_match = re.search(r"(?:phi|φ)\s*[=]?\s*(\d+(?:\.\d+)?)", ql)
    asks_table1 = any(t in ql for t in ["nc", "nq", "ngamma", "n gamma", "n_gamma",
                                         "bearing capacity factor", "bearing factor"])
    if phi_match and asks_table1:
        out.append(("Table 1 lookup", rag.lookup_table1(float(phi_match.group(1)))))

    # Fig 1 lookup, forward: phi -> N
    asks_N_from_phi = phi_match and any(t in ql for t in ["spt", "n value", "n=",
                                                            "penetration resistance",
                                                            "blows"])
    if asks_N_from_phi:
        out.append(("Fig 1 forward (phi -> N)",
                    rag.lookup_fig1_N_from_phi(float(phi_match.group(1)))))

    # Fig 1 lookup, inverse: N -> phi
    n_match = re.search(r"\bn\s*[=]?\s*(\d+(?:\.\d+)?)", ql)
    asks_phi_from_N = n_match and any(t in ql for t in ["phi", "φ", "friction angle",
                                                          "angle of internal friction"])
    if asks_phi_from_N and not phi_match:
        out.append(("Fig 1 inverse (N -> phi)",
                    rag.lookup_fig1_phi_from_N(float(n_match.group(1)))))

    # Fig 3 lookup: needs both c1/c2 and d/b
    c_match = re.search(r"c1\s*/\s*c2\s*[=]?\s*(\d+(?:\.\d+)?)", ql)
    db_match = re.search(r"d\s*/\s*b\s*[=]?\s*(\d+(?:\.\d+)?)", ql)
    if c_match and db_match:
        out.append(("Fig 3 lookup (Nc layered cohesive)",
                    rag.lookup_fig3_Nc(float(c_match.group(1)),
                                        float(db_match.group(1)))))

    return out


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 query.py "your question here"', file=sys.stderr)
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    print(f"Q: {query}\n")

    results = rag.search(query, top_k=4)
    print("=== retrieval (top-4) ===")
    for rank, (score, c) in enumerate(results, 1):
        print(f"  #{rank} score={score:.3f}  [{c['content_type']:6s}] "
              f"cl.{c['clause']}, p.{c['page']:>3}  → {c['id']}")

    print("\n=== top chunk content ===")
    rag.render_chunk(results[0][1])

    lookups = maybe_numeric_lookups(query)
    if lookups:
        print("\n=== numeric lookups (auto-detected from query) ===")
        for label, value in lookups:
            print(f"  {label}: {value}")


if __name__ == "__main__":
    main()
