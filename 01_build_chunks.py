"""
Build chunks from the actual content of IS 6403:1981, pages 13-21.

Notes on copyright: This is for internal R&D use. The chunk text is
paraphrased / restructured for embedding quality, not reproduced verbatim
from the standard. Tables are stored as structured data (factual values).
Figures are stored as images extracted from the PDF with NL captions.
"""

import json
from pathlib import Path

DATA = Path(__file__).parent / "data"
CODE = "IS 6403:1981"

chunks = []

# ============================================================================
# CLAUSES (with embedded formulas)
# ============================================================================

chunks.append({
    "id": "cl_5_0_1_eccentricity",
    "content_type": "clause",
    "code": CODE, "clause": "5.0.1", "page": 7,
    "title": "Effect of eccentricity on footing dimensions",
    "text": (
        "When loading is eccentric with respect to the centroid of the "
        "foundation, the footing dimensions used in the bearing capacity "
        "equation must be reduced. For single eccentricity e, reduce the "
        "dimension in that direction by 2e. For double eccentricity (e_L "
        "along length, e_B along width), the effective dimensions are "
        "L' = L - 2*e_L, B' = B - 2*e_B, and effective area A' = L' * B'. "
        "These effective dimensions are then used in the bearing capacity "
        "formula and for computing area resisting load."
    ),
    "formula_latex": r"L' = L - 2 e_L,\quad B' = B - 2 e_B,\quad A' = L' \cdot B'",
    "formula_nl_summary": (
        "Reduce footing dimensions by twice the eccentricity in each direction "
        "to get effective dimensions for bearing capacity calculation."
    ),
})

chunks.append({
    "id": "cl_5_1_1_strip_general",
    "content_type": "clause",
    "code": CODE, "clause": "5.1.1", "page": 7,
    "title": "Ultimate net bearing capacity of strip footing — general and local shear failure",
    "text": (
        "For a strip footing in soil with cohesion c and angle of shearing "
        "resistance phi, ultimate net bearing capacity q_d is computed as: "
        "(a) general shear failure: q_d = c*Nc + q*(Nq - 1) + 0.5*B*gamma*N_gamma; "
        "(b) local shear failure: q'_d = (2/3)*c*N'c + q*(N'q - 1) + 0.5*B*gamma*N'_gamma. "
        "Here q is effective surcharge at base level, B is footing width, "
        "gamma is bulk unit weight. Bearing capacity factors Nc, Nq, N_gamma "
        "(general) and N'c, N'q, N'_gamma (local) are read from Table 1 — "
        "for local shear, evaluate at phi' = arctan(0.67 * tan phi) and "
        "use the same table."
    ),
    "formula_latex": (
        r"q_d = c N_c + q(N_q - 1) + \tfrac{1}{2} B \gamma N_\gamma "
        r"\quad (\text{general shear})"
    ),
    "formula_nl_summary": (
        "Terzaghi-type three-term bearing capacity formula for strip footings: "
        "cohesion term + surcharge term + width term. Bearing capacity factors "
        "Nc, Nq, N_gamma depend on phi (Table 1)."
    ),
    "see_also": ["table_1_bearing_factors"],
})

chunks.append({
    "id": "cl_5_1_2_modified",
    "content_type": "clause",
    "code": CODE, "clause": "5.1.2", "page": 8,
    "title": "Modified bearing capacity formula — shape, depth, inclination, water table corrections",
    "text": (
        "The strip-footing formula in 5.1.1 is corrected for non-strip shape, "
        "embedment depth, load inclination, and water table position. The "
        "modified general-shear formula is: q_d = c*Nc*sc*dc*ic + q*(Nq-1)*sq*dq*iq + "
        "0.5*B*gamma*N_gamma*s_gamma*d_gamma*i_gamma * W'. "
        "Local-shear form replaces (Nc, Nq, N_gamma) with (N'c, N'q, N'_gamma) "
        "and the cohesion term has a 2/3 factor. "
        "s = shape factors (Table 2), d = depth factors (5.1.2.2), "
        "i = inclination factors (5.1.2.3), W' = water-table correction (5.1.2.4)."
    ),
    "formula_latex": (
        r"q_d = c N_c s_c d_c i_c + q(N_q-1) s_q d_q i_q + "
        r"\tfrac{1}{2} B \gamma N_\gamma s_\gamma d_\gamma i_\gamma W'"
    ),
    "formula_nl_summary": (
        "Full bearing capacity formula combining strip-footing equation with "
        "shape, depth, inclination, and water-table corrections."
    ),
    "see_also": ["table_1_bearing_factors", "table_2_shape_factors",
                 "cl_5_1_2_2_depth", "cl_5_1_2_3_inclination", "cl_5_1_2_4_water"],
})

