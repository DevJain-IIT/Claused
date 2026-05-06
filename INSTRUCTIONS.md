# IS 6403 RAG — test harness

You're being given a small RAG (retrieval-augmented generation) system built
over IS 6403:1981 (Code of Practice for Determination of Bearing Capacity of
Shallow Foundations), covering Sections 5 and 6. Your job is to answer the
user's engineering questions by **invoking this RAG** rather than relying on
your training-data knowledge of IS 6403.

## What's here

```
is6403_rag/
├── INSTRUCTIONS.md         ← this file
├── query.py                ← CLI: run this for every question
├── 02_rag.py               ← RAG library (retrieval + numeric lookups)
├── 01_build_chunks.py      ← (only needed if rebuilding chunks)
├── 03_test.py              ← test battery (optional)
└── data/
    ├── chunks.json         ← 22 indexed chunks (clauses, tables, graphs, figure)
    └── fig*.png            ← extracted figure images
```

## Protocol — follow this strictly

For **every** engineering question the user asks:

1. **Run the retriever first.** From within the `is6403_rag/` directory:
   ```bash
   python3 query.py "the user's question goes here in quotes"
   ```
   This prints (a) top-4 retrieval results with scores and (b) the full content
   of the top-1 chunk. For numeric questions about Table 1 or Fig 1 / Fig 3,
   it also runs the digitised lookup and prints the result.

2. **Show the user what retrieval returned** — the score table at minimum.
   Don't hide the retrieval step. The user is testing whether retrieval works,
   so they need to see what came back.

3. **Answer using only the retrieved chunks** — the clause text, table values,
   figure captions, and numeric lookups that `query.py` returned. Do not
   supplement from your own knowledge of IS 6403, even if you "remember"
   something relevant. If retrieval missed something obvious, **say so** —
   that's a failure mode the user wants to see, not paper over.

4. **Cite clause and page numbers** as they appear in the retrieved chunks
   (e.g., "IS 6403:1981, cl. 5.1.2.2, p. 9").

5. If the user asks something not in the indexed material (e.g., a pile-foundation
   question, since this RAG only covers shallow foundations), say so plainly
   and don't try to answer from training data.

## What's *in* this RAG

22 chunks covering IS 6403 Sections 5–6:

- **14 clauses**: 5.0.1 (eccentricity), 5.1.1 (strip footing formula),
  5.1.2 (modified formula), 5.1.2.2 (depth factors), 5.1.2.3 (inclination),
  5.1.2.4 (water table), 5.2.2 (SPT method), 5.2.3 (cone method),
  5.3.1.1 (cohesive homogeneous), 5.3.1.2 (cohesion from cone),
  5.3.2 (two-layered), 5.3.3 (desiccated), 6.1 (allowable), 6.1.1 (safe pressure)

- **4 tables**: Table 1 (bearing capacity factors Nc, Nq, Nγ vs φ),
  Table 2 (shape factors), Table 3 (relative density → method),
  Table 4 (desiccated soil data)

- **3 digitised graphs** (numeric lookup supported):
  Fig 1 (φ vs SPT N), Fig 2 (cone test chart — image only),
  Fig 3 (Nc for layered cohesive soil, with hand-digitised curves)

- **1 figure** (image + caption): Fig 4 (desiccated soil schematic)

## What's *NOT* in this RAG

- Sections 1–4 of IS 6403 (scope, terminology, symbols, general)
- Anything outside IS 6403 (other IS codes, deep foundations, etc.)
- Detailed calculation examples / worked problems

If the user asks about these, say so rather than guessing.

## Caveats to mention if relevant

- **Digitised curves are hand-read** from the printed figures (~±2 N on Fig 1,
  ~±0.2 on Fig 3 Nc). Good enough to demo the lookup, not production-grade.
- **Amendment 1 (1984)** corrections are incorporated where applicable
  (Table 4 uses 4λB/q_d not 8λB/q_d; Fig 3 axis label is noted).
- **TF-IDF retriever** is a stand-in for the production embedder. Some queries
  (especially short ones with technical symbols like "Nc") will retrieve
  imperfectly — surface this when it happens.
