import os
import aiosqlite

# Absolute by default so the SQLite file location never depends on the process
# CWD / WORKDIR (it must land on the mounted volume, not the ephemeral layer).
DB_PATH = os.getenv("DB_PATH", "/app/data/bot.db")


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS group_albums (
                group_id  TEXT PRIMARY KEY,
                group_name TEXT NOT NULL,
                album_id  TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def get_album_id(group_id: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT album_id FROM group_albums WHERE group_id = ?", (group_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def save_group_album(group_id: str, group_name: str, album_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO group_albums (group_id, group_name, album_id) VALUES (?, ?, ?)",
            (group_id, group_name, album_id),
        )
        await db.commit()