chunks.append({
    "id": "cl_5_1_2_2_depth",
    "content_type": "clause",
    "code": CODE, "clause": "5.1.2.2", "page": 9,
    "title": "Depth factors dc, dq, d_gamma",
    "text": (
        "Depth factors account for the increase in bearing capacity due to "
        "embedment Df: "
        "dc = 1 + 0.2 * (Df/B) * sqrt(N_phi); "
        "for phi < 10 degrees, dq = d_gamma = 1; "
        "for phi > 10 degrees, dq = d_gamma = 1 + 0.1 * (Df/B) * sqrt(N_phi). "
        "Here N_phi = tan^2(pi/4 + phi/2). "
        "These corrections apply only when backfill is properly compacted."
    ),
    "formula_latex": (
        r"d_c = 1 + 0.2 \tfrac{D_f}{B}\sqrt{N_\phi},\quad "
        r"d_q = d_\gamma = 1 + 0.1 \tfrac{D_f}{B}\sqrt{N_\phi}\ (\phi > 10°)"
    ),
    "formula_nl_summary": (
        "Depth factors increase bearing capacity for deeper embedment. "
        "dc grows with sqrt(N_phi); dq, d_gamma equal 1 for low phi and grow "
        "for phi > 10 degrees."
    ),
})

chunks.append({
    "id": "cl_5_1_2_3_inclination",
    "content_type": "clause",
    "code": CODE, "clause": "5.1.2.3", "page": 9,
    "title": "Inclination factors ic, iq, i_gamma",
    "text": (
        "Inclination factors reduce bearing capacity for inclined loads. "
        "With alpha being the inclination of the load to the vertical in "
        "degrees: ic = iq = (1 - alpha/90)^2; i_gamma = (1 - alpha/phi)^2. "
        "All factors equal 1 for vertical loads (alpha = 0)."
    ),
    "formula_latex": (
        r"i_c = i_q = \left(1 - \tfrac{\alpha}{90}\right)^2,\quad "
        r"i_\gamma = \left(1 - \tfrac{\alpha}{\phi}\right)^2"
    ),
    "formula_nl_summary": (
        "Inclination factors penalise capacity when the load isn't vertical. "
        "ic and iq use alpha/90 (degrees); i_gamma uses alpha/phi."
    ),
})

chunks.append({
    "id": "cl_5_1_2_4_water",
    "content_type": "clause",
    "code": CODE, "clause": "5.1.2.4", "page": 9,
    "title": "Effect of water table — correction factor W'",
    "text": (
        "Water-table position affects effective unit weight and is captured "
        "by W' on the gamma term: "
        "(a) if water table is at depth >= (Df + B) below ground, W' = 1.0; "
        "(b) if water table is at depth Df (i.e., at base of footing) or "
        "above, W' = 0.5; "
        "(c) for water table between Df and (Df + B), interpolate W' linearly "
        "between 1.0 and 0.5."
    ),
    "formula_nl_summary": (
        "Water table correction W' on the gamma (width) term: 1.0 if water is "
        "deep, 0.5 if water reaches the footing base, linear interpolation between."
    ),
})

