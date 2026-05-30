import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import ApiClient, Configuration, MessagingApi, MessagingApiBlob
from linebot.v3.webhooks import ImageMessageContent, JoinEvent, MessageEvent

from db import get_album_id, init_db, save_group_album
from immich import add_to_album, create_album, immich_self_check, upload_asset

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]

parser = WebhookParser(LINE_CHANNEL_SECRET)
line_config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

_group_locks: dict[str, asyncio.Lock] = {}
_bg_tasks: set[asyncio.Task] = set()


def _get_lock(group_id: str) -> asyncio.Lock:
    # setdefault = atomic get-or-create; avoids two locks for one group under
    # concurrent first-images (which would let both create a duplicate album).
    return _group_locks.setdefault(group_id, asyncio.Lock())


def _spawn(coro) -> None:
    # Hold a strong ref so the background task isn't GC'd mid-flight; drop on done.
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("DB initialised")
    # Loud startup check: if immich is unreachable or the key is bad, we want it
    # in the logs at boot — not discovered weeks later via missing photos.
    await immich_self_check(logger)
    yield


app = FastAPI(lifespan=lifespan)


async def ensure_album(group_id: str) -> str:
    async with _get_lock(group_id):
        album_id = await get_album_id(group_id)
        if album_id:
            return album_id

        # get_group_summary is a blocking SDK call — run it off the event loop.
        def _summary():
            with ApiClient(line_config) as api_client:
                return MessagingApi(api_client).get_group_summary(group_id)

        try:
            summary = await asyncio.to_thread(_summary)
            group_name = summary.group_name or f"LINE {group_id[:8]}"
        except Exception:
            logger.warning("get_group_summary failed for %s; using fallback name", group_id)
            group_name = f"LINE {group_id[:8]}"

        album_id = await create_album(group_name)
        await save_group_album(group_id, group_name, album_id)
        logger.info("Created album %s for group %s", group_name, group_id)
        return album_id


async def _process_event(event) -> None:
    group_id = getattr(getattr(event, "source", None), "group_id", None)
    if not group_id:
        return

    if isinstance(event, JoinEvent):
        await ensure_album(group_id)
        return

    if isinstance(event, MessageEvent) and isinstance(event.message, ImageMessageContent):
        album_id = await ensure_album(group_id)

        # get_message_content is a blocking SDK call — run it off the event loop.
        def _fetch():
            with ApiClient(line_config) as api_client:
                return MessagingApiBlob(api_client).get_message_content(event.message.id)

        image_bytes = await asyncio.to_thread(_fetch)
        filename = (
            f"{group_id}_{event.message.id}_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.jpg"
        )
        asset_id = await upload_asset(image_bytes, filename)
        await add_to_album(album_id, asset_id)
        logger.info("Saved image %s → album %s", filename, album_id)


async def _handle_event(event) -> None:
    # One failure must not lose the image silently nor abort sibling events.
    try:
        await _process_event(event)
    except Exception:
        gid = getattr(getattr(event, "source", None), "group_id", "?")
        mid = getattr(getattr(event, "message", None), "id", "?")
        logger.exception("Failed to process event (group=%s message=%s)", gid, mid)


@app.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()

    try:
        events = parser.parse(body.decode(), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception:
        # Malformed body / non-JSON / missing 'events' → 200 so LINE doesn't retry-storm.
        logger.warning("Failed to parse webhook body; ignoring")
        return {"status": "ignored"}

    # ACK immediately and do the slow LINE/immich work off the request path. A slow
    # or down immich can then never delay the 200 and trip LINE's webhook auto-disable.
    for event in events:
        _spawn(_handle_event(event))

    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}
