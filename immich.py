import logging
import os
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

IMMICH_URL = os.getenv("IMMICH_URL", "").rstrip("/")
IMMICH_API_KEY = os.getenv("IMMICH_API_KEY", "")

_HEADERS = {"x-api-key": IMMICH_API_KEY}
# Explicit, bounded timeouts so a slow/hung immich surfaces as a logged error
# instead of an indefinitely-pending request.
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_UPLOAD_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def _check(resp: httpx.Response, what: str) -> None:
    # On failure, log status + url + truncated body for an actionable record
    # (e.g. "403 Missing required permission") — never logs the api key.
    if resp.status_code >= 400:
        logger.error(
            "immich %s failed: HTTP %s %s → %s",
            what, resp.status_code, resp.request.url, resp.text[:300],
        )
    resp.raise_for_status()


async def create_album(name: str) -> str:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{IMMICH_URL}/api/albums",
            headers=_HEADERS,
            json={"albumName": name},
        )
        _check(resp, "create_album")
        return resp.json()["id"]


async def upload_asset(image_bytes: bytes, filename: str) -> str:
    now = datetime.now(timezone.utc).isoformat()
    async with httpx.AsyncClient(timeout=_UPLOAD_TIMEOUT) as client:
        resp = await client.post(
            f"{IMMICH_URL}/api/assets",
            headers=_HEADERS,
            files={"assetData": (filename, image_bytes, "image/jpeg")},
            # Immich v3 removed deviceAssetId / deviceId from the upload API.
            data={
                "fileCreatedAt": now,
                "fileModifiedAt": now,
            },
        )
        _check(resp, "upload_asset")
        return resp.json()["id"]


async def add_to_album(album_id: str, asset_id: str) -> None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.put(
            f"{IMMICH_URL}/api/albums/{album_id}/assets",
            headers=_HEADERS,
            json={"ids": [asset_id]},
        )
        _check(resp, "add_to_album")


async def immich_self_check(log) -> None:
    """Startup probe: confirm immich is reachable and the API key works.
    Logs loudly on failure so a bad key / down immich is visible at boot."""
    if not IMMICH_URL or not IMMICH_API_KEY:
        log.error("immich self-check: IMMICH_URL / IMMICH_API_KEY not set")
        return
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{IMMICH_URL}/api/albums", headers=_HEADERS)
        if resp.status_code == 200:
            log.info("immich self-check OK (%s, %d albums visible)", IMMICH_URL, len(resp.json()))
        else:
            log.error(
                "immich self-check FAILED: HTTP %s from %s/api/albums → %s",
                resp.status_code, IMMICH_URL, resp.text[:200],
            )
    except Exception as e:
        log.error("immich self-check FAILED: cannot reach %s (%s)", IMMICH_URL, e)
