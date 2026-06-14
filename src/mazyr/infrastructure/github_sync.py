import base64
import json
from datetime import datetime
from typing import Optional

import httpx

from mazyr.infrastructure.http_pool import get_sync_client
from mazyr.infrastructure.retry import retry_github


class GitHubSyncAdapter:
    """Sync memory snapshots to GitHub repository."""

    def __init__(
        self,
        token: str,
        repo: str,
        branch: str = "main",
        client: httpx.Client | None = None,
    ):
        self.token = token
        self.repo = repo
        self.branch = branch
        self.client = client or get_sync_client()
        self._headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    @retry_github
    def push_snapshot(self, snapshot: dict, path: str = "snapshots") -> dict:
        timestamp = datetime.now().isoformat()
        filename = f"{path}/snapshot_{timestamp}.json"
        content = json.dumps(snapshot, indent=2)
        content_b64 = base64.b64encode(content.encode()).decode()

        sha = self._get_file_sha(filename)

        payload = {
            "message": f"Memory snapshot {timestamp}",
            "content": content_b64,
            "branch": self.branch,
        }
        if sha:
            payload["sha"] = sha

        response = self.client.put(
            f"https://api.github.com/repos/{self.repo}/contents/{filename}",
            headers=self._headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    @retry_github
    def _get_file_sha(self, path: str) -> Optional[str]:
        response = self.client.get(
            f"https://api.github.com/repos/{self.repo}/contents/{path}",
            headers=self._headers,
            params={"ref": self.branch},
        )
        if response.status_code == 200:
            return response.json().get("sha")
        return None
