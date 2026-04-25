# Deployment Guide

## Self-hosted NAS / Server

### Directory layout (recommended)

```
/srv/linebot/          ← docker-compose.yml + .env (config)
/srv/linebot/data/     ← persistent SQLite database
/path/to/LineGroupBot/ ← source code (git clone)
```

### 1. Clone the repo

```bash
git clone https://github.com/gurry0927/LineGroupBot.git
```

### 2. Create config directory

```bash
mkdir -p /srv/linebot/data
```

### 3. Create docker-compose.yml

Place this in `/srv/linebot/docker-compose.yml`, adjusting paths and port as needed:

```yaml
name: linebot

services:
  linebot:
    build: /path/to/LineGroupBot
    container_name: linebot
    restart: unless-stopped
    ports:
      - "3000:3000"
    env_file:
      - .env
    volumes:
      - /srv/linebot/data:/app/data
    environment:
      - TZ=Asia/Taipei
```

### 4. Set up .env

```bash
cp /path/to/LineGroupBot/.env.example /srv/linebot/.env
nano /srv/linebot/.env   # fill in your credentials
```

### 5. Start

```bash
cd /srv/linebot
docker compose up -d --build
docker compose logs -f
```

### 6. Expose via reverse proxy

Point your reverse proxy or tunnel to `http://localhost:3000`.
Set the LINE webhook URL to `https://your-domain.example.com/webhook`.

### Updating

```bash
cd /path/to/LineGroupBot
git pull

cd /srv/linebot
docker compose up -d --build
```

## Useful commands

```bash
# View logs
docker compose -f /srv/linebot/docker-compose.yml logs -f

# Restart
docker compose -f /srv/linebot/docker-compose.yml restart

# Shell into container
docker exec -it linebot bash
```
