"""Retail domain configuration — store settings, zones, hours."""

import json
from pathlib import Path

RETAIL_CONFIGS_DIR = Path(__file__).parent.parent.parent / "configs" / "retail"


def _ensure_dir():
    RETAIL_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)


def save_store_config(store_id: str, config: dict) -> dict:
    """Save configuration for a retail location."""
    _ensure_dir()
    config["store_id"] = store_id
    config.setdefault("name", store_id)
    config.setdefault("capacity", 0)
    config.setdefault("operating_hours", {"open": "08:00", "close": "22:00"})
    config.setdefault("zones", [])
    config.setdefault("pos_system", "generic")
    config.setdefault("alerts", {
        "over_capacity": True,
        "long_queue": True,
        "queue_threshold": 5,
    })

    path = RETAIL_CONFIGS_DIR / f"{store_id}.json"
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    return config


def get_store_config(store_id: str) -> dict | None:
    """Get configuration for a retail location."""
    _ensure_dir()
    path = RETAIL_CONFIGS_DIR / f"{store_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def list_store_configs() -> list[dict]:
    """List all store configurations."""
    _ensure_dir()
    configs = []
    for f in RETAIL_CONFIGS_DIR.glob("*.json"):
        with open(f) as fh:
            data = json.load(fh)
        configs.append({
            "store_id": data.get("store_id", f.stem),
            "name": data.get("name", f.stem),
            "capacity": data.get("capacity", 0),
            "pos_system": data.get("pos_system", "generic"),
            "zones": len(data.get("zones", [])),
        })
    return configs