chunks.append({
    "id": "cl_5_2_2_spt",
    "content_type": "clause",
    "code": CODE, "clause": "5.2.2", "page": 10,
    "title": "Cohesionless soil — bearing capacity from Standard Penetration Resistance (SPT)",
    "text": (
        "Standard penetration resistance N is measured at 75 cm vertical "
        "intervals (or at strata changes) per IS 2131:1981, between footing "
        "base level and a depth of 1.5B to 2B below it. Average the values "
        "(rejecting any individual value more than 50 percent of the average "
        "per Amendment 1; loose-seam values are always retained). "
        "Compute capacity using: q_d = q*(Nq - 1)*sq*dq*iq + 0.5*B*gamma*N_gamma*s_gamma*d_gamma*i_gamma*W'. "
        "Read phi from Fig 1 (phi vs N), then read Nq, N_gamma from Table 1."
    ),
    "formula_latex": (
        r"q_d = q(N_q - 1) s_q d_q i_q + \tfrac{1}{2} B \gamma N_\gamma s_\gamma d_\gamma i_\gamma W'"
    ),
    "formula_nl_summary": (
        "For sand/cohesionless soil, derive phi from SPT N-value via Fig 1, "
        "then apply the standard formula with c=0."
    ),
    "see_also": ["fig_1_phi_vs_N", "table_1_bearing_factors"],
})

chunks.append({
    "id": "cl_5_2_3_cone",
    "content_type": "clause",
    "code": CODE, "clause": "5.2.3", "page": 10,
    "title": "Cohesionless soil — bearing capacity from static cone penetration test",
    "text": (
        "Static cone point resistance qc is measured at 10–15 cm intervals "
        "per IS 4968 Part III, corrected for sounding-rod dead weight. "
        "Average values between footing base and 1.5B–2B below; take the "
        "minimum location-average for design. For shallow strip footings on "
        "cohesionless soils, ultimate bearing capacity is read from Fig 2 "
        "(qd/qc vs B for Df/B = 0, 0.5, 1.0)."
    ),
    "formula_nl_summary": (
        "For sand from cone test: read qd/qc from Fig 2 using footing width B "
        "and embedment ratio Df/B."
    ),
    "see_also": ["fig_2_cone_chart"],
})

chunks.append({
    "id": "cl_5_3_1_1_cohesive_homog",
    "content_type": "clause",
    "code": CODE, "clause": "5.3.1.1", "page": 10,
    "title": "Cohesive soil (phi = 0) — homogeneous layer, immediate post-construction",
    "text": (
        "For fairly saturated homogeneous cohesive soil with phi = 0, "
        "ultimate net bearing capacity immediately after construction is: "
        "q_d = c * Nc * sc * dc * ic, with Nc = 5.14. "
        "Cohesion c is from unconfined compressive strength test (or from "
        "static cone qc per 5.3.1.2). Shape, depth, inclination factors are "
        "as in 5.1. If shear strength within (2/3)B beneath the foundation "
        "varies less than 50 percent from the average, the average value may be used."
    ),
    "formula_latex": r"q_d = c N_c s_c d_c i_c \quad \text{with } N_c = 5.14",
    "formula_nl_summary": (
        "For purely cohesive soil (phi = 0), bearing capacity reduces to "
        "c * 5.14 with shape/depth/inclination corrections. Used for clays "
        "right after construction, before consolidation."
    ),
})

chunks.append({
    "id": "cl_5_3_1_2_cohesion_from_cone",
    "content_type": "clause",
    "code": CODE, "clause": "5.3.1.2", "page": 12,
    "title": "Cohesion c from static cone resistance qc",
    "text": (
        "When direct cohesion measurement isn't available, cohesion can be "
        "estimated from static cone point resistance qc: "
        "for normally consolidated clays (qc < 20 kgf/cm^2), c is in the "
        "range qc/18 to qc/15. "
        "For over-consolidated clays (qc > 20 kgf/cm^2), c is in the range "
        "qc/26 to qc/22."
    ),
    "formula_nl_summary": (
        "Empirical cohesion-from-cone relationships: NC clays have c ~ qc/15-qc/18; "
        "OC clays have c ~ qc/22-qc/26."
    ),
})

chunks.append({
    "id": "cl_5_3_2_two_layered",
    "content_type": "clause",
    "code": CODE, "clause": "5.3.2", "page": 12,
    "title": "Two-layered cohesive soil system",
    "text": (
        "For two layered cohesive soils without marked anisotropy, ultimate "
        "net bearing capacity of a strip footing is: q_d = c1 * Nc, where c1 "
        "is undrained cohesion of the top layer and Nc is read from Fig 3. "
        "Fig 3 plots Nc as a function of c1/c2 ratio (top to bottom layer "
        "cohesion) and d/b ratio (where d is top layer thickness below the "
        "footing base and b is half the footing width). "
        "Note (Amendment 1, 1984): Fig 3 axis ratio was corrected to c2/c1; "
        "the figure as printed shows c1/c2."
    ),
    "formula_latex": r"q_d = c_1 N_c \quad (\text{Fig. 3})",
    "formula_nl_summary": (
        "For a layered clay system, capacity is c1 (top-layer cohesion) times "
        "Nc, where Nc depends on cohesion ratio and top layer thickness via Fig 3."
    ),
    "see_also": ["fig_3_layered_Nc"],
})

