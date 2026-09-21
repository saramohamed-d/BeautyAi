"""
Sprint 8: knowledge library — chunking, ingestion, review workflow,
hybrid search and its use in the chat.

Each test uses its own made-up condition name (see _word), so it can't
depend on, or collide with, documents from other tests or earlier runs.
"""

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.agents.llm import get_llm
from tests.ai_helpers import draft
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.knowledge import KnowledgeChunk
from app.rag.chunking import MAX_CHARS, chunk_markdown, parse_front_matter
from app.rag.embeddings import DemoEmbedder
from app.rag.ingest import ingest_directory
from tests.factories import register_patient

REVIEWER = "Dr Test Reviewer, Dermatologist"


def _slug() -> str:
    return f"test-{uuid.uuid4().hex[:10]}"


def _word() -> str:
    """A made-up condition name unique to one test, so earlier runs' documents can't match."""
    return "zorbex" + "".join(chr(ord("a") + int(c, 16) % 26) for c in uuid.uuid4().hex[:6])


def _doc(word: str, **overrides) -> dict:
    body = (
        f"## What {word} rash is\n\n"
        f"{word.capitalize()} rash is a made-up skin condition used only in tests. It causes itchy {word} patches on the arms.\n\n"
        f"## When to see a dermatologist\n\nSee a dermatologist if {word} patches spread or bleed."
    )
    return {"slug": _slug(), "title": f"{word.capitalize()} rash", "language": "en", "body": body, "source": "Test source", **overrides}


async def _create(admin_client: AsyncClient, word: str, approve: bool = True, **overrides) -> dict:
    created = await admin_client.post("/api/v1/knowledge/documents", json=_doc(word, **overrides))
    assert created.status_code == 201, created.text
    document = created.json()
    assert document["status"] == "pending_review"
    if approve:
        resp = await admin_client.patch(
            f"/api/v1/knowledge/documents/{document['id']}", json={"status": "approved", "reviewed_by": REVIEWER}
        )
        assert resp.status_code == 200, resp.text
        document = resp.json()
    return document


async def _search_ids(client: AsyncClient, q: str, **params) -> list[str]:
    resp = await client.get("/api/v1/knowledge/search", params={"q": q, **params})
    assert resp.status_code == 200, resp.text
    return [hit["document_id"] for hit in resp.json()]


# --- Chunking -----------------------------------------------------------------


def test_front_matter_parsing() -> None:
    meta, body = parse_front_matter("---\nslug: a-b\ntitle: Hello: world\n---\n\n# Body")
    assert meta == {"slug": "a-b", "title": "Hello: world"} and body == "# Body"
    with pytest.raises(ValueError):
        parse_front_matter("no front matter")
    with pytest.raises(ValueError):
        parse_front_matter("---\nslug: x\n")


def test_chunks_follow_headings_and_size_limit() -> None:
    long_paragraph = " ".join(["This sentence is about zorbex care."] * 60)
    passages = chunk_markdown(f"Intro text.\n\n## First\n\nOne.\n\nTwo.\n\n## Second\n\n{long_paragraph}")
    assert passages[0].heading is None and passages[0].content == "Intro text."
    assert passages[1].heading == "First" and passages[1].content == "One.\n\nTwo."
    second = [p for p in passages if p.heading == "Second"]
    assert len(second) > 1 and all(len(p.content) <= MAX_CHARS for p in second)


async def test_directory_ingestion_skips_unchanged_readme_and_reports_bad_files(tmp_path: Path) -> None:
    slug = _slug()
    (tmp_path / "README.md").write_text("# not an article")
    (tmp_path / "good.md").write_text(f"---\nslug: {slug}\ntitle: Zorbex guide\nlanguage: en\nsource: Test\n---\n\n## Part\n\nZorbex text.")
    (tmp_path / "bad.md").write_text("---\ntitle: Missing slug\n---\nText")
    embedder = DemoEmbedder()
    async with AsyncSessionLocal() as db:
        first = await ingest_directory(db, tmp_path, embedder)
        second = await ingest_directory(db, tmp_path, embedder)
    assert first["created"] == [slug] and len(first["failed"]) == 1
    assert second["unchanged"] == [slug] and second["created"] == []


