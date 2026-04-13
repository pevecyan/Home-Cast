
import time
import threading

from flask import Flask, logging, request, jsonify
import logging as py_logging
import pychromecast
import soco
import concurrent.futures

CACHE_UPDATE_INTERVAL = 600  # 10 minutes in seconds

app = Flask(__name__)
logger = logging.create_logger(app)

chromecast_cache = {}
chromecast_names_cache = {}
sonos_cache = {}
sonos_names_cache = {}

def get_chromecasts():
    chromecasts, browser = pychromecast.get_chromecasts()
    browser.stop_discovery()
    return [
        {
            "type": "chromecast",
            "friendly_name": cc.cast_info.friendly_name,
            "slug": cc.cast_info.friendly_name.lower().replace(" ", "_"),
            "host": cc.cast_info.host,
            "port": cc.cast_info.port
        }
        for cc in chromecasts
    ]

def get_sonos():
    devices = soco.discover()
    if not devices:
        return []
    return [
        {
            "type": "sonos",
            "friendly_name": device.player_name,
            "slug": device.player_name.lower().replace(" ", "_"),
            "host": device.ip_address,
            "port": 1400  # Sonos default port
        }
        for device in devices
    ]

def get_chromecast(ip, port) -> pychromecast.Chromecast:
    if (ip, port) not in chromecast_cache:
        cc = pychromecast.get_chromecast_from_host(
            (ip, port, None, None, None)
        )
        cc.wait()
        chromecast_cache[(ip, port)] = cc
    return chromecast_cache[(ip, port)]

def get_chromecast_by_slug(slug):
    if slug not in chromecast_names_cache:
        return None
    ip, port = chromecast_names_cache[slug]
    return get_chromecast(ip, port)

def play_media(chromecast, url, mediaType='audio/mp3'):
    if not chromecast or not url:
        return jsonify({"error": "Invalid device or url"}), 400
    mc = chromecast.media_controller
    mc.play_media(url, mediaType)
    mc.block_until_active()
    return jsonify({"status": "playing", "url": url})

def pause_media(chromecast):
    if not chromecast:
        return jsonify({"error": "Invalid device"}), 400
    chromecast.media_controller.pause()
    return jsonify({"status": "paused"})

def stop_media(chromecast):
    if not chromecast:
        return jsonify({"error": "Invalid device"}), 400
    chromecast.quit_app()
    return jsonify({"status": "stopped"})

def get_volume(chromecast):
    if not chromecast:
        return jsonify({"error": "Invalid device"}), 400
    return jsonify({"volume": chromecast.status.volume_level})

def set_volume(chromecast, volume):
    if not chromecast or volume is None:
        return jsonify({"error": "Invalid device or volume"}), 400
    chromecast.set_volume(float(volume))
    return jsonify({"status": "volume set", "volume": chromecast.status.volume_level})

def adjust_volume(chromecast, delta):
    if not chromecast or delta is None:
        return jsonify({"error": "Invalid device or delta"}), 400
    new_volume = max(0.0, min(1.0, chromecast.status.volume_level + float(delta)))
    chromecast.set_volume(new_volume)
    return jsonify({"status": "volume changed", "volume": chromecast.status.volume_level})

def get_playback_status(chromecast: pychromecast.Chromecast):
    if not chromecast:
        return jsonify({"error": "Invalid device"}), 400
    
    
    status =  "IDLE" if chromecast.is_idle else "PLAYING"
    return jsonify({"status": status})


# --- Sonos helpers ---
def get_sonos_by_slug(slug):
    if slug in sonos_names_cache:
        return sonos_names_cache[slug]
    return None

def get_sonos_volume(device):
    """Return Sonos volume normalized to 0-1."""
    return device.volume / 100.0

def update_device_cache():
    while True:
        logger.info("Updating device cache...")
        chromecasts = get_chromecasts()
        for device in chromecasts:
            ip, port = device["host"], device["port"]
            chromecast_cache[(ip, port)] = get_chromecast(ip, port)
            name_slug = device["friendly_name"].lower().replace(" ", "_")
            chromecast_names_cache[name_slug] = (ip, port)

        logger.info("Updating Sonos cache...")
        sonos_devices = soco.discover() or []
        for device in sonos_devices:
            slug = device.player_name.lower().replace(" ", "_")
            sonos_cache[device.ip_address] = device
            sonos_names_cache[slug] = device
        time.sleep(CACHE_UPDATE_INTERVAL)


# Discover both Chromecast and Sonos devices concurrently
@app.route('/get-devices', methods=['GET'])
def get_devices():
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_chromecast = executor.submit(get_chromecasts)
        future_sonos = executor.submit(get_sonos)
        chromecasts = future_chromecast.result()
        sonos = future_sonos.result()
    devices = chromecasts + sonos
    return jsonify(devices)

# IP/Port endpoints
@app.route('/device/ip/play-url', methods=['POST'])
def play_url_by_ip_port():
    data = request.json
    deviceIP = data.get('deviceIP')
    devicePort = data.get('devicePort')
    cc = get_chromecast(deviceIP, devicePort)
    return play_media(cc, data.get('url'), data.get('mediaType', 'audio/mp3'))

