# Custom Chromecast Receiver — Implementation Plan

## Context

home-cast currently manages Chromecast playback by playing one MP3 at a time via `play_media()` and manually advancing the queue in Python when each track finishes (`ChromecastQueue` in `app/devices/chromecast.py`). This means Google Home, voice commands, and the physical remote cannot control next/prev — only the home-cast UI can.

The goal is to replace this with a **Custom Chromecast Receiver**: a web app (HTML + JS using Google's Cast Application Framework v3) that runs on the Chromecast device itself. The receiver owns playback and the native queue, so Google Home, voice, and any Cast sender get full next/prev/pause/seek. The Python backend becomes a sender that loads the queue once and then issues control commands.

User decisions:
- Receiver hosted on a **separate static host** (GitHub Pages / Cloudflare Pages / Netlify)
- Receiver displays a **queue view** (current track + upcoming tracks list)
- Shuffle is **pre-shuffle only** — toggling shuffle reloads the queue in new order (no mid-queue reshuffle)

---

## Phase 1 — Cast Console Setup (manual, one-time)

1. Register at [cast.google.com/publish](https://cast.google.com/publish) ($5 one-time)
2. Create a new **Custom Receiver** app, pointing to the hosted receiver URL (e.g. `https://your-pages-url/index.html`)
3. Note the **App ID** (e.g. `AB1CD2EF`)
4. During development: whitelist your Chromecast device serial number in the Cast console so it loads from a local/staging URL without needing production HTTPS
5. Add `cast_app_id` to `config.yaml` and `config.yaml.example`

---

## Phase 2 — Receiver Web App

**New directory: `receiver/`** (deployed separately to static host)

```
receiver/
  index.html       ← entry point loaded by Chromecast
  receiver.js      ← all CAF v3 logic
  receiver.css     ← queue view UI styles
  assets/
    logo.png       ← home-cast logo for idle screen
```

### `receiver.js` — CAF v3 implementation

**Initialization:**
```js
const context = cast.framework.CastReceiverContext.getInstance();
const playerManager = context.getPlayerManager();
context.start({ queue: new cast.framework.QueueManager() });
```

**LOAD intercept** — receives `MediaQueueItem[]` from Python sender, starts playback. CAF handles all queue advancement natively after this point.

**Custom message namespace:** `urn:x-cast:io.1home.homecast`
- Inbound messages from Python:
  - `{ type: "SET_REPEAT", mode: "off"|"all"|"one" }` → update CAF repeat mode
  - `{ type: "NOTIFICATION", url, mediaType }` → pause queue, play sound, resume
  - `{ type: "RELOAD_QUEUE", items, startIndex }` → used for shuffle reload
- Outbound messages to Python (queue state sync):
  - `{ type: "QUEUE_STATE", currentIndex, itemIds }` → sent on every track change

**UI — queue view:**
- Left panel: album art (large), track title, artist, album, progress bar, track position (e.g. "3 / 12")
- Right panel: scrollable list of upcoming tracks with title + artist, current track highlighted
- Idle screen: home-cast logo + "Ready to cast" on dark background

**Notification flow (in receiver JS):**
1. Receive `NOTIFICATION` message
2. Save current queue position + seek position
3. Pause queue playback
4. Play notification URL as one-shot media
5. On FINISHED/ERROR: restore queue position and resume

---

## Phase 3 — Python Sender Rewrite

### `app/devices/chromecast.py`

**Replace `ChromecastQueue` with `CustomReceiverQueue`:**

Key changes:
- `load(tracks, shuffle, repeat)`:
  - If `shuffle=True`, shuffle `tracks` list upfront with `random.shuffle()` before building items
  - Launch the custom receiver app: `cc.start_app(cast_app_id)` then wait for it to be ready
  - Build `MediaQueueItem` list — one per track with `MusicTrackMediaMetadata`
  - Call `mc.queue_load(items, repeat_mode=...)` — single call, CAF takes over
  - Store shadow copy of tracks + item IDs for state reporting

- `set_shuffle(enabled)`:
  - Re-shuffle (or un-shuffle) the track list
  - Call `load()` again with new order starting from current track
  - Brief queue reload — acceptable per user decision

- `set_repeat(mode)`:
  - Send custom message `SET_REPEAT` to receiver via `cc.media_controller.send_message(namespace, {...})`

- `play_next()` / `play_prev()`:
  - `mc.queue_next()` / `mc.queue_prev()`

- `play_track_at(index)`:
  - Look up item ID from shadow copy: `_item_ids[index]`
  - Call `mc.queue_play_item(item_id)`

- `get_queue_info()`:
  - Returns same shape as today — `currentIndex`, `trackCount`, `currentTrack`, `tracks`, `shuffle`, `repeat`
  - `currentIndex` derived from `mc.status.current_item_id` matched against `_item_ids`

- `new_media_status()` — simplified:
  - Remove `FINISHED` detection and `play_next()` call (CAF handles advancement)
  - Keep `CANCELLED` detection → `clear()` local shadow state
  - Keep external-media detection (different `content_id` not in our item set)

- `play_notification(cc, slug, sound_url)`:
  - Send `NOTIFICATION` custom message to receiver
  - Receiver handles pause → play sound → resume entirely in JS
  - Remove `_NotificationListener` class and `_notification_url` suppression logic

**`resume(cc)`** — on IDLE queue: call `cc.start_app(cast_app_id)` + reload queue from shadow copy

**`config.yaml`** — add:
```yaml
cast_app_id: "AB1CD2EF"
```

**`app/config.py`** — read `cast_app_id` and pass through `APP` config dict

### `app/music/routes.py`

- `POST /music/play` and `POST /music/playlists/<id>/play`: no route signature changes, queue.load() call stays the same
- `POST /music/transfer`: no changes needed — already transfers track list + shuffle + repeat state

---

## Phase 4 — Frontend (`ui/`)

Minimal changes — the API shape is unchanged so most of `SpeakerCard.vue` and `stores/devices.ts` require no edits.

**`ui/src/components/SpeakerCard.vue`:**
- Shuffle toggle: add a tooltip or note "Shuffle reloads the queue" to set expectations
- No structural changes needed

**`ui/src/stores/devices.ts`:**
- No changes needed

---

## Critical Files

| File | Change |
|---|---|
| `receiver/index.html` | **New** — receiver entry point |
| `receiver/receiver.js` | **New** — CAF v3 logic, queue view, notifications |
| `receiver/receiver.css` | **New** — queue view UI |
| `app/devices/chromecast.py` | **Rewrite** — `ChromecastQueue` → `CustomReceiverQueue`, queue_load, custom messages |
| `app/config.py` | **Minor** — add `cast_app_id` to config schema |
| `config.yaml` / `config.yaml.example` | **Minor** — add `cast_app_id` field |
| `ui/src/components/SpeakerCard.vue` | **Minor** — shuffle tooltip only |

Files with **no changes needed:** `app/music/routes.py`, `app/devices/routes.py`, `app/music/downloader.py`, `app/ws.py`, `ui/src/stores/devices.ts`, `ui/src/api/devices.ts`

---

## What Gets Deleted

| Removed | Replaced by |
|---|---|
| `ChromecastQueue._play_current()` | `mc.queue_load()` one-shot |
| `ChromecastQueue._advance_and_play()` | CAF native queue advancement |
| `ChromecastQueue.new_media_status()` FINISHED handler | CAF handles it |
| `_NotificationListener` class | Custom message → receiver JS |
| `play_notification()` resume/seek logic | Receiver JS handles resume |
| `ChromecastQueue._notification_url` suppression | No longer needed |
| `set_shuffle()` mid-queue rebuild | Pre-shuffle before load |

---

## Implementation Order

1. Cast console registration + dev device whitelist
2. `config.yaml` — add `cast_app_id`
3. `receiver/` — build and deploy to static host, verify it loads on Chromecast
4. `app/devices/chromecast.py` — rewrite `ChromecastQueue` → `CustomReceiverQueue`
5. Test all control flows: play, next, prev, play-track, shuffle, repeat, notify, transfer, stop, resume
6. `SpeakerCard.vue` — shuffle tooltip

---

## Verification

- Play a playlist → all tracks appear in queue view on Chromecast display
- Google Home app shows next/prev controls and track metadata
- Voice: "Hey Google, next song" advances track
- Shuffle toggle → queue reloads in new order, playback continues from first shuffled track
- Repeat modes: off (stops at end), all (loops), one (repeats current)
- Notification: plays sound, resumes at correct position
- Transfer queue between two Chromecast devices
- Stop → receiver shows idle screen
- Resume after stop → queue reloads from beginning