chunks.append({
    "id": "cl_5_3_3_desiccated",
    "content_type": "clause",
    "code": CODE, "clause": "5.3.3", "page": 13,
    "title": "Desiccated cohesive soil — cohesion decreasing with depth",
    "text": (
        "In desiccated cohesive soils, undrained cohesion decreases roughly "
        "linearly with depth before stabilizing (typically by ~3.5 m). "
        "Where the pressure bulb falls within the desiccated top soil and a "
        "linear cohesion-depth profile is established (Fig 4 — lambda is the "
        "rate of decrease of c with depth), capacity is obtained from Table 4 "
        "by trial and error: pick a candidate q_d, compute 4*lambda*B/q_d "
        "(corrected from 8*lambda*B/q_d per Amendment 1, 1984), and match it "
        "with q_d/c1 from Table 4. The procedure assumes a cylindrical failure "
        "surface (Amendment 1)."
    ),
    "formula_nl_summary": (
        "Desiccated clay procedure: iterate q_d by matching the dimensionless "
        "ratio 4*lambda*B/q_d against q_d/c1 from Table 4."
    ),
    "see_also": ["fig_4_desiccated", "table_4_desiccated"],
})

chunks.append({
    "id": "cl_6_1_allowable",
    "content_type": "clause",
    "code": CODE, "clause": "6.1", "page": 14,
    "title": "Allowable bearing capacity",
    "text": (
        "Allowable bearing capacity is taken as the lesser of: "
        "(a) net ultimate bearing capacity from Section 5 divided by a "
        "suitable factor of safety — i.e., net safe bearing capacity; "
        "(b) net soil pressure that can be imposed without settlement "
        "exceeding permissible values per IS 1904:1978 — i.e., safe bearing "
        "pressure (clause 6.1.1)."
    ),
    "formula_nl_summary": (
        "Allowable bearing capacity = min(net safe bearing capacity from shear, "
        "safe bearing pressure from settlement)."
    ),
})

chunks.append({
    "id": "cl_6_1_1_safe_pressure",
    "content_type": "clause",
    "code": CODE, "clause": "6.1.1", "page": 15,
    "title": "Safe bearing pressure — settlement-controlled",
    "text": (
        "Safe bearing pressure is the soil pressure that produces permissible "
        "settlement per IS 1904:1978. Compute settlements for two or three "
        "trial pressures using IS 8009 Part I (1976), then interpolate to find "
        "the pressure corresponding to permissible settlement. "
        "Per Amendment 1 (1984), this can also be derived from plate load "
        "test results (IS 1888:1982) or from standard penetration resistance."
    ),
    "formula_nl_summary": (
        "Pressure that limits settlement to permissible values; computed by "
        "interpolating settlement-pressure curves or from plate load / SPT data."
    ),
})

# ============================================================================
# TABLES
# ============================================================================

chunks.append({
    "id": "table_1_bearing_factors",
    "content_type": "table",
    "code": CODE, "clause": "5.1.1", "page": 8,
    "table_number": "1",
    "caption": "Bearing capacity factors Nc, Nq, N_gamma as a function of angle of shearing resistance phi.",
    "headers": ["phi (deg)", "Nc", "Nq", "N_gamma"],
    "rows": [
        ["0",  "5.14",   "1.00",   "0.00"],
        ["5",  "6.49",   "1.57",   "0.45"],
        ["10", "8.35",   "2.47",   "1.22"],
        ["15", "10.98",  "3.94",   "2.65"],
        ["20", "14.83",  "6.40",   "5.39"],
        ["25", "20.72",  "10.66",  "10.88"],
        ["30", "30.14",  "18.40",  "22.40"],
        ["35", "46.12",  "33.30",  "48.03"],
        ["40", "75.31",  "64.20",  "109.41"],
        ["45", "138.88", "134.88", "271.76"],
        ["50", "266.89", "319.07", "762.89"],
    ],
    "note": (
        "For local shear failure factors N'c, N'q, N'_gamma: compute "
        "phi' = arctan(0.67 * tan phi) and read the table at phi' instead. "
        "The values returned are then N'c, N'q, N'_gamma."
    ),
    "nl_summary": (
        "Bearing capacity factors per IS 6403 Table 1. Values of Nc, Nq, "
        "N_gamma for phi from 0 to 50 degrees in 5-degree increments. Nc is "
        "the cohesion factor, Nq is the surcharge factor, N_gamma is the "
        "self-weight (width) factor. For phi=0, Nc=5.14, Nq=1, N_gamma=0. "
        "Values increase rapidly with phi: at phi=30, (30.14, 18.40, 22.40); "
        "at phi=40, (75.31, 64.20, 109.41)."
    ),
})

