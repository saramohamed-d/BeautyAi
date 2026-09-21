# Knowledge library (RAG source)

Patient-education articles the AI chat can quote, one Markdown file per
article and language (`<topic>.<en|ar>.md`). Loaded with:

```bash
cd backend
python -m app.rag.cli ingest ../data/knowledge                          # enters as pending_review
python -m app.rag.cli ingest ../data/knowledge --approve --reviewer "Dr Name, Dermatologist"
```

Only **approved** documents are ever searched. Editing an approved
article and re-ingesting it sends it back to review.

**Status of these files:** editorial drafts written for development.
They are general and deliberately cautious (no medicine names or doses),
but they have **not** been reviewed by a clinician. A dermatologist must
review and approve each one before real use. The local seed script loads
them as approved with the reviewer label "Development sample — not
clinically reviewed", which is shown on every article page.

Front matter keys: `slug` (unique), `title`, `language` (en|ar),
`source`, `url` (optional), `specialty`, `evidence_level`
(systematic_review | rct | cohort_study | expert_opinion |
official_guidance), `summary`, `version`.