# --- Review workflow ------------------------------------------------------------------


async def test_only_approved_documents_are_searchable_and_visible(client: AsyncClient, admin_client: AsyncClient) -> None:
    word = _word()
    pending = await _create(admin_client, word, approve=False)
    assert pending["id"] not in await _search_ids(client, f"{word} rash itchy patches")
    assert (await client.get(f"/api/v1/knowledge/documents/{pending['id']}")).status_code == 404
    assert (await admin_client.get(f"/api/v1/knowledge/documents/{pending['id']}")).status_code == 200
    listed = (await client.get("/api/v1/knowledge/documents?page_size=100")).json()["items"]
    assert pending["id"] not in {d["id"] for d in listed}

    other = _word()
    approved = await _create(admin_client, other)
    assert approved["reviewed_by"] == REVIEWER and approved["last_reviewed"]
    assert approved["id"] in await _search_ids(client, f"{other} rash itchy patches")
    assert (await client.get(f"/api/v1/knowledge/documents/{approved['id']}")).json()["body"].startswith(f"## What {other}")


async def test_approval_requires_a_named_reviewer(admin_client: AsyncClient) -> None:
    document = await _create(admin_client, _word(), approve=False)
    resp = await admin_client.patch(f"/api/v1/knowledge/documents/{document['id']}", json={"status": "approved"})
    assert resp.status_code == 422


async def test_editing_text_sends_a_document_back_to_review(client: AsyncClient, admin_client: AsyncClient) -> None:
    word = _word()
    document = await _create(admin_client, word)
    assert document["id"] in await _search_ids(client, f"{word} rash itchy patches")
    edited = await admin_client.patch(
        f"/api/v1/knowledge/documents/{document['id']}",
        json={"body": document["body"] + f"\n\n{word} update: new paragraph for review."},
    )
    assert edited.json()["status"] == "pending_review" and edited.json()["reviewed_by"] is None
    assert document["id"] not in await _search_ids(client, f"{word} rash itchy patches")

    both = await admin_client.patch(
        f"/api/v1/knowledge/documents/{document['id']}",
        json={"body": document["body"] + " more", "status": "approved", "reviewed_by": REVIEWER},
    )
    assert both.status_code == 422  # text change and approval must be separate steps


async def test_archived_documents_leave_search(client: AsyncClient, admin_client: AsyncClient) -> None:
    word = _word()
    document = await _create(admin_client, word)
    assert document["id"] in await _search_ids(client, f"{word} rash itchy patches")
    await admin_client.patch(f"/api/v1/knowledge/documents/{document['id']}", json={"status": "archived"})
    assert document["id"] not in await _search_ids(client, f"{word} rash itchy patches")


async def test_only_admins_manage_documents(client: AsyncClient, admin_client: AsyncClient) -> None:
    patient = await register_patient(client)
    assert (await client.post("/api/v1/knowledge/documents", json=_doc(_word()), headers=patient["headers"])).status_code == 403
    assert (await client.post("/api/v1/knowledge/documents", json=_doc(_word()))).status_code == 401
    existing = await _create(admin_client, _word(), approve=False)
    duplicate = await admin_client.post("/api/v1/knowledge/documents", json=_doc(_word(), slug=existing["slug"]))
    assert duplicate.status_code == 409


# --- Search behaviour ---------------------------------------------------------------------


