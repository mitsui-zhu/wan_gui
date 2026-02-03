import requests

REGION_BASE = {
    "cn-beijing": "https://dashscope.aliyuncs.com",
    "sg": "https://dashscope-intl.aliyuncs.com",
    "us-virginia": "https://dashscope-us.aliyuncs.com",
}

def build_headers(api_key: str) -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        # 固定禁用 DataInspection（与示例一致）
        "X-DashScope-DataInspection": '{"input":"disable","output":"disable"}',
    }

def call_sync(api_key: str, region: str, payload: dict) -> tuple[int, dict | str, dict]:
    url = REGION_BASE[region] + "/api/v1/services/aigc/multimodal-generation/generation"
    headers = build_headers(api_key)
    r = requests.post(url, headers=headers, json=payload, timeout=300)
    try:
        return r.status_code, r.json(), dict(r.headers)
    except Exception:
        return r.status_code, r.text, dict(r.headers)

def extract_image_urls(resp_json: dict) -> list[str]:
    urls = []
    output = resp_json.get("output", {})
    choices = output.get("choices", [])
    for ch in choices:
        msg = ch.get("message", {})
        for item in msg.get("content", []):
            if item.get("type") == "image" and isinstance(item.get("image"), str):
                urls.append(item["image"])
    return urls

def download_images(urls: list[str], out_dir: str) -> list[str]:
    import os
    os.makedirs(out_dir, exist_ok=True)
    saved = []
    for i, u in enumerate(urls, 1):
        r = requests.get(u, timeout=120)
        r.raise_for_status()
        p = os.path.join(out_dir, f"result_{i}.png")
        with open(p, "wb") as f:
            f.write(r.content)
        saved.append(p)
    return saved