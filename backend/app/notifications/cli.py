"""
The sender (Sprint 15).

    python -m app.notifications.cli run          # send everything due
    python -m app.notifications.cli run --once   # same, then exit (default)
    python -m app.notifications.cli pending      # show what's waiting

Run it from cron (or a container's scheduler) every few minutes. It's
safe to run concurrently with itself: each message is claimed and
committed one at a time, and `dedupe_key` stops duplicates.
"""

import argparse
import asyncio

from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionLocal
from app.notifications.providers import get_notifier
from app.services import notification_service

logger = get_logger(__name__)


async def run_once() -> dict:
    async with AsyncSessionLocal() as db:
        return await notification_service.dispatch_due(db, get_notifier())


async def show_pending() -> None:
    async with AsyncSessionLocal() as db:
        rows = await notification_service.due(db, limit=50)
        print(f"{len(rows)} due now")
        for row in rows:
            print(f"  {row.scheduled_for:%Y-%m-%d %H:%M}  {row.channel.value:9} {row.template:22} -> {row.recipient}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send due notifications")
    parser.add_argument("command", choices=["run", "pending"])
    parser.add_argument("--once", action="store_true", help="kept for clarity; the sender always exits after one pass")
    args = parser.parse_args()

    configure_logging()
    if args.command == "pending":
        asyncio.run(show_pending())
        return
    result = asyncio.run(run_once())
    print(f"sent {result['sent']}, failed {result['failed']}")


if __name__ == "__main__":
    main()
