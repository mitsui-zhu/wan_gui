import base64
import mimetypes
from pathlib import Path

def guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"

def file_to_data_url(path: str) -> str:
    p = Path(path)
    mime = guess_mime(str(p))
    b = p.read_bytes()
    b64 = base64.b64encode(b).decode("utf-8")
    return f"data:{mime};base64,{b64}"