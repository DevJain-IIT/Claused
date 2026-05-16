"""
RAG over IS 456:2000.

Indexes 74 chunks (65 clauses, 5 tables, 2 graphs, 2 figures) covering
Sections 26 (reinforcement detailing), 38 (flexure), 39 (compression),
40 (shear), 41 (torsion).

Same architecture as the earlier IS 6403 retriever:
  - TF-IDF cosine over chunk text
  - Clause-number / figure-number / table-number boosts from regex
  - Content-type intent boost from keywords (chart, table, etc.)
  - Parameter-vocabulary boost — extra weight when query mentions a chunk's
    parameters / tags / aliases

Plus IS 456-specific deterministic lookups for:
  - Table 19 (design shear strength τ_c by pt and concrete grade)
  - Table 20 (max shear stress τ_c,max by grade)
  - Table 38.1 (xu,max/d by fy)
  - Table 40.2.1 (slab depth factor k by overall depth)
  - Table 26.2.1.1 (bond stress τ_bd by grade)
  - Fig 21 (concrete stress-strain, closed-form parabolic-rectangular)
  - Fig 23 (steel stress-strain — 23A cold-worked, 23B mild steel)

Switching to real embeddings later: replace the TfidfVectorizer block with
calls to OpenAI text-embedding-3-large or BGE-large-en, keeping the same
search() signature.
"""

import json
import re
from pathlib import Path
from typing import Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

