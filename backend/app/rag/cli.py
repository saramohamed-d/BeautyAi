"""
Knowledge base commands.

    python -m app.rag.cli ingest [DIR] [--approve --reviewer "Dr Name"]
    python -m app.rag.cli reembed
    python -m app.rag.cli search "my question" [--language ar]

`ingest` loads Markdown articles (default: the repo's data/knowledge/).
Without --approve they enter as pending_review and are not searchable
until an admin approves them. `reembed` refreshes vectors after changing
OPENAI_EMBEDDING_MODEL. `search` shows what the chat would retrieve.
"""

import argparse
import asyncio
from pathlib import Path

from app.db.session import AsyncSessionLocal
from app.rag.embeddings import get_embedder
from app.rag.ingest import default_knowledge_dir, ingest_directory, reembed_all
from app.rag.retrieval import search


async def _run(args: argparse.Namespace) -> None:
    embedder = get_embedder()
    async with AsyncSessionLocal() as db:
        if args.command == "ingest":
            directory = Path(args.directory) if args.directory else default_knowledge_dir()
            report = await ingest_directory(db, directory, embedder, approve_as=args.reviewer if args.approve else None)
            for outcome, items in report.items():
                print(f"{outcome:>9}: {len(items)}" + (f"  {', '.join(items)}" if items and outcome != "unchanged" else ""))
            if not args.approve:
                print("New or changed documents are pending review and not searchable until approved.")
        elif args.command == "reembed":
            print(f"Re-embedded {await reembed_all(db, embedder)} passages with {embedder.model}.")
        else:
            for ref in await search(db, args.query, embedder, language=args.language, limit=args.limit):
                print(f"{ref.score:.4f}  sim={ref.similarity:.3f}  [{ref.language}] {ref.title} — {ref.heading}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest")
    ingest.add_argument("directory", nargs="?")
    ingest.add_argument("--approve", action="store_true", help="approve after loading (requires --reviewer)")
    ingest.add_argument("--reviewer", help="name and role of the clinician who reviewed the content")
    commands.add_parser("reembed")
    find = commands.add_parser("search")
    find.add_argument("query")
    find.add_argument("--language", choices=["en", "ar"])
    find.add_argument("--limit", type=int, default=4)
    args = parser.parse_args()
    if args.command == "ingest" and args.approve and not (args.reviewer or "").strip():
        parser.error("--approve requires --reviewer")
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