chunks.append({
    "id": "table_2_shape_factors",
    "content_type": "table",
    "code": CODE, "clause": "5.1.2.1", "page": 8,
    "table_number": "2",
    "caption": "Shape factors sc, sq, s_gamma for different footing shapes.",
    "headers": ["Shape", "sc", "sq", "s_gamma"],
    "rows": [
        ["Continuous strip", "1.00",          "1.00",          "1.00"],
        ["Rectangle",        "1 + 0.2*B/L",   "1 + 0.2*B/L",   "1 - 0.4*B/L"],
        ["Square",           "1.3",           "1.2",           "0.8"],
        ["Circle",           "1.3",           "1.2",           "0.6"],
    ],
    "note": "For circular footings, use B as the diameter in the bearing capacity formula.",
    "nl_summary": (
        "Shape factors per IS 6403 Table 2. Strip footing has all factors 1.0. "
        "Rectangular footings use B/L (width/length) ratio: sc and sq grow with "
        "B/L, s_gamma shrinks. Square gives sc=1.3, sq=1.2, s_gamma=0.8. "
        "Circle gives sc=1.3, sq=1.2, s_gamma=0.6."
    ),
})

chunks.append({
    "id": "table_3_relative_density",
    "content_type": "table",
    "code": CODE, "clause": "5.2.1.1", "page": 9,
    "table_number": "3",
    "caption": "Method of analysis (general/local shear) based on relative density of cohesionless soil.",
    "headers": ["Relative density", "Void ratio", "Condition", "Method of analysis"],
    "rows": [
        ["> 70%",       "< 0.55",     "Dense",  "General shear"],
        ["< 20%",       "> 0.75",     "Loose",  "Local shear (or punching)"],
        ["20% to 70%",  "0.55–0.75",  "Medium", "Interpolate between general and local shear"],
    ],
    "nl_summary": (
        "Choosing general vs local shear failure analysis for cohesionless "
        "soils based on relative density: dense (>70%) uses general shear, "
        "loose (<20%) uses local shear / punching, medium soils interpolate."
    ),
})

chunks.append({
    "id": "table_4_desiccated",
    "content_type": "table",
    "code": CODE, "clause": "5.3.3", "page": 14,
    "table_number": "4",
    "caption": (
        "Data for ultimate net bearing capacity of desiccated cohesive soil. "
        "Use 4*lambda*B/q_d (per Amendment 1; the original printing showed 8*lambda*B/q_d) "
        "matched against q_d/c1 by trial and error."
    ),
    "headers": ["4*lambda*B / q_d", "q_d / c1"],
    "rows": [
        ["0.0", "5.7"],
        ["0.2", "5.0"],
        ["0.4", "4.5"],
        ["0.6", "4.0"],
        ["0.8", "3.6"],
        ["1.0", "3.2"],
    ],
    "nl_summary": (
        "Desiccated cohesive soil bearing capacity table. As lambda*B/q_d "
        "increases (more cohesion-decrease relative to capacity), the "
        "q_d/c1 ratio drops from 5.7 (no decrease) to 3.2 (strong decrease). "
        "Used in trial-and-error solution of desiccated soil capacity."
    ),
})

# ============================================================================
# FIGURES (with digitised curve data where applicable)
# ============================================================================

