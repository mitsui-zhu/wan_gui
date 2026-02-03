import time
import os
import mimetypes
import oss2
from oss2.credentials import StaticCredentialsProvider

def upload_and_presign_get(
    endpoint: str,
    bucket_name: str,
    access_key_id: str,
    access_key_secret: str,
    local_path: str,
    expires_sec: int,
    object_prefix: str = "wan_tmp/"
) -> tuple[str, str]:
    provider = StaticCredentialsProvider(access_key_id, access_key_secret)
    auth = oss2.ProviderAuth(provider)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    ts = int(time.time())
    base = os.path.basename(local_path)
    object_key = f"{object_prefix}{ts}_{base}"

    content_type, _ = mimetypes.guess_type(local_path)
    headers = {}
    if content_type:
        headers["Content-Type"] = content_type

    bucket.put_object_from_file(object_key, local_path, headers=headers)
    signed_url = bucket.sign_url("GET", object_key, expires_sec)
    return object_key, signed_url