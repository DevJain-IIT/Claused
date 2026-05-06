"""
Streamlit dashboard for the IS 6403:1981 RAG.

ChatGPT-style UX:
  - Sidebar lists past conversations (most recent first)
  - "+ New chat" button starts a fresh conversation
  - Click any conversation to load it
  - Delete button per conversation
  - Each LLM call sees the full conversation history (in-session memory)
  - Everything persists in chat.db (SQLite)

Run:
    pip install -r requirements.txt
    cp .env.example .env  # then add OPENROUTER_API_KEY
    streamlit run app.py
"""

import os
import re
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# Load .env
load_dotenv(Path(__file__).parent / ".env")

# Local imports
sys.path.insert(0, str(Path(__file__).parent))
from importlib import import_module
rag = import_module("02_rag")
import db


# Initialise database on every startup (idempotent)
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
# Prompt construction
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a structural engineering assistant for IS 6403:1981
(Indian Standard — Determination of Bearing Capacity of Shallow Foundations).

Rules you must follow:
1. Answer using ONLY the SOURCES provided in the latest user message. Do not use
   your training-data knowledge of IS codes — if it's not in the sources, say so.
2. Every factual claim must cite as [IS 6403:1981 cl. X.Y, p. Z].
3. If DETERMINISTIC LOOKUPS are provided, use those numerical values verbatim.
   Do not recompute or approximate.
4. If a graph chunk is flagged with placeholder digitisation, say so — tell the
   user the value is approximate and the curve needs WebPlotDigitizer-quality
   re-digitisation for production use.
5. If retrieval scores are low (top score < 0.30) or if no source addresses the
   question, say so plainly rather than guessing.
6. Keep answers concise and engineering-focused. Show working when interpolating
   table values. Use units consistently.
7. MATH FORMATTING: Streamlit renders math only when wrapped in $...$ (inline)
   or $$...$$ (display block). Always use these delimiters — never use square
   brackets [ ... ], \\( ... \\), or \\[ ... \\] for math.
8. CONVERSATIONAL CONTEXT: You are seeing the full conversation history. Use it
   for follow-up questions ("what about phi=35?", "give me an example") — but
   each new turn still has its own SOURCES section that's the authoritative
   ground truth. Don't trust earlier-turn assistant answers as a source — only
   the SOURCES blocks in user messages."""


def build_sources_block(retrieved):
    blocks = []
    for rank, (score, c) in enumerate(retrieved, 1):
        cite = f"IS 6403:1981 cl. {c['clause']}, p. {c['page']}"
        if c["content_type"] == "clause":
            b = f"[Source {rank} — {cite}]\n{c['title']}\n{c['text']}"
            if c.get("formula_latex"):
                b += f"\nFormula (LaTeX): {c['formula_latex']}"
        elif c["content_type"] == "table":
            rows = "\n".join("| " + " | ".join(r) + " |" for r in c["rows"])
            b = (f"[Source {rank} — {cite}]\nTable {c['table_number']}: "
                 f"{c['caption']}\n| {' | '.join(c['headers'])} |\n{rows}")
            if c.get("note"):
                b += f"\nNote: {c['note']}"
        else:
            b = f"[Source {rank} — {cite}]\n{c['nl_caption']}"
        blocks.append(b)
    return "\n\n".join(blocks)


def auto_detect_lookups(query: str):
    out = []
    ql = query.lower()
    phi = re.search(r"(?:phi|φ)\s*[=:]?\s*(\d+(?:\.\d+)?)", ql)
    asks_table1 = any(t in ql for t in
                      ["nc", "nq", "ngamma", "n gamma", "n_gamma",
                       "bearing capacity factor", "bearing factor"])
    if phi and asks_table1:
        out.append(("Table 1 (bearing capacity factors)",
                    rag.lookup_table1(float(phi.group(1)))))
    asks_N = phi and any(t in ql for t in
                          ["spt", "n value", "penetration resistance", "blow"])
    if asks_N:
        out.append(("Fig 1 forward (phi → N)",
                    rag.lookup_fig1_N_from_phi(float(phi.group(1)))))
    n_val = re.search(r"\bn\s*[=:]?\s*(\d+(?:\.\d+)?)", ql)
    asks_phi = (n_val and not phi
                and any(t in ql for t in ["phi", "φ", "friction angle"]))
    if asks_phi:
        out.append(("Fig 1 inverse (N → phi)",
                    rag.lookup_fig1_phi_from_N(float(n_val.group(1)))))
    c_match = re.search(r"c1\s*/\s*c2\s*[=:]?\s*(\d+(?:\.\d+)?)", ql)
    db_match = re.search(r"d\s*/\s*b\s*[=:]?\s*(\d+(?:\.\d+)?)", ql)
    if c_match and db_match:
        out.append(("Fig 3 (layered cohesive Nc)",
                    rag.lookup_fig3_Nc(float(c_match.group(1)),
                                        float(db_match.group(1)))))
    return out


def call_llm(client, model, system_prompt, conversation_messages, temperature=0.2):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            *conversation_messages,
        ],
        temperature=temperature,
        max_tokens=1024,
        extra_headers={
            "HTTP-Referer": "http://localhost:8501",
            "X-Title": "IS 6403 RAG Dashboard",
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
# Session state init
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
st.set_page_config(page_title="IS 6403 RAG", layout="wide",
                   initial_sidebar_state="expanded")

# Light CSS for ChatGPT-ish look
st.markdown("""
<style>
    section[data-testid="stSidebar"] .stButton > button {
        text-align: left;
        justify-content: flex-start;
        white-space: normal;
        height: auto;
        padding: 0.5rem 0.75rem;
        line-height: 1.3;
    }
    .active-conv > button {
        background-color: rgba(120, 120, 220, 0.15) !important;
        font-weight: 600;
    }
    .new-chat-btn > button {
        background-color: #2b2d31;
        color: white;
        border: 1px solid #3a3d44;
    }
    .new-chat-btn > button:hover {
        background-color: #3a3d44;
    }
