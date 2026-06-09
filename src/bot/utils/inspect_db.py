import asyncio
import sqlite3

DB_FILE = "bot.db"


async def inspect_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    print("--- Forward Queue Stats ---")
    cursor.execute("SELECT count(*) FROM forward_queue")
    print(f"Total items in forward_queue: {cursor.fetchone()[0]}")

    print("\n--- Duplicate Check in Queue ---")
    cursor.execute(
        "SELECT file_unique_id, target_chat_id, count(*) FROM forward_queue GROUP BY file_unique_id, target_chat_id HAVING count(*) > 1 LIMIT 20"
    )
    dupes = cursor.fetchall()
    if dupes:
        print("Found duplicate items in forward_queue (same file_unique_id for same target):")
        for d in dupes:
            print(f"  fuid: {d[0]}, target: {d[1]}, count: {d[2]}")
    else:
        print("No duplicates found in forward_queue.")

    print("\n--- Seen Table Stats ---")
    cursor.execute("SELECT count(*) FROM seen")
    print(f"Items in seen: {cursor.fetchone()[0]}")

    print("\n--- Forward Seen Table Stats ---")
    cursor.execute("SELECT count(*) FROM forward_seen")
    print(f"Items in forward_seen: {cursor.fetchone()[0]}")

    print("\n--- Sample Queue Items ---")
    cursor.execute("SELECT id, target_chat_id, media_type, file_unique_id, priority FROM forward_queue LIMIT 10")
    for row in cursor.fetchall():
        print(row)

    conn.close()


if __name__ == "__main__":
    asyncio.run(inspect_db())
