# Knowledge library & retrieval (RAG)

## Status: Sprint 8

The AI chat answers from a **reviewed** patient-education library and
shows the articles it used ("Sources" under the reply, linking to
`/learn/<id>`). Only APPROVED documents are ever searched or shown to
non-admins.

## Content and review

- Articles live in `data/knowledge/*.md` (front matter + Markdown, one
  file per language). See `data/knowledge/README.md` for the format.
- **The 12 starter articles (6 topics × EN/AR) are editorial drafts**,
  written to be general and cautious (no medicine names or doses), and
  **not clinically reviewed**. Locally, the seed approves them as
  "Development sample — not clinically reviewed"; that label is shown on
  every article page. A dermatologist must review and approve them
  before real use.
- Workflow: new or changed text enters as `pending_review` (indexed but
  not searchable). Approval needs a named reviewer (`reviewed_by`).
  Editing an approved article's text sends it back to review; text
  changes and approval can't happen in the same request.

```bash
cd backend
python -m app.rag.cli ingest                                   # load/refresh data/knowledge (pending review)
python -m app.rag.cli ingest --approve --reviewer "Dr Name"    # load and approve
python -m app.rag.cli reembed                                  # after changing the embedding model
python -m app.rag.cli search "brown patches after pregnancy"   # see what the chat would retrieve
```

Admins can also manage articles through the API (`/knowledge/documents`).

## Pipeline

```
article (.md) → front matter + Markdown → passages by heading (≤ ~900 chars)
             → embeddings (title + heading + text) → knowledge_chunks
```

- Documents are keyed by `slug`; unchanged files are skipped (content hash).
- Each passage stores its `heading`, `language`, `embedding` (1536-d,
  pgvector) and `embedding_model`.

## Search (`app/rag/retrieval.py`)

Hybrid, merged with Reciprocal Rank Fusion:

1. **Meaning:** cosine similarity on pgvector (HNSW index), only against
   vectors from the current embedding model.
2. **Keywords:** Postgres full-text search with the **Arabic** or
   **English** analyzer per passage (stemming, stop words). Query words
   are OR-ed; a word typed with a final ه is also searched with ة.

A passage is kept if its similarity clears the embedder's threshold,
**or** it matches at least two distinct query words and a quarter of
that threshold. Keywords rescue relevant passages the embeddings rank
low (common with Arabic word forms); a single shared word can't pull in
unrelated text. At most 2 passages per document; the patient's language
gets a small boost.

In the chat: the patient's latest message is searched (together with the
previous one when it's short, e.g. "about 6 months"); up to 4 passages
are given to the model as a numbered library in a separate developer
message; only citations pointing at passages actually given become
sources. Each reply stores which passages were retrieved and their
scores (`extra_data.retrieval`) for evaluation. Emergencies skip all of
this (no model call). If search fails, the chat answers without it.

## Embedders

| `AI_PROVIDER` | Embedder | Notes |
|---|---|---|
| `openai` | OpenAI, model from `OPENAI_EMBEDDING_MODEL` (required; e.g. `text-embedding-3-small`), 1536 dimensions | Understands meaning and works across English/Arabic |
| `demo` | Offline feature hashing of words and character n-grams, with a light Arabic stemmer | Development and tests only |

**Known limits of the demo embedder** (not of production): it matches
words, not meaning, and can't match across languages. For example, "I
have pimples on my chin, when should I see a doctor" finds nothing (the
acne text shares only "pimples"), and "laser hair removal" pulls in the
hair-loss article on the shared word "hair". Thresholds for the real
model (`OpenAIEmbedder.min_similarity = 0.35`) are a starting point to
tune with the evaluation set (Sprint 16).

## Not done yet

- Clinical review of the starter articles; more topics.
- Retrieval evaluation set (questions with expected articles) and
  threshold tuning against the real embedding model (Sprint 16).
- Streaming and per-sentence citations.
