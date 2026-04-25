import asyncio
import logging
import os
import subprocess
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import ApiClient, Configuration, MessagingApi, MessagingApiBlob
from linebot.v3.webhooks import ImageMessageContent, JoinEvent, MessageEvent

from db import get_album_id, init_db, save_group_album
from immich import add_to_album, create_album, upload_asset

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
DEPLOY_SECRET = os.environ.get("DEPLOY_SECRET", "")

SOURCE_DIR  = os.environ.get("SOURCE_DIR",  "/home/gakes/projects/gurry0927/LineGroupBot")
COMPOSE_DIR = os.environ.get("COMPOSE_DIR", "/data/services/linebot")

parser = WebhookParser(LINE_CHANNEL_SECRET)
line_config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

_group_locks: dict[str, asyncio.Lock] = {}

def _get_lock(group_id: str) -> asyncio.Lock:
    if group_id not in _group_locks:
        _group_locks[group_id] = asyncio.Lock()
    return _group_locks[group_id]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("DB initialised")
    yield


app = FastAPI(lifespan=lifespan)


async def ensure_album(group_id: str) -> str:
    async with _get_lock(group_id):
        album_id = await get_album_id(group_id)
        if album_id:
            return album_id

        with ApiClient(line_config) as api_client:
            line_api = MessagingApi(api_client)
            try:
                summary = line_api.get_group_summary(group_id)
                group_name = summary.group_name or f"LINE {group_id[:8]}"
            except Exception:
                group_name = f"LINE {group_id[:8]}"

        album_id = await create_album(group_name)
        await save_group_album(group_id, group_name, album_id)
        logger.info("Created album %s for group %s", group_name, group_id)
        return album_id


@app.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()

    try:
        events = parser.parse(body.decode(), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        source = event.source
        group_id = getattr(source, "group_id", None)
        if not group_id:
            continue

        if isinstance(event, JoinEvent):
            await ensure_album(group_id)

        elif isinstance(event, MessageEvent) and isinstance(event.message, ImageMessageContent):
            album_id = await ensure_album(group_id)

            with ApiClient(line_config) as api_client:
                blob_api = MessagingApiBlob(api_client)
                image_bytes = blob_api.get_message_content(event.message.id)

            filename = (
                f"{group_id}_{event.message.id}_"
                f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.jpg"
            )
            asset_id = await upload_asset(image_bytes, filename)
            await add_to_album(album_id, asset_id)
            logger.info("Saved image %s → album %s", filename, album_id)

    return {"status": "ok"}


@app.post("/deploy")
async def deploy(x_deploy_token: str = Header(default="")):
    if not DEPLOY_SECRET or x_deploy_token != DEPLOY_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    def run():
        subprocess.run(["git", "pull", "origin", "main"], cwd=SOURCE_DIR)
        subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd=COMPOSE_DIR)
        logger.info("Deploy completed")

    threading.Thread(target=run, daemon=True).start()
    return JSONResponse({"ok": True})


@app.get("/health")
async def health():
    return {"status": "ok"}
