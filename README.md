# Home-Cast

A self-hosted home audio controller with a Vue 3 UI. Controls **Chromecast** and **Sonos** speakers — search and play music from YouTube Music, stream radio stations, manage playlists, and trigger notification sounds.

## Features

- **Multi-device support** — Chromecast (audio & video) and Sonos
- **YouTube Music** — search songs, artists, albums, playlists; play with automatic queuing and background download
- **Radio** — search via Radio Browser API, play live streams
- **Saved playlists** — create and manage local playlists
- **Queue** — shuffle, repeat (off / all / one), next / prev, sleep timer
- **Notification sound** — interrupt playback with a sound clip, then resume from the same position
- **Real-time UI** — WebSocket state updates every 3 seconds
- **Mobile-friendly** Vue 3 + PrimeVue UI

<img width="1475" height="1151" alt="image" src="https://github.com/user-attachments/assets/543766eb-a5e1-45a0-b6a0-4b1c1370e7cb" />


## Quick Start (Docker)

```bash
# 1. Pull and run
docker compose up -d

# 2. Open the UI
http://<your-server-ip>:5050
```

The container runs nginx (port 5050) serving the Vue UI and proxying API calls to the Flask backend (port 5000 internally).

## Configuration

Copy `config.yaml.example` to `config.yaml` (for local dev) or set the `APP_HOSTNAME` environment variable (for Docker):

```yaml
# config.yaml
hostname: "http://192.168.1.100:5000"   # LAN IP — speakers must reach this
port: 5000
cache:
  ttl: 3600       # seconds to keep downloaded audio
  dir: "./cache"
```

> **Important:** `hostname` must be the LAN IP/hostname of your server, not `localhost`. Chromecast and Sonos devices fetch audio files directly from this URL.

### Docker environment variables

| Variable | Description |
|---|---|
| `APP_HOSTNAME` | Overrides `hostname` in config (e.g. `http://192.168.1.100:5050`) |
| `APP_PORT` | Overrides Flask port (default `5000`) |
| `APP_CACHE_DIR` | Overrides cache directory |

## API

All endpoints accept and return JSON.

### Devices

| Method | Path | Description |
|---|---|---|
| GET | `/get-devices` | List all discovered Chromecast & Sonos devices |
| POST | `/refresh-devices` | Force device rediscovery |
| POST | `/device/slug/play-url` | Play a URL on a device |
| POST | `/device/slug/pause` | Pause |
| POST | `/device/slug/resume` | Resume |
| POST | `/device/slug/stop` | Stop |
| POST | `/device/slug/next` | Next track |
| POST | `/device/slug/prev` | Previous track |
| POST | `/device/slug/volume` | Get volume |
| POST | `/device/slug/volume/set` | Set volume (0–1) |
| POST | `/device/slug/volume/delta` | Adjust volume by delta |
| POST | `/device/slug/shuffle` | Set shuffle on/off |
| POST | `/device/slug/repeat` | Set repeat mode (`off` / `all` / `one`) |
| POST | `/device/slug/sleep` | Set sleep timer (minutes) |
| POST | `/device/slug/state` | Get full device state |
| POST | `/device/slug/notify` | Play notification sound, then resume |

Device body always includes `{ "slug": "...", "type": "chromecast" | "sonos" }`.

#### Notification sound example

```json
POST /device/slug/notify
{
  "slug": "living_room",
  "type": "chromecast",
  "soundUrl": "http://example.com/chime.mp3"
}
```

Pauses current music, plays the sound, then resumes from the same song and timestamp.

### Music

| Method | Path | Description |
|---|---|---|
| GET | `/music/search?q=&type=` | Search (type: `songs` / `artists` / `playlists` / `albums`) |
| POST | `/music/play` | Play song or YouTube Music playlist |
| GET | `/music/playlists` | List saved playlists |
| POST | `/music/playlists` | Create saved playlist |
| GET | `/music/playlists/<id>` | Get saved playlist |
| PUT | `/music/playlists/<id>` | Update saved playlist |
| DELETE | `/music/playlists/<id>` | Delete saved playlist |
| POST | `/music/playlists/<id>/play` | Play saved playlist |

Play body: `{ "slug", "type", "videoId" | "playlistId", "shuffle": false, "repeat": "off" }`

### Radio

| Method | Path | Description |
|---|---|---|
| GET | `/radio/search?q=` | Search radio stations |
| GET | `/radio/popular` | Popular stations |
| POST | `/radio/play` | Play a radio station |

### WebSocket

Connect to the server root with Socket.IO. The server emits a `states` event every 3 seconds (or immediately after any action) with a map of device states:

```json
{
  "living_room:chromecast": {
    "status": "PLAYING",
    "volume": 0.4,
    "queue": { "currentIndex": 2, "trackCount": 12, "shuffle": true, "repeat": "all" },
    "nowPlaying": { "title": "...", "thumbnail": "...", "contentId": "..." }
  }
}
```

## Local Development

```bash
# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py

# Frontend (separate terminal)
cd ui
npm install
npm run dev
```

The Vite dev server proxies `/api/` to the Flask backend automatically.

## Docker Build

```bash
docker build -t ghcr.io/pevecyan/home-cast:1.0.0 .
docker push ghcr.io/pevecyan/home-cast:1.0.0
```

## Requirements

- Python 3.12+
- Node 20+ (for UI build)
- ffmpeg (for yt-dlp audio extraction)
- Speakers must be on the same LAN as the server
