"""
Streamlit dashboard for the IS 456:2000 RAG.

ChatGPT-style UX:
  - Sidebar lists past conversations (most recent first)
  - "+ New chat" button starts a fresh conversation
  - Click any conversation to load it
  - Delete with confirmation per conversation
  - LLM call sees the full conversation history (in-session memory)
  - Everything persists in chat.db (SQLite)

Coverage:
  74 chunks across IS 456 Sections 26, 38, 39, 40, 41
  (reinforcement detailing, flexure, compression, shear, torsion)

Run:
    pip install -r requirements.txt
    cp .env.example .env       # then add OPENROUTER_API_KEY
    streamlit run app.py
"""

import os
import re
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))
from importlib import import_module
rag = import_module("02_rag")
import db

db.init_db()


# ---------------------------------------------------------------------------
# OpenRouter client
# ---------------------------------------------------------------------------
def make_client():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


AVAILABLE_MODELS = [
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "anthropic/claude-sonnet-4.5",
    "anthropic/claude-3.5-haiku",
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-3.3-70b-instruct",
]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a structural engineering assistant for IS 456:2000
(Indian Standard — Plain and Reinforced Concrete, Code of Practice).

The RAG indexes Sections 26 (reinforcement detailing), 38 (flexure),
39 (compression members), 40 (shear), and 41 (torsion). Anything outside
these sections is NOT in the index — say so plainly rather than guessing.

Rules you must follow:
1. Answer using ONLY the SOURCES provided in the latest user message. Do not
   use your training-data knowledge of IS 456 — if it's not in the sources,
   say so explicitly.
2. Every factual claim must cite as [IS 456:2000 cl. X.Y, p. Z].
3. If DETERMINISTIC LOOKUPS are provided, use those numerical values verbatim.
   Do not recompute or approximate.
4. If retrieval scores are low (top score < 0.30) or no source addresses the
   question, say so plainly rather than guessing.
5. Keep answers concise and engineering-focused. Show working when interpolating.
   Use units consistently (typically N/mm² for stress, mm for length).
6. MATH FORMATTING: Streamlit renders math only when wrapped in $...$ (inline)
   or $$...$$ (display block). Always use these delimiters — never use square
   brackets [ ... ], \\( ... \\), or \\[ ... \\] for math.
