import json
import os
import time
import random
import urllib.parse
import urllib.request
from typing import Optional


class VercelBlobClient:
    API_URL = "https://vercel.com/api/blob"
    API_VERSION = "12"

    def __init__(self):
        self.token = (os.getenv("BLOB_READ_WRITE_TOKEN") or "").strip()
        self.store_id = (os.getenv("BLOB_STORE_ID") or "").strip()
        if self.store_id.startswith("store_"):
            self.store_id = self.store_id[len("store_"):]
        if self.token and not self.store_id:
            parts = self.token.split("_")
            if len(parts) >= 4:
                self.store_id = parts[3]

    def is_configured(self) -> bool:
        return bool(self.token and self.store_id)

    def _headers(self, content_type: Optional[str] = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "x-api-version": self.API_VERSION,
            "x-vercel-blob-store-id": self.store_id,
            "x-api-blob-request-id": f"{self.store_id}:{int(time.time() * 1000)}:{random.random():.12f}",
            "x-api-blob-request-attempt": "0",
        }
        if content_type:
            headers["content-type"] = content_type
        return headers

    def put(self, pathname: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
        query = urllib.parse.urlencode({"pathname": pathname})
        headers = self._headers()
        headers.update({
            "x-vercel-blob-access": "private",
            "x-content-type": content_type,
            "x-allow-overwrite": "1",
        })
        request = urllib.request.Request(
            f"{self.API_URL}/?{query}",
            data=data,
            headers=headers,
            method="PUT",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    def get(self, pathname: str) -> bytes:
        quoted_path = "/".join(urllib.parse.quote(part) for part in pathname.split("/"))
        url = f"https://{self.store_id}.private.blob.vercel-storage.com/{quoted_path}?cache=0"
        request = urllib.request.Request(
            url,
            headers=self._headers(),
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()

    def delete(self, pathname: str) -> None:
        payload = json.dumps({"urls": [pathname]}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.API_URL}/delete",
            data=payload,
            headers=self._headers("application/json"),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            response.read()


vercel_blob_client = VercelBlobClient()
