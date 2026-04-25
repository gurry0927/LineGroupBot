# LineGroupBot

A LINE bot that automatically saves group photos to your self-hosted [Immich](https://immich.app) instance.

## Features

- Automatically creates an Immich album when the bot joins a LINE group
- Saves every photo sent in the group to the corresponding album
- Supports multiple groups — each group gets its own album
- Per-group queue to prevent duplicate albums under concurrent uploads

## Requirements

- A LINE Messaging API channel ([LINE Developers Console](https://developers.line.biz))
- A self-hosted Immich instance with API access
- Docker & Docker Compose

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/gurry0927/LineGroupBot.git
cd LineGroupBot

# 2. Set up environment
cp .env.example .env
# Edit .env and fill in your LINE and Immich credentials

# 3. Start the bot
docker compose up -d --build
```

The bot listens on port **3000**. Expose it via a reverse proxy or tunnel (e.g. Cloudflare Tunnel, ngrok) and set the webhook URL in the LINE Developers Console:

```
https://your-domain.example.com/webhook
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE channel access token |
| `LINE_CHANNEL_SECRET` | LINE channel secret |
| `IMMICH_URL` | Your Immich instance URL (e.g. `https://immich.example.com`) |
| `IMMICH_API_KEY` | Immich API key |
| `DB_PATH` | SQLite database path inside container (default: `data/bot.db`) |

## Data Persistence

Photo records and group→album mappings are stored in a SQLite database mounted at `./data/bot.db`.
Back up the `data/` directory to preserve your data.

## License

MIT
