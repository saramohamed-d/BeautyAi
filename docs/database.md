# Database

No models exist yet. This document will be populated in **Sprint 1** with:
- Entity-relationship overview
- Table definitions (patients, doctors, clinics, appointments, knowledge_documents, etc.)
- Indexing strategy
- Migration workflow

Sprint 0 only establishes the async SQLAlchemy engine/session
(`backend/app/db/session.py`) and the Alembic wiring
(`backend/alembic/env.py`), both pointed at PostgreSQL with the pgvector
extension image (`pgvector/pgvector:pg16`), used starting Sprint 8.
