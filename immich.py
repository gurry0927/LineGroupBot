import os
from datetime import datetime, timezone

import httpx

IMMICH_URL = os.getenv("IMMICH_URL", "")
IMMICH_API_KEY = os.getenv("IMMICH_API_KEY", "")

_HEADERS = {"x-api-key": IMMICH_API_KEY}


async def create_album(name: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{IMMICH_URL}/api/albums",
            headers=_HEADERS,
            json={"albumName": name},
        )
        resp.raise_for_status()
        return resp.json()["id"]


async def upload_asset(image_bytes: bytes, filename: str) -> str:
    now = datetime.now(timezone.utc).isoformat()
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{IMMICH_URL}/api/assets",
            headers=_HEADERS,
            files={"assetData": (filename, image_bytes, "image/jpeg")},
            data={
                "deviceAssetId": filename,
                "deviceId": "linebot",
                "fileCreatedAt": now,
                "fileModifiedAt": now,
            },
        )
        resp.raise_for_status()
        return resp.json()["id"]


async def add_to_album(album_id: str, asset_id: str):
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{IMMICH_URL}/api/albums/{album_id}/assets",
            headers=_HEADERS,
            json={"ids": [asset_id]},
        )
        resp.raise_for_status()