chunks.append({
    "id": "fig_1_phi_vs_N",
    "content_type": "graph",
    "code": CODE, "clause": "5.2.2", "page": 11,
    "figure_number": "1",
    "figure_subtype": "phi_vs_spt",
    "image_path": str(DATA / "fig1_phi_vs_N.png"),
    "axes": {"x": "phi (degrees)", "y": "N (blows / 30 cm)"},

    # Hand-digitised from the printed figure
    "curves": [{
        "label": "phi vs N",
        "points": [
            {"x": 28.5, "y": 2},
            {"x": 30,   "y": 4},
            {"x": 32,   "y": 8},
            {"x": 34,   "y": 14},
            {"x": 36,   "y": 22},
            {"x": 38,   "y": 32},
            {"x": 40,   "y": 45},
            {"x": 42,   "y": 58},
            {"x": 44,   "y": 75},
        ],
    }],
    "density_categories": [
        {"label": "Very loose", "phi_range": [0, 30],  "N_range": [0, 4]},
        {"label": "Loose",      "phi_range": [30, 32], "N_range": [4, 10]},
        {"label": "Medium",     "phi_range": [32, 36], "N_range": [10, 30]},
        {"label": "Dense",      "phi_range": [36, 41], "N_range": [30, 50]},
        {"label": "Very dense", "phi_range": [41, 50], "N_range": [50, 100]},
    ],
    "nl_caption": (
        "Figure 1 of IS 6403 — relationship between angle of internal "
        "friction phi (degrees) and corrected SPT N value (blows per 30 cm) "
        "for cohesionless soils. Used to derive phi from SPT data for use "
        "in the bearing capacity formulae. Categories shown: very loose, "
        "loose, medium, dense, very dense. Curve shows N rising rapidly "
        "with phi: N = 4 at phi = 30 degrees, N = 22 at phi = 36, "
        "N = 45 at phi = 40, N = 75 at phi = 44."
    ),
})

chunks.append({
    "id": "fig_2_cone_chart",
    "content_type": "graph",
    "code": CODE, "clause": "5.2.3", "page": 12,
    "figure_number": "2",
    "figure_subtype": "cone_test_chart",
    "image_path": str(DATA / "fig2_cone_test_chart.png"),
    "axes": {"x": "B (cm)", "y": "qd / qc"},
    "nl_caption": (
        "Figure 2 of IS 6403 — chart for static cone test. Plots dimensionless "
        "ratio qd/qc (ultimate bearing capacity to cone resistance) against "
        "footing width B in cm, for three values of embedment ratio Df/B = 0, "
        "0.5, and 1.0. Used to determine bearing capacity of shallow strip "
        "footings on cohesionless soil from cone penetration test data. "
        "qd/qc decreases as B increases; ranges roughly from 0.0625 to 0.25 "
        "across the chart."
    ),
})

