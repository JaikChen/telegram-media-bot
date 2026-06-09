import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.bot.data.database import db_manager


async def check_queues():
    db = await db_manager.get_db()
    async with db.execute("SELECT count(*) FROM forward_queue") as cursor:
        fq_count = (await cursor.fetchone())[0]

    async with db.execute("SELECT count(*) FROM dead_letter_queue") as cursor:
        dlq_count = (await cursor.fetchone())[0]

    print(f"Forward Queue Count: {fq_count}")
    print(f"Dead Letter Queue Count: {dlq_count}")

    if dlq_count > 0:
        print("\n--- Recent DLQ Items ---")
        async with db.execute("SELECT id, target_chat_id, reason FROM dead_letter_queue LIMIT 5") as cursor:
            async for row in cursor:
                print(row)


if __name__ == "__main__":
    asyncio.run(check_queues())
