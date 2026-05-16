# IS 456 RAG Dashboard

ChatGPT-style local dashboard for IS 456:2000 (Plain and Reinforced Concrete —
Code of Practice). Built on OpenRouter — GPT-4o-mini by default.

## Coverage

**74 chunks** across IS 456 Sections 26, 38, 39, 40, 41:

| Section | Topic | Chunks |
|---|---|---|
| 26 | Reinforcement detailing (cover, bond, dev length, beams, columns) | 40 |
| 38 | Limit state of collapse — flexure | 5 |
| 39 | Limit state of collapse — compression | 8 |
| 40 | Shear | 13 |
| 41 | Torsion | 8 |

Breakdown by content type: 65 clauses, 5 tables, 2 graphs, 2 figures.

## Setup

    python3 -m venv venv
    source venv/bin/activate    # Windows: venv\Scripts\activate
    pip install -r requirements.txt

    # Edit .env and put your key after OPENROUTER_API_KEY=

    streamlit run app.py

Opens at http://localhost:8501

## What's included

### Retrieval
- TF-IDF cosine similarity over 74 chunks
- Clause/figure/table number boosts (regex)
- Content-type intent boost (chart/table/figure keywords)
- Parameter vocabulary boost (per-chunk hand-curated regex)
- Tag matching boost (uses the `tags` field from your schema)

### Deterministic numeric lookups
The dashboard automatically detects when a query has parameters matching one
of these and computes the answer in Python before the LLM sees it:

- **Table 19** — Design shear strength τ_c, interpolated by pt and grade
- **Table 20** — Maximum shear stress τ_c,max by grade
- **Table 38.1** — xu,max/d ratio by fy
- **Table 26.2.1.1** — Bond stress τ_bd, with the deformed-bar (×1.60) and
  compression (×1.25) multipliers per the clause note
- **Table cl. 40.2.1.1** — Slab depth factor k by overall depth
- **Fig 21** — Concrete stress at given strain (closed-form parabolic-rectangular)
- **Fig 23A** — Steel stress at given strain (calibrated piecewise-linear for
  cold-worked deformed bars)

The LLM is instructed to use these computed values verbatim. It explains the
result; Python does the arithmetic. This is the pattern you'd extend for the
vetting agent.

### Chat features
- Sidebar listing past conversations (most recent first)
- `+ New chat` button
- Click any past conversation to load it
- Delete with confirmation
- In-session memory: LLM sees the full conversation history
- SQLite persistence in `chat.db`

### Files

    .env                 ← OpenRouter API key
    app.py               ← Streamlit UI + prompt construction + lookups orchestration
    02_rag.py            ← Retriever + numeric lookups for IS 456
    db.py                ← SQLite persistence (conversations, messages)
    01_build_chunks.py   ← Merges the four uploaded JSON files into one chunks.json
    data/chunks.json     ← 74 merged chunks
    chat.db              ← Created on first run (conversation history)
    requirements.txt

## Notes

**All chunks are currently `status: "draft"`.** The retriever still surfaces
them (production mode would filter for `status: "production"`). Worth promoting
to production after you've reviewed them.

**The two graphs (Fig 21, Fig 23) have no image files** — `image_url` is null
in the source data. They're stored as closed-form curve definitions (Fig 21:
parabolic + plateau equations; Fig 23A: calibrated key points). Lookups work
without images; the dashboard will just show the caption text.

**Math rendering:** Streamlit only renders LaTeX in `$...$` or `$$...$$`
delimiters. The system prompt instructs the LLM accordingly, plus there's a
regex fallback in `fix_math_delimiters()` that catches `[ \frac{...} ]`-style
formatting and rewrites it.

## To wipe history

Delete `chat.db`. The schema will be recreated on next startup.

## When you grow

The schema fits cleanly into Postgres + pgvector when you move to a real
backend. Each chunk row becomes a database row with the same fields. The
retriever's `search()` signature stays identical; only its innards change from
TF-IDF + in-memory to vector similarity over Qdrant or pgvector.