@app.route('/device/ip/pause', methods=['POST'])
def pause_by_ip_port():
    data = request.json
    deviceIP = data.get('deviceIP')
    devicePort = data.get('devicePort')
    cc = get_chromecast(deviceIP, devicePort)
    return pause_media(cc)

@app.route('/device/ip/stop', methods=['POST'])
def stop_by_ip_port():
    data = request.json
    deviceIP = data.get('deviceIP')
    devicePort = data.get('devicePort')
    cc = get_chromecast(deviceIP, devicePort)
    return stop_media(cc)

@app.route('/device/ip/volume', methods=['POST'])
def volume_by_ip_port():
    data = request.json
    deviceIP = data.get('deviceIP')
    devicePort = data.get('devicePort')
    cc = get_chromecast(deviceIP, devicePort)
    return get_volume(cc)

@app.route('/device/ip/volume/set', methods=['POST'])
def set_volume_by_ip_port():
    data = request.json
    deviceIP = data.get('deviceIP')
    devicePort = data.get('devicePort')
    cc = get_chromecast(deviceIP, devicePort)
    return set_volume(cc, data.get('volume'))

@app.route('/device/ip/volume/delta', methods=['POST'])
def volume_delta_by_ip_port():
    data = request.json
    deviceIP = data.get('deviceIP')
    devicePort = data.get('devicePort')
    cc = get_chromecast(deviceIP, devicePort)
    return adjust_volume(cc, data.get('delta'))

@app.route('/device/ip/state', methods=['POST'])
def get_state_by_ip_port():
    data = request.json
    deviceIP = data.get('deviceIP')
    devicePort = data.get('devicePort')

    cc = get_chromecast(deviceIP, devicePort)
    if not cc:
        return jsonify({"error": "Invalid IP or Port"}), 400

    playback_status = get_playback_status(cc)
    volume = get_volume(cc)

    state_data = {
        'status': playback_status.json['status'],
        'volume': volume.json['volume']
    }

    return jsonify(state_data)

# Slug endpoints
@app.route('/device/slug/play-url', methods=['POST'])
def play_url_by_slug():
    data = request.json
    slug = data.get('slug')
    cc = get_chromecast_by_slug(slug)
    if not cc:
        return jsonify({"error": "Invalid slug"}), 400
    return play_media(cc, data.get('url'), data.get('mediaType', 'audio/mp3'))

@app.route('/device/slug/pause', methods=['POST'])
def pause_by_slug():
    data = request.json
    slug = data.get('slug')
    cc = get_chromecast_by_slug(slug)
    if not cc:
        return jsonify({"error": "Invalid slug"}), 400
    return pause_media(cc)

@app.route('/device/slug/stop', methods=['POST'])
def stop_by_slug():
    data = request.json
    slug = data.get('slug')
    cc = get_chromecast_by_slug(slug)
    if not cc:
        return jsonify({"error": "Invalid slug"}), 400
    return stop_media(cc)

@app.route('/device/slug/volume', methods=['POST'])
def volume_by_slug():
    data = request.json
    slug = data.get('slug')
    device_type = data.get('type', 'chromecast')
    if device_type == 'sonos':
        device = get_sonos_by_slug(slug)
        if not device:
            return jsonify({"error": "Invalid slug for Sonos"}), 400
        volume = get_sonos_volume(device)
        return jsonify({"volume": volume})
    else:
        cc = get_chromecast_by_slug(slug)
        if not cc:
            return jsonify({"error": "Invalid slug"}), 400
        return get_volume(cc)

@app.route('/device/slug/volume/set', methods=['POST'])
def set_volume_by_slug():
    data = request.json
    slug = data.get('slug')
    cc = get_chromecast_by_slug(slug)
    if not cc:
        return jsonify({"error": "Invalid slug"}), 400
    return set_volume(cc, data.get('volume'))

@app.route('/device/slug/volume/delta', methods=['POST'])
def volume_delta_by_slug():
    data = request.json
    slug = data.get('slug')
    cc = get_chromecast_by_slug(slug)
    if not cc:
        return jsonify({"error": "Invalid slug"}), 400
    return adjust_volume(cc, data.get('delta'))



@app.route('/device/slug/state', methods=['POST'])
def get_state_by_slug():
    data = request.json
    slug = data.get('slug')

    cc = get_chromecast_by_slug(slug)
    if not cc:
        return jsonify({"error": "Invalid slug"}), 400

    playback_status = get_playback_status(cc)
    volume = get_volume(cc)

    state_data = {
        'status': playback_status.json['status'],
        'volume': volume.json['volume']
    }

    return jsonify(state_data)

def start_device_cache_updater():
    threading.Thread(target=update_device_cache).start()

if __name__ == '__main__':
    logger.info("Starting device control server...")
    # Start the cache updater thread
    start_device_cache_updater()
    app.run(host='0.0.0.0', port=5000)


