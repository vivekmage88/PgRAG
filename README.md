# Document RAG API — Postgres + pgvector

A retrieval-augmented generation service over PDF documents. Upload a PDF, ask questions in natural language, get answers grounded in the document with page-number citations.

Built on FastAPI and PostgreSQL with the pgvector extension — no separate vector database.

---

## Pipeline

**Ingestion**, once per document:

```
PDF → extract per page → clean → split heading → chunk (300 tokens, 50 overlap)
    → prepend heading → embed in batches → insert in one transaction
```

**Query**, per question:

```
question → answer cache → embed (cached) → cosine search → distance gate
         → build context → LLM → cache → answer with citations
```

| File | Responsibility |
|---|---|
| `ingest.py` | PDF to chunks. No network, no database. |
| `embed.py` | Text to vectors, batched. Network only. |
| `models.py` | `Document` and `Chunk` tables, with a `vector(1536)` column |
| `store.py` | Pair chunks with vectors, insert in one transaction |
| `retrieve.py` | Cosine search with distance threshold |
| `answer.py` | Context assembly, LLM call, answer cache |
| `cache.py` | Redis layer for embeddings and answers |
| `main.py` | FastAPI endpoints |

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/documents` | Upload and index a PDF |
| `GET` | `/documents` | List indexed documents |
| `DELETE` | `/documents/{id}` | Remove a document and its chunks |
| `POST` | `/ask` | Ask a question, get a cited answer |

```bash
curl -X POST http://127.0.0.1:8000/documents \
  -F "file=@fastapi.pdf" -F "title=FastAPI Reference"

curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "how does FastAPI work?"}'
```

```json
{
  "answer": "FastAPI works by using standard Python type hints to define the API contract through the function signatures of endpoints... (p1)",
  "sources": [
    { "page": 1, "heading": "FastAPI Overview and Core Concepts", "distance": 0.378 },
    { "page": 2, "heading": "Installing FastAPI and Running the First Application", "distance": 0.453 }
  ]
}
```

`document_id` is optional on `/ask`. Omit it to search every indexed document.

---

## Setup

Requires Python 3.12, PostgreSQL 17 with pgvector, Redis, and an OpenAI API key.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

createdb pgrag
psql pgrag -c "CREATE EXTENSION vector;"

cp .env.example .env
alembic upgrade head

brew services start redis
uvicorn main:app --reload
```

---

## Design decisions

### Postgres instead of a dedicated vector database

The chunks live in the same database as everything else, which buys three things a separate vector store cannot.

**Referential integrity.** `documents` and `chunks` are related by a foreign key with `ON DELETE CASCADE`. Deleting a document removes its 44 chunks in the same transaction, enforced by the database. Across two systems that is two operations with a window where one can succeed and the other fail.

**Listing is a query, not a scan.** `GET /documents` is `SELECT * FROM documents`. With chunks-only storage it means loading every chunk's metadata and grouping it in application code.

**One datastore.** Transactions, backups, replication, connection pooling and monitoring already exist. A dedicated vector database earns its place at a scale this is not near.

### Chunking: 300 tokens with 50 overlap

**Tokens, not words or characters**, because tokens are what the embedding API limits and bills. Character counts do not map cleanly onto either.

**300 rather than a whole page**, because a page can cover several subtopics and embedding them together averages the meaning into something that matches everything weakly.

**50 tokens of overlap** so a sentence spanning a chunk boundary appears whole in at least one chunk. Without it, a claim can end in one chunk and its explanation begin in the next, leaving neither retrievable. The cost is roughly 17% more chunks and tokens.

The text is encoded to token IDs, sliced by index, and decoded back — the only way to cut at exact token counts.

### Contextual header on every chunk

Each chunk is prefixed with its page's section heading before embedding. The second chunk of a page otherwise begins mid-sentence and carries no signal about its topic. Measured at roughly 6 points of precision@1 in an earlier version of this pipeline.

### Chunking loops, embedding batches

Extraction and chunking are local CPU work and run one page at a time. Embedding is a network round trip costing ~200ms regardless of payload size, so chunks are collected into one list and sent 50 at a time. 44 chunks is one API call, not 44.

Chunks and vectors are matched **by list position**, so the order must never change between building the text list and receiving the vectors. `save_document` asserts the two lengths match before inserting anything.

### Distance threshold before the LLM call

Vector search always returns `k` rows. There is no empty result and no "no match" signal — ask for five and you get the five nearest, however far away. Without a threshold, an out-of-domain question returns irrelevant chunks and the model answers from them fluently.

When nothing passes the gate, the endpoint returns a fallback and **the LLM is never called**: no cost, no latency, no generation from empty context.

Measured on this corpus with cosine distance:

| Question | Best distance |
|---|---|
| "what is FastAPI" | 0.311 |
| "what is the capital of France" | 0.899 |

Threshold set at 0.6.

### Two caches, different lifetimes

| Cache | Depends on | TTL | Saves |
|---|---|---|---|
| Embedding | Question text, model | 7 days | One API call |
| Answer | Question, k, threshold, document | 1 hour | Whole pipeline |

An embedding is a pure function of text and model, so nothing in the system can invalidate it. An answer depends on what is currently indexed, so re-ingesting a document makes cached answers potentially wrong. Cache lifetime matches how fast the underlying data goes stale.

The answer cache key includes every parameter that affects the output. Keying on the question alone would serve a five-chunk answer to a request that asked for one.

Measured: **~2.4s uncached, sub-millisecond on a cache hit.**

### Caches fail open

Every Redis call is wrapped and returns a cache miss on failure. Verified by stopping Redis: both requests still returned correct answers. A cache is an optimisation, never a dependency.

One finding from that test — latency rose to **19s per request**, worse than having no cache at all, because every call waits out its 2-second connection timeout and there are four cache calls per request. The fix is a circuit breaker that stops attempting Redis after repeated failures.

### Validation belongs in the handler

`search` and `answer_question` take a session and plain arguments and raise no HTTP exceptions. The document-exists check and its 404 live in the endpoint. That keeps the retrieval layer usable from a script, a worker, or an evaluation harness without importing a web framework — which is how every stage of this project was tested during development.

