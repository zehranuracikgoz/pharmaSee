import hmac

from fastapi import Header, HTTPException

from app.config import settings


async def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """guard for manual trigger endpoints: X-Admin-Token must match ADMIN_TOKEN """
    if not settings.ADMIN_TOKEN:
        # no token configured: keep the endpoints closed instead of open by accident
        raise HTTPException(status_code=503, detail="admin endpoints are disabled (ADMIN_TOKEN is not set)")
    # constant-time comparison so response timing doesn't leak the token
    if not x_admin_token or not hmac.compare_digest(
        x_admin_token.encode(), settings.ADMIN_TOKEN.encode()
    ):
        raise HTTPException (status_code=401, detail="invalid or missing admin token")
