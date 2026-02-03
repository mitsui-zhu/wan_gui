import json
import os
from pathlib import Path

APP_NAME = "WanImageGUI"

def _app_config_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / APP_NAME

    mac_app_support = Path.home() / "Library" / "Application Support"
    if mac_app_support.exists():
        return mac_app_support / APP_NAME

    return Path.home() / ".config" / APP_NAME

def config_path() -> Path:
    d = _app_config_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "config.json"

def load_config() -> dict:
    p = config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_config(cfg: dict) -> None:
    p = config_path()
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")