async def test_arabic_keyword_search_with_stemming(client: AsyncClient, admin_client: AsyncClient) -> None:
    # A made-up Arabic word unique to this run.
    word = "زورب" + "".join("بتثجحخدذرزسشصضطظعغفقكلمنهوي"[int(c, 16)] for c in uuid.uuid4().hex[:4])
    body = f"## ما هو {word}\n\n{word} حالة جلدية تجريبية تسبب بقع حمراء على الذراعين عند الأطفال.\n\n## العلاج\n\nاستشيري طبيب الجلدية."
    document = await _create(admin_client, _word(), language="ar", title=word, body=body)
    # Different word forms than the text: "والبقع" (with prefixes), "الذراع".
    assert document["id"] in await _search_ids(client, f"{word} والبقع في الذراع", language="ar")


async def test_single_shared_common_word_does_not_match(client: AsyncClient, admin_client: AsyncClient) -> None:
    word = _word()
    document = await _create(admin_client, word)
    assert document["id"] in await _search_ids(client, f"{word} rash on my arms")  # positive control
    assert document["id"] not in await _search_ids(client, "please tell me about arms")


async def test_vectors_from_another_embedding_model_are_ignored(client: AsyncClient, admin_client: AsyncClient) -> None:
    word = _word()
    document = await _create(admin_client, word)
    assert document["id"] in await _search_ids(client, f"{word} rash itchy patches")
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(KnowledgeChunk)
            .where(KnowledgeChunk.knowledge_document_id == uuid.UUID(document["id"]))
            .values(embedding_model="some-older-model")
        )
        await db.commit()
    assert document["id"] not in await _search_ids(client, f"{word} rash itchy patches")


# --- Chat integration ------------------------------------------------------------------------


class CitingLLM:
    name, model = "scripted", "scripted-1"

    def __init__(self, cite: list[int]) -> None:
        self.cite, self.references = cite, None

    async def respond(self, *, instructions, history, references, consultation, user_ref):
        self.references = references
        return draft("Here is some general guidance.", cited_sources=self.cite, concern="other")


@pytest.fixture
def citing_llm() -> Iterator[CitingLLM]:
    llm = CitingLLM(cite=[1, 9])  # 9 doesn't exist and must be dropped
    app.dependency_overrides[get_llm] = lambda: llm
    yield llm
    app.dependency_overrides.pop(get_llm, None)


async def test_chat_uses_approved_passages_and_returns_valid_sources(
    client: AsyncClient, admin_client: AsyncClient, citing_llm: CitingLLM
) -> None:
    word = _word()
    approved = await _create(admin_client, word)
    pending = await _create(admin_client, word, approve=False)
    patient = await register_patient(client)
    conversation = (await client.post("/api/v1/conversations", headers=patient["headers"], json={"accept_ai_terms": True})).json()

    resp = await client.post(
        f"/api/v1/conversations/{conversation['id']}/chat",
        headers=patient["headers"],
        json={"content": f"I have itchy {word} rash patches on my arms"},
    )
    body = resp.json()
    given = {str(r.document_id) for r in citing_llm.references}
    assert approved["id"] in given and pending["id"] not in given
    assert body["sources"] == [
        {"document_id": str(citing_llm.references[0].document_id), "title": citing_llm.references[0].title,
         "heading": citing_llm.references[0].heading, "language": "en"}
    ]
    extra = body["assistant_message"]["extra_data"]
    assert extra["sources"] == body["sources"]
    assert len(extra["retrieval"]) == len(citing_llm.references)  # what the model saw, for evaluation


async def test_short_follow_up_is_searched_with_the_previous_message(
    client: AsyncClient, admin_client: AsyncClient, citing_llm: CitingLLM
) -> None:
    word = _word()
    approved = await _create(admin_client, word)
    patient = await register_patient(client)
    conversation = (await client.post("/api/v1/conversations", headers=patient["headers"], json={"accept_ai_terms": True})).json()
    path = f"/api/v1/conversations/{conversation['id']}/chat"
    await client.post(path, headers=patient["headers"], json={"content": f"I have itchy {word} rash patches on my arms"})
    await client.post(path, headers=patient["headers"], json={"content": "about two weeks"})
    assert approved["id"] in {str(r.document_id) for r in citing_llm.references}
