import logging

from flask import Blueprint, send_file, jsonify

from app.music.downloader import get_cache

logger = logging.getLogger(__name__)

media_bp = Blueprint("media", __name__, url_prefix="/media")


@media_bp.route("/<video_id>.mp3", methods=["GET"])
def serve_song(video_id):
    logger.info("Media request for: %s", video_id)
    cache = get_cache()
    try:
        path = cache.ensure_song(video_id)
        logger.info("Serving: %s (%d bytes)", path, path.stat().st_size)
    except RuntimeError as e:
        logger.error("Media serve failed: %s", e)
        return jsonify({"error": str(e)}), 500
    return send_file(path, mimetype="audio/mpeg", conditional=True)


@media_bp.route("/<video_id>/info", methods=["GET"])
def song_info(video_id):
    cache = get_cache()
    cached = cache.get_song_path(video_id) is not None
    return jsonify({
        "videoId": video_id,
        "cached": cached,
        "url": cache.get_song_url(video_id),
    })
