from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import settings
from .seed import NOTIFICATIONS, SCHEMES
from datetime import datetime, timedelta, timezone


def create_client() -> AsyncIOMotorClient:
    return AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000, tz_aware=True)


async def init_db(db: AsyncIOMotorDatabase) -> None:
    """Create indexes and seed reference data on first run."""
    await db.farmer_profiles.create_index("created_at")
    await db.notifications.create_index("created_at")
    if await db.schemes.count_documents({}) == 0:
        await db.schemes.insert_many([dict(s) for s in SCHEMES])
    if await db.notifications.count_documents({}) == 0:
        now = datetime.now(timezone.utc)
        await db.notifications.insert_many(
            [{"title": t, "detail": d, "unread": u, "created_at": now - timedelta(minutes=m)} for t, d, m, u in NOTIFICATIONS]
        )
