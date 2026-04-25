import aiosqlite
import hashlib
import json
import asyncio
from app.database import DATABASE_URL

_locks: dict[str, asyncio.Lock] = {}

def hash_payload(payload: dict) -> str:
    dumped_payload = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(dumped_payload).hexdigest()

async def get_lock(key: str) -> asyncio.Lock:
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]

async def check_idempotency(key: str, payload_hash: str):
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM idempotency_keys WHERE key = ?", 
            (key,)
        ) as cursor:
            return await cursor.fetchone()

async def save_initial_request(key: str, payload_hash: str):
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "INSERT INTO idempotency_keys (key, payload_hash, status) VALUES (?, ?, ?)",
            (key, payload_hash, "in_flight")
        )
        await db.commit()

async def save_final_response(key: str, response_body: str, status_code: int):
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            """
            UPDATE idempotency_keys 
            SET status = ?, response_body = ?, response_status_code = ? 
            WHERE key = ?
            """,
            ("done", response_body, status_code, key)
        )
        await db.commit()