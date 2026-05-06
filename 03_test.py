"""Test the IS 6403 RAG with a battery of questions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from importlib import import_module
rag = import_module("02_rag")


# Test set: each entry is (question, expected_top_chunk_id) for grading
tests = [
    # --- clauses ---
    ("How do I calculate the depth factor dc?",          "cl_5_1_2_2_depth"),
    ("What's the formula for ultimate bearing capacity of a strip footing?",
                                                          "cl_5_1_1_strip_general"),
    ("How is the inclination factor i_gamma calculated?", "cl_5_1_2_3_inclination"),
    ("What if water table rises to the base of the footing?",
                                                          "cl_5_1_2_4_water"),
    ("How do I get cohesion from cone penetration test?", "cl_5_3_1_2_cohesion_from_cone"),
    ("What's the procedure for desiccated cohesive soil?", "cl_5_3_3_desiccated"),
    ("Define allowable bearing capacity",                  "cl_6_1_allowable"),

    # --- tables ---
    ("What is Nc for phi = 30 degrees?",                  "table_1_bearing_factors"),
    ("What's the shape factor s_gamma for a square footing?",
                                                          "table_2_shape_factors"),
    ("When should I use general shear vs local shear analysis?",
                                                          "table_3_relative_density"),

    # --- graphs ---
    ("Show me the relationship between phi and SPT N",    "fig_1_phi_vs_N"),
    ("Chart for static cone test",                         "fig_2_cone_chart"),
    ("Bearing capacity factor for two layered cohesive soil", "fig_3_layered_Nc"),

    # --- direct clause-number lookup ---
    ("What does clause 5.3.2 cover?",                     "cl_5_3_2_two_layered"),
    ("Explain Table 4",                                    "table_4_desiccated"),
    ("What's in Figure 3?",                                "fig_3_layered_Nc"),
]

# ---------- Retrieval correctness ----------
print("=" * 78)
print("RETRIEVAL TEST")
print("=" * 78)
hits = 0
for q, expected in tests:
    results = rag.search(q, top_k=3)
    top_id = results[0][1]["id"]
    ok = (top_id == expected)
    hits += int(ok)
    mark = "✓" if ok else "✗"
    print(f"  {mark}  {q[:62]:64s}  → {top_id}")
    if not ok:
        print(f"      expected: {expected}")

print(f"\nTop-1 accuracy: {hits}/{len(tests)} = {100*hits/len(tests):.0f}%")

# ---------- Numeric lookups ----------
print("\n" + "=" * 78)
print("NUMERIC LOOKUPS")
print("=" * 78)

print("\nTable 1 — bearing capacity factors at exact and interpolated phi:")
for phi in [30, 32.5, 38, 27]:
    print(f"  phi={phi:5}°  →  {rag.lookup_table1(phi)}")

print("\nFig 1 — phi vs N (forward and inverse):")
for phi in [32, 38, 41]:
    r = rag.lookup_fig1_N_from_phi(phi)
    print(f"  phi={phi}° → N≈{r['N']:.1f}")
for N in [10, 25, 50]:
    r = rag.lookup_fig1_phi_from_N(N)
    print(f"  N={N} → phi≈{r['phi_deg']:.1f}°")

print("\nFig 3 — layered cohesive Nc(c1/c2, d/b):")
test_cases = [
    (0.5, 1.0),     # top weaker, moderate top thickness
    (1.5, 0.4),     # top stronger, thin top
    (1.0, 0.5),     # right at convergence
    (0.4, 0.75),    # interpolated d/b on lower side
    (1.8, 0.3),     # interpolated d/b on upper side
]
for c1_c2, db in test_cases:
    r = rag.lookup_fig3_Nc(c1_c2, db)
    if r.get("Nc") is not None:
        print(f"  c1/c2={c1_c2}, d/b={db}  →  Nc≈{r['Nc']:.2f}  "
              f"(interp between {r['interpolated_between']})")
    else:
        print(f"  c1/c2={c1_c2}, d/b={db}  →  {r.get('error')}")

# ---------- Show one full retrieval-and-render example ----------
print("\n" + "=" * 78)
print("FULL RETRIEVAL + RENDER  (what an LLM would see)")
print("=" * 78)

q = "How do I calculate ultimate bearing capacity for a square footing in cohesionless soil with phi=35 degrees?"
results = rag.search(q, top_k=3)
print(f"\nQ: {q}")
print(f"\nRetrieved {len(results)} chunks:")
for score, c in results:
    print(f"  - [{c['content_type']:6s}] {c['id']}  (score {score:.3f})")
for score, c in results:
    rag.render_chunk(c, max_text_chars=400)
