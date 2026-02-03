import json
from pathlib import Path
from datetime import datetime

def create_run_dir(base_dir: str) -> Path:
    base = Path(base_dir).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = base / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "input_images").mkdir(exist_ok=True)
    return run_dir

def save_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def append_text(path: Path, text: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)

def copy_input_images(run_dir: Path, image_paths: list[str]) -> None:
    inp = run_dir / "input_images"
    for p in image_paths:
        try:
            src = Path(p)
            if src.exists():
                dst = inp / src.name
                if not dst.exists():
                    dst.write_bytes(src.read_bytes())
        except Exception:
            pass