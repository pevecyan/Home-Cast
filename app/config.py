import os
import yaml


_defaults = {
    "hostname": "http://localhost:5000",
    "port": 5000,
    "cast_app_id": None,
    "cache": {
        "ttl": 3600,
        "dir": "./cache",
    },
}


def load_config(path="config.yaml"):
    config = dict(_defaults)
    if os.path.exists(path):
        with open(path) as f:
            user = yaml.safe_load(f) or {}
        # merge top-level keys
        for key, val in user.items():
            if isinstance(val, dict) and isinstance(config.get(key), dict):
                config[key] = {**config[key], **val}
            else:
                config[key] = val
    # environment variable overrides
    if os.environ.get("APP_HOSTNAME"):
        config["hostname"] = os.environ["APP_HOSTNAME"]
    if os.environ.get("APP_PORT"):
        config["port"] = int(os.environ["APP_PORT"])
    if os.environ.get("APP_CACHE_DIR"):
        config["cache"]["dir"] = os.environ["APP_CACHE_DIR"]
    return config
