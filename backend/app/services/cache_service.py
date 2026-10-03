"""
Database-backed cache layer
each endpoint + params combination gets a 24h TTL
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select,delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.models import CacheEntry


def _utcnow() -> datetime:
    # tz-aware for timestamptz columns; asyncpg treats naive values as local time
    return datetime.now(timezone.utc)


def _make_hash(endpoint: str, params: dict) -> str:
    raw = endpoint + json.dumps(params, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:64]

async def get_cached(
    db: AsyncSession, endpoint: str, params: dict
) -> dict | list | None:
    """return a valid cache entry if present, else None."""
    h = _make_hash(endpoint, params)
    stmt = select(CacheEntry).where(
        CacheEntry.endpoint == endpoint,
        CacheEntry.params_hash == h,
        CacheEntry.expires_at > _utcnow(),
    )
    result = await db.execute(stmt)
    entry= result.scalar_one_or_none()
    if entry:
        return json.loads(entry.data_json)
    return None


async def set_cached(
    db:AsyncSession,
    endpoint: str,
    params: dict,
    data: dict | list,
    ttl_seconds: int | None = None,
) -> None:
    """Write data to the cache, replacing any old entry for the same key."""
    h = _make_hash(endpoint, params)
    ttl = ttl_seconds or settings.CACHE_TTL_SECONDS

    # remove the old entry
    await db.execute(
        delete(CacheEntry).where(
            CacheEntry.endpoint == endpoint,
            CacheEntry.params_hash == h,
        )
    )

    entry = CacheEntry(
        endpoint=endpoint,
        params_hash=h,
        data_json=json.dumps(data, default=str),
        expires_at=_utcnow() + timedelta(seconds=ttl),
    )
    db.add(entry)
    await db.commit()


async def invalidate_cached(db: AsyncSession, endpoint: str, params: dict) -> None:
    """drop the cache entry for one key so the next read fetches fresh data"""
    await db.execute(
        delete(CacheEntry).where(
            CacheEntry.endpoint ==endpoint,
            CacheEntry.params_hash == _make_hash(endpoint, params),
        )
    )
    await db.commit()


async def purge_expired(db: AsyncSession) -> int:
    """Delete all expired cache entries. Meant to be called by a scheduler."""
    result = await db.execute(
        delete(CacheEntry).where(CacheEntry.expires_at<= _utcnow())
    )
    await db.commit()
    return result.rowcount