DATA = Path(__file__).parent / "data"
chunks = json.loads((DATA / "chunks.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Embeddable text per chunk
# ---------------------------------------------------------------------------
def embed_text(c: dict) -> str:
    head = f"[{c['code']} cl. {c['clause']}]"
    tags = " ".join(c.get("tags", []))
    ct = c["content_type"]

    if ct == "clause":
        parts = [head, c.get("title", ""), c.get("text", "")]
        if c.get("formula_nl_summary"):
            parts.append(f"Formula: {c['formula_nl_summary']}")
        if tags:
            parts.append(f"Tags: {tags}")
        return " ".join(parts)

    if ct == "table":
        rows_preview = " | ".join(", ".join(str(x) for x in r) for r in c["rows"][:3])
        return (f"{head} Table {c.get('table_number', '?')}. {c.get('caption', '')} "
                f"Columns: {', '.join(c.get('headers', []))}. "
                f"Sample rows: {rows_preview}. "
                f"{c.get('nl_summary', '')} Tags: {tags}")

    if ct == "graph":
        ax = c.get("axes", {})
        x_label = ax.get("x", {}).get("label", "?") if isinstance(ax.get("x"), dict) else "?"
        y_label = ax.get("y", {}).get("label", "?") if isinstance(ax.get("y"), dict) else "?"
        return (f"{head} Figure {c.get('figure_number', '?')} "
                f"({c.get('figure_subtype', '')}). "
                f"Title: {c.get('title', '')}. Axes: x = {x_label}, y = {y_label}. "
                f"{c.get('nl_caption', '') or c.get('caption', '')} Tags: {tags}")

    if ct == "figure":
        return (f"{head} Figure {c.get('figure_number', '?')} "
                f"({c.get('figure_subtype', '')}). "
                f"Title: {c.get('title', '')}. "
                f"{c.get('nl_caption', '')} Tags: {tags}")

    raise ValueError(f"unknown content_type {ct}")


texts = [embed_text(c) for c in chunks]
vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
emb = normalize(vectorizer.fit_transform(texts).toarray())


# ---------------------------------------------------------------------------
# 2. Hybrid retrieval
# ---------------------------------------------------------------------------
CLAUSE_RE = re.compile(r"\b(?:cl\.?|clause)\s*([\d.]+)", re.I)
FIG_RE = re.compile(r"\bfig(?:ure)?\.?\s*(\d+)", re.I)
TABLE_RE = re.compile(r"\btable\s*([\d.]+)", re.I)


# Parameter vocab — boosts chunks when query mentions their key parameters.
# IS 456 has heavy symbol use (fck, fy, tau_c, xu, As, etc.) so the vocab
# is symbol-heavy, with aliases for the common ways engineers refer to them.
PARAM_VOCAB = {
    # Section 26 — reinforcement detailing
    "table_26_2_1_1_bond_stress": {
        "tau_bd":  [r"\btau[_ ]?bd\b", r"τ_?bd\b", r"bond stress"],
        "develop": [r"development length", r"\bl_?d\b"],
        "grade":   [r"\bm\s*(?:15|20|25|30|35|40|45)\b", r"concrete grade"],
        "deformed":[r"deformed bar", r"\bis\s*1786\b"],
    },
    # Section 38 — flexure
    "table_38_1_xu_max_d_ratio": {
        "xu_max":  [r"x_?u[,\s]*max", r"xu max", r"maximum neutral axis"],
        "fy":      [r"\bf_?y\b", r"yield strength", r"\bfe\s*\d+"],
        "neutral": [r"neutral axis"],
    },
    "fig_21_concrete_stress_strain": {
        "fck":     [r"\bf_?ck\b", r"characteristic.*compressive"],
        "ss":      [r"stress[-\s]?strain", r"σ[-\s]?ε", r"stress.strain"],
        "concrete":[r"\bconcrete\b"],
        "parabolic":[r"parabolic", r"rectangular block", r"0\.0035", r"0\.002"],
    },
    "fig_22_stress_block": {
        "stress_block":[r"stress block", r"0\.36\s*f_?ck", r"0\.42\s*x_?u"],
        "moment":  [r"moment of resistance", r"flexure"],
    },
    "fig_23_steel_stress_strain": {
        "ss":      [r"stress[-\s]?strain", r"σ[-\s]?ε"],
        "steel":   [r"\bsteel\b", r"reinforcement", r"\bfe\s*\d+", r"cold[-\s]?worked", r"mild steel"],
        "fy":      [r"\bf_?y\b", r"yield"],
    },
    # Section 40 — shear
    "table_19_design_shear_strength_concrete": {
        "tau_c":   [r"\btau[_ ]?c\b(?!,?\s*max)", r"τ_?c\b(?!,?\s*max)",
                    r"design shear strength"],
        "pt":      [r"\bpt\b", r"percentage.*tension", r"100\s*a_?s\s*/",
                    r"tension reinforcement.*percentage"],
        "grade":   [r"\bm\s*(?:15|20|25|30|35|40|45)\b", r"concrete grade"],
    },
    "table_20_max_shear_stress": {
        "tau_max": [r"tau[_ ]?c[,\s]*max", r"τ_?c[,\s]*max", r"maximum shear",
                    r"max.*shear stress"],
        "grade":   [r"\bm\s*(?:15|20|25|30|35|40|45)\b"],
    },
    "table_40_2_1_slab_depth_factor": {
        "k":       [r"\bk\s*factor", r"depth factor", r"\bk\b"],
        "slab":    [r"\bslab\b", r"solid slab"],
        "depth":   [r"overall depth"],
    },
    # Key clauses that compete on overlapping vocab
    "cl_26_2_1_development_length": {
        "Ld":      [r"development length", r"\bl_?d\b", r"anchorage"],
        "phi":     [r"\bphi\b\s*(?:bar|diameter)?", r"bar diameter"],
        "formula": [r"\bphi\s*sigma\s*/\s*4\s*tau", r"l_?d\s*="],
    },
    "cl_26_5_1_1_min_tension_steel": {
        "min_tension":[r"minimum tension", r"min.*reinforcement", r"0\.85\s*/\s*f_?y",
                       r"a_?s,?\s*min"],
        "beam":    [r"\bbeam\b"],
    },
    "cl_38_1_flexure_assumptions": {
        "flexure": [r"flexure", r"flexural", r"\bbending\b"],
        "limit":   [r"limit state", r"collapse"],
        "assumption":[r"assumption"],
        "strain":  [r"0\.0035", r"max.*strain"],
    },
    "cl_39_1_compression_assumptions": {
        "compression":[r"compression"],
        "axial":   [r"axial", r"pure axial"],
        "0_002":   [r"0\.002\b"],
    },
    "cl_39_5_uniaxial_bending": {
        "uniaxial":[r"uniaxial bending"],
        "column":  [r"column"],
    },
    "cl_39_6_biaxial_bending": {
        "biaxial": [r"biaxial bending", r"biaxial"],
        "pn":      [r"\bp_?n\b", r"\balpha_?n\b"],
    },
    "cl_39_7_slender_additional_moment": {
        "slender": [r"slender", r"slenderness", r"additional moment"],
    },
    "cl_40_1_general_shear": {
        "tauv":    [r"\btau[_ ]?v\b", r"τ_?v\b", r"nominal shear",
                    r"v_?u\s*/\s*\(?\s*b\s*\*?\s*d"],
    },
    "cl_40_4_shear_reinforcement_design": {
        "stirrup": [r"stirrup", r"\bv_?us\b", r"shear reinforcement",
                    r"vertical stirrup", r"inclined stirrup", r"bent[-\s]?up"],
        "spacing": [r"spacing", r"\bs_?v\b"],
    },
    "cl_41_3_design_for_torsion": {
        "torsion": [r"torsion", r"\bt_?u\b", r"twisting"],
        "equivalent":[r"equivalent moment", r"m_?e", r"m_?t"],
    },
}

_PARAM_PATTERNS = {
    cid: {p: [re.compile(rx, re.I) for rx in pats]
          for p, pats in params.items()}
    for cid, params in PARAM_VOCAB.items()
}


def _parameter_match_count(query: str, chunk_id: str) -> int:
    patterns = _PARAM_PATTERNS.get(chunk_id, {})
    return sum(1 for plist in patterns.values()
               if any(p.search(query) for p in plist))


def _tag_match_count(query: str, chunk: dict) -> int:
    """How many of a chunk's tags appear in the query (as substrings)."""
    ql = query.lower()
    return sum(1 for tag in chunk.get("tags", [])
               if tag.replace("-", " ").lower() in ql
               or tag.lower() in ql)


def search(query: str, top_k: int = 4,
           content_type: Optional[str] = None,
           include_draft: bool = True):
    """
    Returns top-k (score, chunk) pairs.

    include_draft=False filters out chunks with status='draft' (the normal
    production behaviour). For now defaults to True since EVERY chunk is draft.
    """
    q = normalize(vectorizer.transform([query]).toarray())[0]
    cosines = emb @ q

    wanted_clause = (CLAUSE_RE.search(query) or [None, None])[1]
    wanted_fig    = (FIG_RE.search(query)    or [None, None])[1]
    wanted_table  = (TABLE_RE.search(query)  or [None, None])[1]

    intent = {}
    ql = query.lower()
    if any(w in ql for w in ["chart", "curve", "graph", "plot"]):
        intent["graph"] = 0.10
    if "table" in ql:
        intent["table"] = 0.10
    if any(w in ql for w in ["figure", "fig.", "fig ", "diagram", "schematic"]):
        intent["figure"] = 0.10

    rows = []
    for i, c in enumerate(chunks):
        if content_type and c["content_type"] != content_type:
            continue
        if not include_draft and c.get("status") == "draft":
            continue

        score = float(cosines[i])
        if wanted_clause and c["clause"].startswith(wanted_clause):
            score += 0.40
        if wanted_fig and c.get("figure_number") == wanted_fig:
            score += 0.50
        if wanted_table and str(c.get("table_number", "")).startswith(wanted_table):
            score += 0.50
        score += intent.get(c["content_type"], 0.0)

        # Parameter vocab boost (hand-curated regex)
        score += 0.15 * _parameter_match_count(query, c["id"])

        # Tag-based boost (every chunk has tags now in the new schema)
        score += 0.08 * _tag_match_count(query, c)

        rows.append((score, c))

    rows.sort(key=lambda r: r[0], reverse=True)
    return rows[:top_k]


# ---------------------------------------------------------------------------
# 3. Numeric lookup helpers
# ---------------------------------------------------------------------------
def _interp1(xs, ys, x):
    if x < xs[0] or x > xs[-1]:
        return None
    return float(np.interp(x, xs, ys))


def _strip_comparator(s: str) -> str:
    s = s.replace("≤", "").replace("≥", "").replace("<", "").replace(">", "")
    for phrase in ["and above", "or more", "or less", "and below"]:
        s = s.replace(phrase, "")
    return s.strip()


# --- Table 19: design shear strength τ_c by pt and concrete grade ---
def lookup_table_19(pt: float, grade: str):
    t = next(c for c in chunks if c["id"] == "table_19_design_shear_strength_concrete")
    grade = grade.upper().strip().replace(" ", "")
    grade_map = {"M15": 1, "M20": 2, "M25": 3, "M30": 4, "M35": 5,
                 "M40": 6, "M40+": 6, "M45": 6, "M50": 6,
                 "M40ANDABOVE": 6}
    if grade not in grade_map:
        return {"error": f"Unknown grade {grade!r}",
                "supported": list(grade_map.keys())}
    col = grade_map[grade]
    pts = [float(_strip_comparator(r[0])) for r in t["rows"]]
    vals = [float(r[col]) for r in t["rows"]]
    if pt <= pts[0]:
        return {"pt": pt, "grade": grade, "tau_c": vals[0],
                "note": f"pt ≤ {pts[0]} — using row floor"}
    if pt >= pts[-1]:
        return {"pt": pt, "grade": grade, "tau_c": vals[-1],
                "note": f"pt ≥ {pts[-1]} — using row ceiling"}
    return {"pt": pt, "grade": grade,
            "tau_c": float(np.interp(pt, pts, vals)),
            "source": "IS 456:2000 Table 19, cl. 40.2"}


# --- Table 20: max shear stress τ_c,max by grade ---
def lookup_table_20(grade: str):
    t = next(c for c in chunks if c["id"] == "table_20_max_shear_stress")
    grade = grade.upper().strip().replace(" ", "")
    # Headers: ['Quantity', 'M15', 'M20', 'M25', 'M30', 'M35', 'M40 and above']
    aliases = {"M40": "M40 and above", "M40+": "M40 and above",
               "M45": "M40 and above", "M50": "M40 and above",
               "M40ANDABOVE": "M40 and above"}
    grade = aliases.get(grade, grade)
    headers = t["headers"]
    if grade not in headers:
        return {"error": f"Grade {grade!r} not in {headers[1:]}"}
    col = headers.index(grade)
    return {"grade": grade,
            "tau_c_max": float(t["rows"][0][col]),
            "source": "IS 456:2000 Table 20, cl. 40.2.3"}


# --- Table 38.1: xu,max/d by fy ---
def lookup_xu_max_d(fy: float):
    t = next(c for c in chunks if c["id"] == "table_38_1_xu_max_d_ratio")
    fys = [float(r[0]) for r in t["rows"]]
    vals = [float(r[1]) for r in t["rows"]]
    if fy in fys:
        return {"fy": fy, "xu_max_over_d": vals[fys.index(fy)],
                "source": "IS 456:2000 Table 38.1, cl. 38.1"}
    if fy < fys[0] or fy > fys[-1]:
        return {"fy": fy, "error": f"fy outside tabulated range {fys}"}
    return {"fy": fy,
            "xu_max_over_d": float(np.interp(fy, fys, vals)),
            "note": "Linearly interpolated — standard only tabulates Fe250/415/500",
            "source": "IS 456:2000 Table 38.1, cl. 38.1"}


# --- Table 40.2.1: slab depth factor k ---
def lookup_slab_depth_factor(D_mm: float):
    t = next(c for c in chunks if c["id"] == "table_40_2_1_slab_depth_factor")
    # Rows like ['300 or more', '1.00'] ... ['150 or less', '1.30']
    depths, ks = [], []
    for row in t["rows"]:
        depths.append(float(_strip_comparator(row[0])))
        ks.append(float(row[1]))
    # Sort ascending by depth
    pairs = sorted(zip(depths, ks))
    depths, ks = [p[0] for p in pairs], [p[1] for p in pairs]
    if D_mm <= depths[0]:
        return {"D_mm": D_mm, "k": ks[0],
                "note": f"D ≤ {depths[0]} mm — using floor value k = {ks[0]}",
                "source": "IS 456:2000 Table cl. 40.2.1.1"}
    if D_mm >= depths[-1]:
        return {"D_mm": D_mm, "k": ks[-1],
                "note": f"D ≥ {depths[-1]} mm — using ceiling value k = {ks[-1]}",
                "source": "IS 456:2000 Table cl. 40.2.1.1"}
    return {"D_mm": D_mm, "k": float(np.interp(D_mm, depths, ks)),
            "source": "IS 456:2000 Table cl. 40.2.1.1 (interpolated)"}


# --- Table 26.2.1.1: bond stress τ_bd by grade ---
def lookup_bond_stress(grade: str, bar_type: str = "plain",
                       direction: str = "tension"):
    """
    Bond stress τ_bd for plain bars in tension; multipliers per the note:
      - deformed bars (IS 1786): × 1.60
      - bars in compression:     × 1.25
    """
    t = next(c for c in chunks if c["id"] == "table_26_2_1_1_bond_stress")
    grade = grade.upper().strip().replace(" ", "")
    aliases = {"M40": "M40+", "M45": "M40+", "M50": "M40+"}
    grade = aliases.get(grade, grade)
    headers = t["headers"]
    if grade not in headers:
        return {"error": f"Grade {grade!r} not in {headers[1:]}"}
    col = headers.index(grade)
    base = float(t["rows"][0][col])

    multiplier = 1.0
    if bar_type.lower() in ("deformed", "hysd"):
        multiplier *= 1.60
    if direction.lower() == "compression":
        multiplier *= 1.25

    return {"grade": grade,
            "bar_type": bar_type, "direction": direction,
            "tau_bd_N_per_mm2": round(base * multiplier, 3),
            "base_value_plain_tension": base,
            "multiplier_applied": round(multiplier, 3),
            "source": "IS 456:2000 cl. 26.2.1.1"}


# --- Fig 21: concrete stress-strain (closed form) ---
def lookup_fig21_concrete_stress(strain: float, fck: float,
                                 apply_gamma_m: bool = True):
    """Design (γm=1.5) or characteristic (γm=1.0) concrete stress at given strain."""
    gamma_m = 1.5 if apply_gamma_m else 1.0
    peak = 0.67 * fck / gamma_m
    if strain < 0:
        return {"error": "strain must be ≥ 0"}
    if strain > 0.0035:
        return {"strain": strain, "stress": 0.0,
                "region": "beyond ultimate (concrete crushed)",
                "f_ck": fck, "peak_stress": peak}
    if strain >= 0.002:
        return {"strain": strain, "stress": peak,
                "region": "plateau",
                "f_ck": fck, "gamma_m": gamma_m,
                "source": "IS 456:2000 Fig 21, cl. 38.1"}
    # Parabolic region
    e_norm = strain / 0.002
    stress = peak * (2 * e_norm - e_norm * e_norm)
    return {"strain": strain, "stress": float(stress),
            "region": "parabolic",
            "f_ck": fck, "gamma_m": gamma_m, "peak_stress": peak,
            "source": "IS 456:2000 Fig 21, cl. 38.1"}


# --- Fig 23A: cold-worked deformed bar stress-strain ---
def lookup_fig23a_steel_stress(strain: float, fy: float):
    """
    Characteristic stress-strain for cold-worked deformed bars (Fe415, Fe500 etc.).
    Linear-elastic up to 0.80·fy, then progressively yielding through calibrated
    points at 0.85, 0.90, 0.95, 0.975, 1.00 of fy. Beyond, plateau at fy.
    """
    Es = 200000  # N/mm²
    g = next(c for c in chunks if c["id"] == "fig_23_steel_stress_strain")
    curve_23a = next(cu for cu in g["curves"]
                     if "Cold-worked" in cu.get("name", ""))
    pts = curve_23a["key_points"]

    # Compute total strain at each key point: σ/Es + inelastic_offset
    table = []
    for kp in pts:
        sigma = kp["stress_ratio_to_fy"] * fy
        total_eps = sigma / Es + kp["inelastic_strain_offset"]
        table.append((total_eps, sigma))
    table.sort()
    eps_vals = [t[0] for t in table]
    sig_vals = [t[1] for t in table]

    eps_elastic_limit = eps_vals[0]   # at 0.80·fy
    eps_yield_top = eps_vals[-1]      # at 1.00·fy

    if strain < 0:
        return {"error": "strain must be ≥ 0"}
    if strain < eps_elastic_limit:
        return {"strain": strain, "stress": Es * strain,
                "region": "linear-elastic",
                "fy": fy, "Es": Es,
                "source": "IS 456:2000 Fig 23A, cl. 38.1"}
    if strain > eps_yield_top:
        return {"strain": strain, "stress": fy,
                "region": "plateau at fy",
                "fy": fy, "Es": Es,
                "source": "IS 456:2000 Fig 23A, cl. 38.1"}
    return {"strain": strain,
            "stress": float(np.interp(strain, eps_vals, sig_vals)),
            "region": "piecewise-linear (yielding zone)",
            "fy": fy, "Es": Es,
            "source": "IS 456:2000 Fig 23A, cl. 38.1"}


# ---------------------------------------------------------------------------
# 4. Renderer (used for debug printing — not the LLM source format)
# ---------------------------------------------------------------------------
def render_chunk(c: dict, max_chars: int = 600):
    cite = f"[IS 456:2000 cl. {c['clause']}, p. {c.get('page', '?')}]"
    print(f"\n=== {cite}  type={c['content_type']}  status={c.get('status', '?')} ===")
    if c.get("tags"):
        print(f"Tags: {', '.join(c['tags'])}")
    ct = c["content_type"]
    if ct == "clause":
        print(f"Title: {c.get('title', '')}")
        print(c.get("text", "")[:max_chars])
        if c.get("formula_latex"):
            print(f"\nFormula (LaTeX): {c['formula_latex']}")
    elif ct == "table":
        print(f"Caption: {c.get('caption', '')}")
        print(f"Headers: {' | '.join(c.get('headers', []))}")
        for r in c.get("rows", [])[:8]:
            print("         " + " | ".join(str(x) for x in r))
        if len(c.get("rows", [])) > 8:
            print(f"         ... ({len(c['rows']) - 8} more rows)")
    else:
        print(c.get("nl_caption", "") or c.get("caption", "")[:max_chars])
