# IS 6403 RAG Dashboard

ChatGPT-style local dashboard for IS 6403:1981 with persistent conversations.

## What's new

- **Sidebar with conversation list** (like ChatGPT)
- **`+ New chat` button** to start fresh anytime
- **Click any past conversation** to load and continue it
- **Delete with confirmation** per conversation
- **In-session memory** — LLM sees full conversation history, so follow-ups
  like "what about phi=35?" work correctly
- **SQLite persistence** — close the browser, reopen later, conversations are
  still there

## Setup

    python3 -m venv venv
    source venv/bin/activate    # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    # Edit .env and add your OPENROUTER_API_KEY
    streamlit run app.py

Opens at `http://localhost:8501`.

## How memory works

The LLM receives, on every turn:
1. System prompt (rules, citation format)
2. Last N pairs of (user, assistant) from this conversation (default 8 pairs,
   configurable in sidebar)
3. Latest user turn augmented with freshly retrieved sources for THIS question

So follow-ups know context, but each question gets fresh authoritative sources.

The "history pairs sent to LLM" slider controls how much context goes back.
0 disables memory; 8 covers most cases.

## Database

Two tables in `chat.db`:
    conversations(id, title, created_at, updated_at)
    messages(id, conversation_id, role, content, debug_json, created_at)

When you migrate to PostgreSQL for the website, this same schema works — just
swap the sqlite3 calls in db.py for psycopg2.

To wipe all conversations: delete `chat.db`.

## Files

    .env                ← OpenRouter key
    app.py              ← the dashboard
    db.py               ← SQLite persistence (NEW)
    02_rag.py           ← retriever + lookups
    data/chunks.json    ← 22 indexed chunks
    data/figs/*.png     ← extracted figure images
    chat.db             ← created on first run

## Test sequence

1. Ask a question, get an answer with citations
2. Ask a follow-up like "what about phi=35?" — should understand context
3. Click `+ New chat`, ask something else
4. Click back to first conversation — all messages preserved
5. Close browser, restart `streamlit run app.py` — still there
