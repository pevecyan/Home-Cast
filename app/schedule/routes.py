from flask import Blueprint, request, jsonify

from app import storage

schedule_bp = Blueprint("schedule", __name__, url_prefix="/schedule")


@schedule_bp.route("/alarms", methods=["GET"])
def list_alarms():
    return jsonify(storage.get_alarms())


@schedule_bp.route("/alarms", methods=["POST"])
def create_alarm():
    alarm = storage.add_alarm(request.json or {})
    return jsonify(alarm), 201


@schedule_bp.route("/alarms/<alarm_id>", methods=["GET"])
def get_alarm(alarm_id):
    for a in storage.get_alarms():
        if a["id"] == alarm_id:
            return jsonify(a)
    return jsonify({"error": "Alarm not found"}), 404


@schedule_bp.route("/alarms/<alarm_id>", methods=["PUT"])
def update_alarm(alarm_id):
    updated = storage.update_alarm(alarm_id, request.json or {})
    if not updated:
        return jsonify({"error": "Alarm not found"}), 404
    return jsonify(updated)


@schedule_bp.route("/alarms/<alarm_id>", methods=["DELETE"])
def delete_alarm(alarm_id):
    storage.delete_alarm(alarm_id)
    return jsonify({"status": "deleted"})


@schedule_bp.route("/alarms/<alarm_id>/toggle", methods=["POST"])
def toggle_alarm(alarm_id):
    data = request.get_json(silent=True) or {}
    # Explicit `enabled` wins; otherwise flip the current value.
    if "enabled" in data:
        target = bool(data["enabled"])
    else:
        current = next((a for a in storage.get_alarms() if a["id"] == alarm_id), None)
        if not current:
            return jsonify({"error": "Alarm not found"}), 404
        target = not current.get("enabled", True)
    updated = storage.set_alarm_enabled(alarm_id, target)
    if not updated:
        return jsonify({"error": "Alarm not found"}), 404
    return jsonify(updated)
