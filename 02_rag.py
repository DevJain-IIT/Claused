"""
RAG over IS 6403:1981 (pages 13-21 / Sections 5-6).

Indexes 22 chunks (14 clauses, 4 tables, 3 graphs, 1 figure).
Provides hybrid retrieval and content-type-aware answer composition,
including numeric lookups against Table 1 and digitised Figures 1 and 3.
"""

import json
import re
from pathlib import Path
from typing import Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

DATA = Path(__file__).parent / "data"
chunks = json.loads((DATA / "chunks.json").read_text())


# ---------------------------------------------------------------------------
# 1. Embeddable text per chunk type (same shape as the earlier prototype)
# ---------------------------------------------------------------------------
def embed_text(c: dict) -> str:
    head = f"[{c['code']} cl. {c['clause']}]"
    ct = c["content_type"]

    if ct == "clause":
        parts = [head, c["title"], c["text"]]
        if c.get("formula_nl_summary"):
            parts.append(f"Formula: {c['formula_nl_summary']}")
        return " ".join(parts)

    if ct == "table":
        rows_preview = " | ".join(", ".join(r) for r in c["rows"][:3])
        return (f"{head} Table {c['table_number']}. {c['caption']} "
                f"Columns: {', '.join(c['headers'])}. "
                f"Sample rows: {rows_preview}. {c['nl_summary']}")

    if ct == "graph":
        axes = c.get("axes", {})
        return (f"{head} Figure {c['figure_number']} ({c['figure_subtype']}). "
                f"Axes: x = {axes.get('x','?')}, y = {axes.get('y','?')}. "
                f"{c['nl_caption']}")

    if ct == "figure":
        return (f"{head} Figure {c['figure_number']} ({c['figure_subtype']}). "
                f"{c['nl_caption']}")

    raise ValueError(ct)


texts = [embed_text(c) for c in chunks]
vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
emb = normalize(vectorizer.fit_transform(texts).toarray())


# ---------------------------------------------------------------------------
# 2. Hybrid retrieval
# ---------------------------------------------------------------------------
CLAUSE_RE = re.compile(r"\b(?:cl\.?|clause)\s*([\d.]+)", re.I)
FIG_RE = re.compile(r"\bfig(?:ure)?\.?\s*(\d+)", re.I)
TABLE_RE = re.compile(r"\btable\s*(\d+)", re.I)


def search(query: str, top_k: int = 4, content_type: Optional[str] = None):
    q = normalize(vectorizer.transform([query]).toarray())[0]
    cosines = emb @ q

    wanted_clause = (CLAUSE_RE.search(query) or [None, None])[1]
    wanted_fig    = (FIG_RE.search(query)    or [None, None])[1]
    wanted_table  = (TABLE_RE.search(query)  or [None, None])[1]

    intent = {}
    ql = query.lower()
    if any(w in ql for w in ["chart", "curve", "graph", "plot", "diagram"]):
        intent["graph"] = 0.10
    if "table" in ql:
        intent["table"] = 0.10
    if any(w in ql for w in ["figure", "fig.", "fig ", "drawing", "schematic"]):
        intent["figure"] = 0.10

    rows = []
    for i, c in enumerate(chunks):
        if content_type and c["content_type"] != content_type:
            continue
        score = float(cosines[i])
        if wanted_clause and c["clause"].startswith(wanted_clause):
            score += 0.40
        if wanted_fig and c.get("figure_number") == wanted_fig:
            score += 0.50
        if wanted_table and c.get("table_number") == wanted_table:
            score += 0.50
        score += intent.get(c["content_type"], 0.0)
        rows.append((score, c))

    rows.sort(key=lambda r: r[0], reverse=True)
    return rows[:top_k]


# ---------------------------------------------------------------------------
# 3. Numeric lookup helpers
# ---------------------------------------------------------------------------
def _interp1(points, x):
    """Linear interpolate y at x given a list of {x, y} points (sorted by x)."""
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    if x < xs[0] or x > xs[-1]:
        return None  # outside digitised range
    return float(np.interp(x, xs, ys))


def lookup_table1(phi_deg: float):
    """Interpolate Nc, Nq, N_gamma at a given phi (degrees) from Table 1."""
    t = next(c for c in chunks if c["id"] == "table_1_bearing_factors")
    phis = [float(r[0]) for r in t["rows"]]
    out = {"phi_deg": phi_deg}
    if phi_deg < phis[0] or phi_deg > phis[-1]:
        out["error"] = f"phi={phi_deg} outside Table 1 range [{phis[0]}, {phis[-1]}]"
        return out
    for col_idx, name in enumerate(["Nc", "Nq", "N_gamma"], start=1):
        col = [float(r[col_idx]) for r in t["rows"]]
        out[name] = float(np.interp(phi_deg, phis, col))
    return out


def lookup_fig1_N_from_phi(phi_deg: float):
    """Read SPT N from Fig 1 for given phi."""
    g = next(c for c in chunks if c["id"] == "fig_1_phi_vs_N")
    pts = g["curves"][0]["points"]
    n = _interp1(pts, phi_deg)
    return {"phi_deg": phi_deg, "N": n}


