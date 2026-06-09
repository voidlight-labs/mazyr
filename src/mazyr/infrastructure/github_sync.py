import json
import base64
from datetime import datetime
from typing import Optional
import httpx


class GitHubSyncAdapter:
    """Sync memory snapshots to GitHub repository."""

    def __init__(self, token: str, repo: str, branch: str = "main"):
        self.token = token
        self.repo = repo
        self.branch = branch
        self.client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )

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
            f"/repos/{self.repo}/contents/{filename}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def _get_file_sha(self, path: str) -> Optional[str]:
        response = self.client.get(
            f"/repos/{self.repo}/contents/{path}",
            params={"ref": self.branch},
        )
        if response.status_code == 200:
            return response.json().get("sha")
        return None