</style>
""", unsafe_allow_html=True)

init_session()

# ---- Sidebar ----
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
            cols = st.columns([0.85, 0.15], gap="small")
            with cols[0]:
                wrapper_class = "active-conv" if is_active else ""
                st.markdown(f'<div class="{wrapper_class}">', unsafe_allow_html=True)
                if st.button(conv["title"], key=f"open_{conv['id']}",
                              use_container_width=True):
                    switch_conversation(conv["id"])
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with cols[1]:
                if st.button("✕", key=f"del_{conv['id']}",
                              help="Delete this conversation"):
                    st.session_state.pending_delete = conv["id"]
                    st.rerun()

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

    st.divider()

    with st.expander("⚙ Configuration"):
        api_key_present = bool(os.getenv("OPENROUTER_API_KEY"))
        if api_key_present:
            st.success("OPENROUTER_API_KEY loaded")
        else:
            st.error("OPENROUTER_API_KEY missing — add it to .env")

        model = st.selectbox("Model", AVAILABLE_MODELS, index=0,
                              key="model_select")
        top_k = st.slider("Retrieval top-k", 2, 8, 4, key="topk_slider")
        temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.1,
                                  key="temp_slider")
        history_pairs = st.slider("History pairs sent to LLM", 0, 16, 8,
                                    help="0 disables in-session memory; "
                                         "higher = more context, more tokens",
                                    key="hist_slider")

    with st.expander("📚 RAG index"):
        st.metric("Chunks", len(rag.chunks))
        by_type = {}
        for c in rag.chunks:
            by_type[c["content_type"]] = by_type.get(c["content_type"], 0) + 1
        st.write(by_type)


# ---- Main pane ----
active_id = st.session_state.active_conversation_id

if active_id is None and not convs:
    start_new_conversation()
    active_id = st.session_state.active_conversation_id

if active_id:
    conv = db.get_conversation(active_id)
    if conv:
        st.title(conv["title"])
        st.caption(f"IS 6403:1981 RAG · model: `{model}` · "
                    f"history pairs: {history_pairs}")
    else:
        st.session_state.active_conversation_id = None
        st.rerun()
else:
    st.title("IS 6403:1981 — Bearing Capacity RAG")
    st.caption("Click *New chat* to start, or pick a previous conversation "
                "from the sidebar.")

# Render conversation
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

# Input
query = st.chat_input("Ask about IS 6403:1981 …",
                       disabled=(active_id is None))

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
        with st.spinner(f"Calling {model}…"):
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
                st.text(f"  {s:.3f}  [{c['content_type']:6s}] cl.{c['clause']:8s}  → {c['id']}")
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
                st.warning("Top score is low — query may be outside the indexed material.")

    db.add_message(active_id, "assistant", answer, debug=debug_data)
    st.rerun()