def lookup_fig1_phi_from_N(N: float):
    """Inverse: read phi from Fig 1 for given N."""
    g = next(c for c in chunks if c["id"] == "fig_1_phi_vs_N")
    pts = g["curves"][0]["points"]
    # Inverse interp: invert the (phi -> N) mapping
    phis = [p["x"] for p in pts]
    Ns   = [p["y"] for p in pts]
    if N < Ns[0] or N > Ns[-1]:
        return {"N": N, "phi_deg": None,
                "error": f"N={N} outside Fig 1 range [{Ns[0]}, {Ns[-1]}]"}
    return {"N": N, "phi_deg": float(np.interp(N, Ns, phis))}


def lookup_fig3_Nc(c1_over_c2: float, d_over_b: float):
    """
    Read Nc from Fig 3 for given c1/c2 and d/b.

    Fig 3 has two families of d/b-labelled curves:
      - 'lower' curves valid for c1/c2 <= 1 (top weaker) — labels 0, 0.5, 1.0, 1.5, 2.0
      - 'upper' curves valid for c1/c2 >= 1 (top stronger) — labels 0, 0.2, 0.4, 0.6, 0.8, 1.0
    The d/b = 0 curve spans both halves linearly through (1, 5.5).

    Strategy: pick the family by which side of c1/c2 = 1 we're on, find the
    bracketing two d/b values, interpolate Nc on each, then interpolate
    between the two d/b values.
    """
    g = next(c for c in chunks if c["id"] == "fig_3_layered_Nc")

    # Pull out the lower vs upper families
    def family(side):  # side = 'lower' or 'upper'
        return sorted(
            (curve for curve in g["curves"]
             if (side in curve["label"]) or curve["label"] == "d/b = 0"),
            key=lambda cu: float(re.search(r"d/b = ([\d.]+)", cu["label"]).group(1))
        )

    if c1_over_c2 <= 1.0:
        fam = family("lower")
    else:
        fam = family("upper")

    db_values = [float(re.search(r"d/b = ([\d.]+)", cu["label"]).group(1))
                 for cu in fam]

    if d_over_b < db_values[0] or d_over_b > db_values[-1]:
        return {"c1_over_c2": c1_over_c2, "d_over_b": d_over_b, "Nc": None,
                "error": (f"d/b = {d_over_b} outside available curves "
                          f"{db_values} for this side of the chart")}

    # Bracket d/b
    for i in range(len(db_values) - 1):
        if db_values[i] <= d_over_b <= db_values[i + 1]:
            db_lo, db_hi = db_values[i], db_values[i + 1]
            curve_lo, curve_hi = fam[i], fam[i + 1]
            break
    else:
        db_lo = db_hi = db_values[0]
        curve_lo = curve_hi = fam[0]

    # Read Nc on each bracketing curve at our c1/c2
    Nc_lo = _interp1(curve_lo["points"], c1_over_c2)
    Nc_hi = _interp1(curve_hi["points"], c1_over_c2)
    if Nc_lo is None or Nc_hi is None:
        return {"c1_over_c2": c1_over_c2, "d_over_b": d_over_b, "Nc": None,
                "error": f"c1/c2 = {c1_over_c2} outside one of the bracketing curves' digitised range"}

    if db_hi == db_lo:
        Nc = Nc_lo
    else:
        w = (d_over_b - db_lo) / (db_hi - db_lo)
        Nc = (1 - w) * Nc_lo + w * Nc_hi

    return {"c1_over_c2": c1_over_c2, "d_over_b": d_over_b,
            "Nc": float(Nc),
            "interpolated_between": [curve_lo["label"], curve_hi["label"]]}


# ---------------------------------------------------------------------------
# 4. Public answer function
# ---------------------------------------------------------------------------
def answer(query: str, top_k: int = 3, verbose: bool = True):
    results = search(query, top_k=top_k)
    if verbose:
        print(f"\nQ: {query}")
        for rank, (score, c) in enumerate(results, 1):
            ct = c["content_type"]
            tag = f"[{ct:6s}] cl.{c['clause']}, p.{c['page']}"
            print(f"  #{rank} score={score:.3f} {tag}  → {c['id']}")
    return results


def render_chunk(c: dict, max_text_chars: int = 600):
    """Pretty-print a chunk (the form an LLM would see)."""
    cite = f"[IS 6403:1981 cl. {c['clause']}, p. {c['page']}]"
    head = f"\n=== {cite}  type={c['content_type']} ==="
    print(head)

    if c["content_type"] == "clause":
        print(f"Title: {c['title']}")
        print(c["text"][:max_text_chars])
        if c.get("formula_latex"):
            print(f"\nFormula (LaTeX): {c['formula_latex']}")

    elif c["content_type"] == "table":
        print(f"Caption: {c['caption']}")
        print(f"Headers: {' | '.join(c['headers'])}")
        for r in c["rows"]:
            print("         " + " | ".join(r))
        if c.get("note"):
            print(f"Note: {c['note']}")

    elif c["content_type"] in ("graph", "figure"):
        print(f"Caption: {c['nl_caption'][:max_text_chars]}")
        print(f"Image:   {c['image_path']}")
        if c.get("amendment_note"):
            print(f"Amendment: {c['amendment_note']}")
