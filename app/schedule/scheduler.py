"""Alarm scheduler.

A single background thread wakes once a minute and fires any enabled alarm
whose ``time`` matches the current local ``HH:MM`` and whose weekday mask
includes today (an empty mask is a one-shot: it fires once, then disables
itself). This is restart-safe — alarms are persisted JSON loaded on startup —
and mirrors the discovery cache thread in ``app/devices/discovery.py`` rather
than juggling a pile of ``threading.Timer`` objects.

Firing runs inside ``app.app_context()`` so the shared play helpers can read
config; failures on one device or one alarm never abort the tick.
"""

import time
import logging
import threading
from datetime import datetime

from app import storage
from app.music import player
from app.devices import chromecast, sonos
from app.devices.routes import _resolve_targets
from app.ws import broadcast_states

logger = logging.getLogger(__name__)

# The Flask app captured at startup — the tick thread has no request context.
_app = None
# Guard against firing the same alarm twice within its minute: id -> "YYYY-MM-DD HH:MM"
_last_fired = {}


def start_scheduler(flask_app):
    global _app
    _app = flask_app
    t = threading.Thread(target=_tick_loop, name="alarm-scheduler", daemon=True)
    t.start()
    logger.info("Alarm scheduler started")


def _tick_loop():
    while True:
        try:
            _check_due(datetime.now())
        except Exception:
            logger.exception("Alarm tick failed")
        # Sleep to just past the next minute boundary so we wake ~once/minute
        # aligned to the clock (a fire slightly late is fine; early is not).
        now = datetime.now()
        time.sleep(max(1, 60 - now.second))


def _check_due(now):
    stamp = now.strftime("%Y-%m-%d %H:%M")
    hhmm = now.strftime("%H:%M")
    weekday = now.weekday()  # Mon=0..Sun=6

    for alarm in storage.get_alarms():
        if not alarm.get("enabled"):
            continue
        if alarm.get("time") != hhmm:
            continue
        days = alarm.get("days") or []
        if days and weekday not in days:
            continue
        if _last_fired.get(alarm["id"]) == stamp:
            continue  # already fired this minute
        _last_fired[alarm["id"]] = stamp
        _fire(alarm)


def _fire(alarm):
    logger.info("Firing alarm %s (%s)", alarm.get("id"), alarm.get("time"))
    with _app.app_context():
        try:
            _do_fire(alarm)
        except Exception:
            logger.exception("Alarm %s failed to fire", alarm.get("id"))
        finally:
            # One-shot alarms disable themselves after firing (success or not,
            # so a broken alarm doesn't retry every day).
            if not (alarm.get("days") or []):
                storage.set_alarm_enabled(alarm["id"], False)
                logger.info("One-shot alarm %s disabled after firing", alarm["id"])


def _do_fire(alarm):
    config = _app.config["APP"]
    target = alarm.get("target") or {}
    slug = target.get("slug", "all")
    dtype = target.get("type", "all")
    targets = _resolve_targets(slug, dtype)
    if not targets:
        logger.warning("Alarm %s has no resolvable targets", alarm["id"])
        return

    volume = alarm.get("volume")
    fade_in = int(alarm.get("fadeIn") or 0)

    # Apply the starting volume before play. With fade-in we begin near-silent
    # and ramp up in a background thread once playback has started.
    if volume is not None:
        start_vol = 0.05 if fade_in > 0 else float(volume)
        for tslug, tdtype in targets:
            _set_volume(tslug, tdtype, start_vol)

    _play_action(config, alarm, targets)

    if volume is not None and fade_in > 0:
        threading.Thread(
            target=_fade_volume,
            args=(list(targets), 0.05, float(volume), fade_in),
            daemon=True,
        ).start()

    broadcast_states()


def _play_action(config, alarm, targets):
    action = alarm.get("action") or {}
    kind = action.get("kind")
    ref = action.get("ref")
    shuffle = alarm.get("shuffle", False)
    repeat = alarm.get("repeat", "off")

    if kind == "playlist":
        if not ref:
            raise player.PlayError("Alarm playlist not set")
        for tslug, tdtype in targets:
            try:
                player.play_saved_playlist(
                    config, ref, tslug, tdtype, shuffle=shuffle, repeat=repeat,
                )
            except player.PlayError as e:
                logger.warning("Alarm playlist failed on %s:%s — %s", tslug, tdtype, e)

    elif kind == "radio":
        station = _find_favorite(ref)
        if not station:
            raise player.PlayError(f"Favorite radio {ref!r} not found")
        for tslug, tdtype in targets:
            try:
                player.play_radio(
                    tslug, tdtype, station["url"],
                    station_name=station.get("name", "Radio"),
                    station_favicon=station.get("favicon"),
                )
            except player.PlayError as e:
                logger.warning("Alarm radio failed on %s:%s — %s", tslug, tdtype, e)

    else:
        raise player.PlayError(f"Unknown alarm action kind: {kind!r}")


def _find_favorite(stationuuid):
    for s in storage.get_favorites():
        if s.get("stationuuid") == stationuuid:
            return s
    return None


def _set_volume(slug, dtype, volume):
    try:
        if dtype == "sonos":
            device = sonos.get_by_slug(slug)
            if device:
                sonos.set_volume(device, volume)
        else:
            cc = chromecast.get_by_slug(slug)
            if cc:
                chromecast.set_volume(cc, volume)
    except Exception:
        logger.debug("Failed to set volume on %s:%s", slug, dtype)


def _fade_volume(targets, start, end, seconds):
    """Ramp volume from start to end over `seconds`, in ~2s steps."""
    steps = max(1, seconds // 2)
    for i in range(1, steps + 1):
        time.sleep(min(2, seconds / steps))
        vol = start + (end - start) * (i / steps)
        for tslug, tdtype in targets:
            _set_volume(tslug, tdtype, round(vol, 3))
