"""
SQLite tabanlı önbellekleme katmani
her endpoint +parametre kombinasyonu için 24 saatlik TTL uygulanır
"""
import hashlib
import json
from datetime import datetime, timedelta

from sqlalchemy import select,delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.models import CacheEntry


def _make_hash(endpoint: str, params: dict) -> str:
    raw = endpoint + json.dumps(params, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:64]

async def get_cached(
    db: AsyncSession, endpoint: str, params: dict
) -> dict | list | None:
    """Geçerli bir önbellek kaydı varsa döndür; yoksa None."""
    h = _make_hash(endpoint, params)
    stmt = select(CacheEntry).where(
        CacheEntry.endpoint == endpoint,
        CacheEntry.params_hash == h,
        CacheEntry.expires_at > datetime.utcnow(),
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
    """Veriyi önbelleğe yaz; aynı anahtar için eski kayıt varsa sil"""
    h = _make_hash(endpoint, params)
    ttl = ttl_seconds or settings.CACHE_TTL_SECONDS

    # eski kaydı temizle
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
        expires_at=datetime.utcnow() + timedelta(seconds=ttl),
    )
    db.add(entry)
    await db.commit()


async def purge_expired(db: AsyncSession) -> int:
    """Süresi dolmuş tümm önbellek kayıtlarını sil. Scheduler tarafından çağrılır"""
    result = await db.execute(
        delete(CacheEntry).where(CacheEntry.expires_at<= datetime.utcnow())
    )
    await db.commit()
    return result.rowcount