chunks.append({
    "id": "fig_3_layered_Nc",
    "content_type": "graph",
    "code": CODE, "clause": "5.3.2", "page": 13,
    "figure_number": "3",
    "figure_subtype": "layered_cohesive_Nc",
    "image_path": str(DATA / "fig3_layered_cohesive.png"),
    "axes": {"x": "c1/c2", "y": "Nc"},

    # Hand-digitised. All curves converge near (c1/c2 = 1, Nc ≈ 5.5).
    # For c1/c2 < 1 (top weaker): higher d/b => higher Nc (more top layer between footing and weak interface).
    # For c1/c2 > 1 (top stronger): lower d/b => higher Nc (failure pushed into stronger lower layer is harder).
    "curves": [
        {"label": "d/b = 0",
         "points": [{"x": 0, "y": 0}, {"x": 0.4, "y": 2.2}, {"x": 0.8, "y": 4.4},
                    {"x": 1.0, "y": 5.5}, {"x": 1.2, "y": 6.6}, {"x": 1.5, "y": 8.25},
                    {"x": 2.0, "y": 11.0}]},
        {"label": "d/b = 0.5 (lower)",   # only valid for c1/c2 <= 1
         "points": [{"x": 0, "y": 3.0}, {"x": 0.4, "y": 3.9},
                    {"x": 0.8, "y": 4.9}, {"x": 1.0, "y": 5.5}]},
        {"label": "d/b = 1.0 (lower)",
         "points": [{"x": 0, "y": 4.0}, {"x": 0.4, "y": 4.6},
                    {"x": 0.8, "y": 5.2}, {"x": 1.0, "y": 5.5}]},
        {"label": "d/b = 1.5 (lower)",
         "points": [{"x": 0, "y": 4.5}, {"x": 0.4, "y": 4.9},
                    {"x": 0.8, "y": 5.3}, {"x": 1.0, "y": 5.5}]},
        {"label": "d/b = 2.0 (lower)",
         "points": [{"x": 0, "y": 5.0}, {"x": 0.4, "y": 5.2},
                    {"x": 0.8, "y": 5.4}, {"x": 1.0, "y": 5.5}]},
        {"label": "d/b = 0.2 (upper)",   # only valid for c1/c2 >= 1
         "points": [{"x": 1.0, "y": 5.5}, {"x": 1.2, "y": 6.5},
                    {"x": 1.5, "y": 8.1}, {"x": 2.0, "y": 10.2}]},
        {"label": "d/b = 0.4 (upper)",
         "points": [{"x": 1.0, "y": 5.5}, {"x": 1.2, "y": 6.3},
                    {"x": 1.5, "y": 7.7}, {"x": 2.0, "y": 9.5}]},
        {"label": "d/b = 0.6 (upper)",
         "points": [{"x": 1.0, "y": 5.5}, {"x": 1.2, "y": 6.0},
                    {"x": 1.5, "y": 6.7}, {"x": 2.0, "y": 7.0}]},
        {"label": "d/b = 0.8 (upper)",
         "points": [{"x": 1.0, "y": 5.5}, {"x": 1.2, "y": 5.8},
                    {"x": 1.5, "y": 6.1}, {"x": 2.0, "y": 6.3}]},
        {"label": "d/b = 1.0 (upper)",
         "points": [{"x": 1.0, "y": 5.5}, {"x": 1.2, "y": 5.6},
                    {"x": 1.5, "y": 5.7}, {"x": 2.0, "y": 5.7}]},
    ],
    "amendment_note": (
        "Per Amendment 1 (May 1984), the original Fig 3 x-axis label "
        "'c1/c2' was directed to be substituted with 'c2/c1'. "
        "The figure as printed in the standard shows c1/c2."
    ),
    "nl_caption": (
        "Figure 3 of IS 6403 — bearing capacity factor Nc for layered cohesive "
        "soil deposits, plotted against ratio c1/c2 (top to bottom layer "
        "undrained cohesion) for various d/b ratios, where d is top layer "
        "thickness below footing and b is half the footing width. Two families "
        "of curves: lower-side curves (c1/c2 < 1, top layer weaker) labeled "
        "d/b = 0, 0.5, 1.0, 1.5, 2.0; upper-side curves (c1/c2 > 1, top "
        "stronger) labeled d/b = 0, 0.2, 0.4, 0.6, 0.8, 1.0. All curves "
        "converge at (c1/c2 = 1, Nc ~ 5.5). Used together with q_d = c1 * Nc "
        "for two-layered cohesive systems."
    ),
})

chunks.append({
    "id": "fig_4_desiccated",
    "content_type": "figure",
    "code": CODE, "clause": "5.3.3", "page": 14,
    "figure_number": "4",
    "figure_subtype": "desiccated_schematic",
    "image_path": str(DATA / "fig4_desiccated.png"),
    "nl_caption": (
        "Figure 4 of IS 6403 — schematic showing the geometry of bearing "
        "capacity in desiccated cohesive soil. Left subfigure shows the "
        "footing width B, applied pressure q_d, and the assumed cylindrical "
        "failure surface extending below. Right subfigure shows undrained "
        "cohesion c (kgf/cm^2) decreasing linearly with depth at rate lambda "
        "(per cm), starting from value c1 at the surface. lambda is the "
        "slope of the c-vs-depth profile and is determined from borehole data."
    ),
})

# ============================================================================
# Save
# ============================================================================

(DATA / "chunks.json").write_text(json.dumps(chunks, indent=2))
print(f"Wrote {len(chunks)} chunks to {DATA / 'chunks.json'}")
print()
for c in chunks:
    print(f"  [{c['content_type']:6s}]  {c['id']:30s}  cl. {c['clause']:8s}  p.{c['page']}")