7. CONVERSATIONAL CONTEXT: You see the full conversation history. Use it for
   follow-up questions ("what about for M30?", "and for Fe500?") — but each
   new turn still has its own SOURCES section that's the authoritative ground
   truth. Don't trust earlier-turn assistant answers as a source — only the
   SOURCES blocks in user messages."""


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------
def build_sources_block(retrieved):
    blocks = []
    for rank, (score, c) in enumerate(retrieved, 1):
        cite = f"IS 456:2000 cl. {c['clause']}, p. {c.get('page', '?')}"
        ct = c["content_type"]
        if ct == "clause":
            b = f"[Source {rank} — {cite}]\n{c.get('title', '')}\n{c.get('text', '')}"
            if c.get("formula_latex"):
                b += f"\nFormula (LaTeX): {c['formula_latex']}"
        elif ct == "table":
            rows = "\n".join("| " + " | ".join(str(x) for x in r) + " |"
                              for r in c.get("rows", []))
            b = (f"[Source {rank} — {cite}]\nTable {c.get('table_number', '?')}: "
                 f"{c.get('caption', '')}\n| {' | '.join(c.get('headers', []))} |\n{rows}")
            if c.get("note"):
                b += f"\nNote: {c['note']}"
        else:   # graph or figure
            b = (f"[Source {rank} — {cite}]\n"
                 f"Figure {c.get('figure_number', '?')}: {c.get('title', '')}\n"
                 f"{c.get('nl_caption', '') or c.get('caption', '')}")
        blocks.append(b)
    return "\n\n".join(blocks)


def auto_detect_lookups(query: str):
    """Run deterministic numeric lookups when the query has the right parameters."""
    out = []
    ql = query.lower()

    # Helpers to pull common parameters from the query
    def extract_grade():
        m = re.search(r"\bm\s*(15|20|25|30|35|40|45|50)\b", ql)
        return f"M{m.group(1)}" if m else None

    def extract_float(*patterns):
        for pat in patterns:
            m = re.search(pat, ql)
            if m:
                try:
                    return float(m.group(1))
                except (ValueError, IndexError):
                    pass
        return None

    grade = extract_grade()
    pt = extract_float(r"(?:pt|p_?t|percentage tension|tension steel)\s*[=:]?\s*(\d+(?:\.\d+)?)")
    fy = extract_float(r"\bfy\s*[=:]?\s*(\d+)", r"\bfe\s*(\d{3})\b")
    strain = extract_float(r"(?:strain|ε|epsilon)\s*[=:]?\s*(\d*\.\d+)")
    fck = extract_float(r"\bfck\s*[=:]?\s*(\d+)")
    D = extract_float(r"\bd\s*[=:]?\s*(\d+)\s*mm", r"depth\s*(?:of\s*slab)?\s*[=:]?\s*(\d+)\s*mm",
                       r"slab.{0,15}\b(\d{2,4})\s*mm")

    # Table 19: τ_c (needs pt + grade)
    if pt is not None and grade:
        out.append(("Table 19 (τ_c)", rag.lookup_table_19(pt, grade)))

    # Table 20: τ_c,max (needs grade + max-shear context)
    elif grade and any(w in ql for w in ["max shear", "tau max", "τ max",
                                          "maximum shear", "tc,max", "τc,max",
                                          "tau_c_max"]):
        out.append(("Table 20 (τ_c,max)", rag.lookup_table_20(grade)))

    # Table 38.1: xu,max/d (needs fy + xu/max context)
    if fy is not None and any(w in ql for w in ["xu", "x_u", "neutral axis",
                                                  "maximum depth"]):
        out.append(("Table 38.1 (xu,max/d)", rag.lookup_xu_max_d(fy)))

    # Slab depth factor k
    if D is not None and any(w in ql for w in ["slab", "depth factor", "k factor"]):
        out.append(("Slab depth factor k", rag.lookup_slab_depth_factor(D)))

    # Bond stress
    if grade and any(w in ql for w in ["bond stress", "τ_bd", "tau_bd", "tau bd"]):
        bar_type = "deformed" if any(w in ql for w in ["deformed", "hysd", "is 1786"]) else "plain"
        direction = "compression" if "compression" in ql else "tension"
        out.append((f"Bond stress τ_bd ({bar_type}, {direction})",
                    rag.lookup_bond_stress(grade, bar_type, direction)))

    # Fig 21: concrete stress at strain
    if strain is not None and fck is not None:
        out.append(("Fig 21 (concrete stress)",
                    rag.lookup_fig21_concrete_stress(strain, fck)))
    elif strain is not None and grade:
        # Grade implies fck (M25 → fck=25 etc.)
        fck_implied = int(grade[1:])
        out.append((f"Fig 21 (concrete stress, fck={fck_implied} from {grade})",
                    rag.lookup_fig21_concrete_stress(strain, fck_implied)))

    # Fig 23A: steel stress at strain
    if strain is not None and fy is not None:
        out.append(("Fig 23A (steel stress)",
                    rag.lookup_fig23a_steel_stress(strain, fy)))

    return out


def call_llm(client, model, system_prompt, conversation_messages, temperature=0.2):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            *conversation_messages,
        ],
        temperature=temperature,
        max_tokens=1500,
        extra_headers={
            "HTTP-Referer": "http://localhost:8501",
            "X-Title": "IS 456 RAG Dashboard",
        },
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Math-delimiter post-processing
# ---------------------------------------------------------------------------
_RE_DISPLAY_ESCAPE = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
_RE_INLINE_ESCAPE = re.compile(r"\\\((.+?)\\\)", re.DOTALL)
_RE_BRACKET_MATH = re.compile(
    r"\[\s*((?:[^\[\]]*?\\[a-zA-Z]+[^\[\]]*?))\s*\]", re.DOTALL,
)


def _looks_like_citation(content: str) -> bool:
    s = content.strip()
    return (s.startswith("IS ")
            or "cl." in s.lower()
            or re.match(r"^[A-Z\s\d:.,\-]+$", s) is not None)


def fix_math_delimiters(text: str) -> str:
    text = _RE_DISPLAY_ESCAPE.sub(lambda m: f"\n$$ {m.group(1).strip()} $$\n", text)
    text = _RE_INLINE_ESCAPE.sub(lambda m: f"${m.group(1).strip()}$", text)

    def _bracket_replace(m):
        if _looks_like_citation(m.group(1)):
            return m.group(0)
        return f"\n$$ {m.group(1).strip()} $$\n"

    return _RE_BRACKET_MATH.sub(_bracket_replace, text)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
def init_session():
    if "active_conversation_id" not in st.session_state:
        st.session_state.active_conversation_id = None
    if "pending_delete" not in st.session_state:
        st.session_state.pending_delete = None


def start_new_conversation():
    new_id = db.create_conversation()
    st.session_state.active_conversation_id = new_id


def switch_conversation(conv_id: int):
    st.session_state.active_conversation_id = conv_id


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="IS 456 RAG", layout="wide",
                   initial_sidebar_state="expanded")

init_session()


# Base CSS — always on
st.markdown("""
<style>
    /* Kill the huge default top padding on the main pane */
    [data-testid="stMain"] .main .block-container,
    [data-testid="stMain"] [data-testid="stMainBlockContainer"] {
        padding-top: 0.5rem !important;
        padding-bottom: 1rem !important;
        max-width: 880px;
    }
    /* Hide the empty deploy bar at top-right area gap */
    [data-testid="stToolbar"] { display: none !important; }
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: auto !important;
    }
    /* Keep the sidebar expand button visible when sidebar is collapsed */
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
    }
    /* Custom heading — smaller than st.title, less margin */
    h2.conv-title {
        font-size: 1.4rem !important;
        font-weight: 600 !important;
        margin: 0 0 0.5rem 0 !important;
        padding: 0 !important;
        line-height: 1.3 !important;
    }

    /* SIDEBAR — Claude-style tight conversation list */
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0.5rem !important;
    }
    /* Default Streamlit button (sidebar conversation tiles) — compact */
    section[data-testid="stSidebar"] .stButton > button {
        text-align: left;
        justify-content: flex-start;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        height: auto;
        padding: 0.4rem 0.7rem !important;
        line-height: 1.2 !important;
        font-size: 0.875rem !important;
        font-weight: 400 !important;
        border: 1px solid transparent !important;
        background-color: transparent !important;
        border-radius: 6px !important;
        margin: 0 !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background-color: rgba(120, 120, 220, 0.08) !important;
    }
    /* Conversation row containers — kill vertical gap */
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        gap: 0.15rem !important;
        margin-bottom: 0.1rem !important;
    }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.15rem !important;
    }
    /* Active conversation — highlighted */
    .active-conv > div > button {
        background-color: rgba(120, 120, 220, 0.18) !important;
        font-weight: 500 !important;
    }
    /* New chat button — distinct, slightly more prominent */
    .new-chat-btn > div > button {
        background-color: #f5f5f7 !important;
        color: #1a1b1e !important;
        border: 1px solid #e0e0e3 !important;
        font-weight: 500 !important;
        padding: 0.5rem 0.75rem !important;
    }
    .new-chat-btn > div > button:hover {
        background-color: #ebebee !important;
        border-color: #d0d0d3 !important;
    }
    /* Delete (🗑) button — target STABLE Streamlit classes (not auto-generated cache classes) */

    /* The box is drawn by the tooltip wrapper because of help= attribute.
       Kill its borders, backgrounds, padding on every element inside .del-btn */
    .del-btn .stTooltipIcon,
    .del-btn .stTooltipHoverTarget,
    .del-btn .stButton,
    .del-btn .stVerticalBlock,
    .del-btn .stHorizontalBlock,
    .del-btn [class*="stTooltip"],
    .del-btn [class*="stButton"],
    .del-btn div,
    .del-btn span {
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* The button itself: red icon, no background */
    .del-btn button {
        all: unset !important;
        cursor: pointer !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 1.8rem !important;
        height: 1.8rem !important;
        font-size: 0.95rem !important;
        line-height: 1 !important;
        color: #d04040 !important;
        opacity: 0.55 !important;
        border-radius: 4px !important;
        transition: opacity 0.15s ease, background-color 0.15s ease;
    }
    .del-btn button:hover {
        opacity: 1 !important;
        background-color: rgba(208, 64, 64, 0.10) !important;
        color: #c02020 !important;
    }
    .del-btn button:focus,
    .del-btn button:active {
        outline: none !important;
        box-shadow: none !important;
    }

    /* Top-spacing — use STABLE class names */
    .stMainBlockContainer,
    .stAppViewContainer .stMain .stMainBlockContainer,
    .main .block-container,
    [class*="stMainBlockContainer"] {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
    }
    /* Hide Streamlit's empty top header */
    .stAppHeader,
    [class*="stAppHeader"],
    header[class*="st-"],
    .stApp > header {
        display: none !important;
        height: 0 !important;
    }
    /* Hide deploy toolbar */
    .stToolbar,
    [class*="stToolbar"],
    .stDecoration,
    [class*="stDecoration"] {
        display: none !important;
    }
    /* Smaller divider in sidebar */
    section[data-testid="stSidebar"] hr {
        margin: 0.6rem 0 !important;
    }
    /* Tighter caption */
    section[data-testid="stSidebar"] [data-testid="stCaption"] {
        font-size: 0.72rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #888 !important;
        margin: 0.4rem 0 0.3rem 0 !important;
        padding: 0 0.3rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- Sidebar -----------------
with st.sidebar:
    st.markdown('<div class="new-chat-btn">', unsafe_allow_html=True)
    if st.button("➕ New chat", use_container_width=True, key="new_chat_top"):
        start_new_conversation()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    st.caption("Conversations")
    convs = db.list_conversations(limit=50)
    if not convs:
        st.caption("No conversations yet.")
    else:
        for conv in convs:
            is_active = (conv["id"] == st.session_state.active_conversation_id)
            cols = st.columns([0.88, 0.12], gap="small")
            with cols[0]:
                wrapper = "active-conv" if is_active else ""
                st.markdown(f'<div class="{wrapper}">', unsafe_allow_html=True)
                if st.button(conv["title"], key=f"open_{conv['id']}",
                              use_container_width=True):
                    switch_conversation(conv["id"])
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with cols[1]:
                st.markdown('<div class="del-btn">', unsafe_allow_html=True)
                if st.button("🗑", key=f"del_{conv['id']}",
                              help="Delete this conversation"):
                    st.session_state.pending_delete = conv["id"]
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.pending_delete is not None:
        pd_id = st.session_state.pending_delete
        pd_conv = db.get_conversation(pd_id)
        if pd_conv:
            st.warning(f"Delete *{pd_conv['title']}*?")
            cc = st.columns(2)
            with cc[0]:
                if st.button("Yes, delete", key="confirm_delete",
                              use_container_width=True):
                    db.delete_conversation(pd_id)
                    if st.session_state.active_conversation_id == pd_id:
                        st.session_state.active_conversation_id = None
                    st.session_state.pending_delete = None
                    st.rerun()
            with cc[1]:
                if st.button("Cancel", key="cancel_delete",
                              use_container_width=True):
                    st.session_state.pending_delete = None
                    st.rerun()

    # API-key status — silent if loaded, only shows if missing
    if not os.getenv("OPENROUTER_API_KEY"):
        st.divider()
        st.error("⚠ OPENROUTER_API_KEY missing — add it to .env and restart")


# ---- Hardcoded configuration (was the Configuration expander) ----
model = "openai/gpt-4o-mini"
top_k = 4
temperature = 0.1
history_pairs = 8


# ----------------- Main pane -----------------
active_id = st.session_state.active_conversation_id

if active_id is None and not convs:
    start_new_conversation()
    active_id = st.session_state.active_conversation_id

if active_id:
    conv = db.get_conversation(active_id)
    if conv:
        st.markdown(f'<h2 class="conv-title">{conv["title"]}</h2>',
                    unsafe_allow_html=True)
    else:
        st.session_state.active_conversation_id = None
        st.rerun()
else:
    st.markdown('<h2 class="conv-title">IS 456:2000 — Reinforced Concrete RAG</h2>',
                unsafe_allow_html=True)
    st.caption("Click *New chat* to start, or pick a previous conversation "
               "from the sidebar.")

if active_id:
    messages = db.get_messages(active_id)
    for m in messages:
        with st.chat_message(m["role"]):
            st.markdown(fix_math_delimiters(m["content"]))
            if m["role"] == "assistant" and m.get("debug"):
                with st.expander("🔍 Retrieval debug"):
                    debug = m["debug"]
                    if debug.get("scores"):
                        st.write("**Retrieval scores:**")
                        for s, cid in debug["scores"]:
                            st.text(f"  {s:.3f}  {cid}")
                    if debug.get("lookups"):
                        st.write("**Deterministic lookups:**")
                        for label, val in debug["lookups"]:
                            st.text(f"  {label}: {val}")
                    if "model" in debug:
                        st.text(f"  Model: {debug['model']}")

query = st.chat_input("Ask about IS 456:2000 …", disabled=(active_id is None))

if query and active_id:
    api_key_present = bool(os.getenv("OPENROUTER_API_KEY"))
    if not api_key_present:
        st.error("Cannot send query — no OPENROUTER_API_KEY in .env.")
        st.stop()

    db.add_message(active_id, "user", query)

    with st.chat_message("user"):
        st.markdown(query)

    results = rag.search(query, top_k=top_k)
    top_score = results[0][0] if results else 0
    lookups = auto_detect_lookups(query)

    sources = build_sources_block(results)
    lookup_block = ""
    if lookups:
        lookup_block = "\n\nDETERMINISTIC LOOKUPS (use these values verbatim):\n"
        for label, val in lookups:
            lookup_block += f"- {label}: {val}\n"

    augmented_user_message = (
        f"SOURCES (top-{len(results)} retrieval, max score {top_score:.3f}):\n\n"
        f"{sources}{lookup_block}\n\n"
        f"USER QUESTION: {query}"
    )

    history = db.get_messages_for_llm(active_id, limit_pairs=history_pairs)
    if history and history[-1]["role"] == "user":
        history[-1] = {"role": "user", "content": augmented_user_message}
    else:
        history.append({"role": "user", "content": augmented_user_message})

    client = make_client()
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                answer = call_llm(client, model, SYSTEM_PROMPT,
                                   history, temperature=temperature)
            except Exception as e:
                answer = f"⚠ LLM call failed: `{e}`"
        st.markdown(fix_math_delimiters(answer))

        debug_data = {
            "scores": [(round(s, 3), c["id"]) for s, c in results],
            "lookups": [(label, str(val)) for label, val in lookups],
            "model": model,
            "top_score": round(top_score, 3),
            "history_pairs_sent": history_pairs,
        }
        with st.expander("🔍 Retrieval debug"):
            st.write("**Retrieval scores:**")
            for s, c in results:
                st.text(f"  {s:.3f}  [{c['content_type']:6s}] cl.{c['clause']:10s}  → {c['id']}")
            if lookups:
                st.write("**Deterministic lookups:**")
                for label, val in lookups:
                    st.text(f"  {label}: {val}")
            else:
                st.write("**Deterministic lookups:** (none auto-detected)")
            st.write(f"**Model:** `{model}`")
            st.write(f"**Top-1 score:** {top_score:.3f}")
            st.write(f"**History pairs sent:** {history_pairs}")
            if top_score < 0.30:
                st.warning("Top score is low — query may be outside the indexed material "
                            "(Sections 26, 38, 39, 40, 41 only).")

    db.add_message(active_id, "assistant", answer, debug=debug_data)
    st.rerun()