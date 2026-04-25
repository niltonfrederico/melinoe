"""SeaweedFS Filer client for uploading files via the REST HTTP API."""

from dataclasses import dataclass
from pathlib import Path

import httpx

from melinoe.logger import workflow_log


@dataclass(frozen=True)
class UploadResult:
    remote_path: str
    url: str


class SeaweedFSClient:
    def __init__(self, filer_url: str, public_url: str | None = None) -> None:
        self._filer_url = filer_url.rstrip("/")
        self._public_url = (public_url or filer_url).rstrip("/")

    def upload(self, path: Path, remote_path: str) -> UploadResult:
        remote_path = remote_path.lstrip("/")
        upload_url = f"{self._filer_url}/{remote_path}"
        public_url = f"{self._public_url}/{remote_path}"
        content_type = _mime_for(path.suffix)
        with httpx.Client(timeout=30) as client, path.open("rb") as f:
            response = client.put(upload_url, content=f.read(), headers={"Content-Type": content_type})
        response.raise_for_status()
        workflow_log.info("SeaweedFS ← %s (%s)", remote_path, response.status_code)
        return UploadResult(remote_path=remote_path, url=public_url)

    def delete_directory(self, remote_path: str) -> None:
        remote_path = remote_path.strip("/")
        url = f"{self._filer_url}/{remote_path}"
        with httpx.Client(timeout=30) as client:
            response = client.delete(url, params={"recursive": "true", "ignoreRecursiveError": "true"})
        if response.status_code not in (200, 204, 404):
            response.raise_for_status()
        workflow_log.info("SeaweedFS ← deleted directory /%s (%s)", remote_path, response.status_code)


_MIME_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _mime_for(suffix: str) -> str:
    return _MIME_TYPES.get(suffix.lower(), "application/octet-stream")
