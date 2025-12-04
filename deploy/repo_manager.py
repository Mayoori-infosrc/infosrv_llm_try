# deploy/repo_manager.py
import base64
import os
import time
from typing import Dict, Any, List

import requests

from core.utils import logger

GITHUB_API = "https://api.github.com"


class RepoManager:
    """
    Simple GitHub repository manager for the generator pipeline.

    Requires:
      - GITHUB_TOKEN
      - GITHUB_REPOSITORY_OWNER
    """

    def __init__(self, token: str = None, owner: str = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.owner = owner or os.getenv("GITHUB_REPOSITORY_OWNER")

        if not self.token:
            raise RuntimeError("GITHUB_TOKEN required")
        if not self.owner:
            raise RuntimeError("GITHUB_REPOSITORY_OWNER required")

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{GITHUB_API}{path}"
        resp = requests.request(method, url, headers=self._headers, **kwargs)
        if resp.status_code >= 400:
            raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text}")
        return resp

    def repo_exists(self, repo_name: str) -> bool:
        try:
            self._request("GET", f"/repos/{self.owner}/{repo_name}")
            return True
        except Exception:
            return False

    def create_repo(self, repo_name: str, private: bool = True, description: str = "") -> Dict[str, Any]:
        if self.repo_exists(repo_name):
            logger.info("Repository already exists: %s/%s", self.owner, repo_name)
            resp = self._request("GET", f"/repos/{self.owner}/{repo_name}")
            return resp.json()

        payload = {
            "name": repo_name,
            "private": private,
            "description": description,
            "auto_init": False,
        }
        logger.info("Creating GitHub repository: %s/%s", self.owner, repo_name)
        resp = self._request("POST", f"/orgs/{self.owner}/repos", json=payload)
        return resp.json()

    def ensure_repo(self, repo_name: str, private: bool = True, description: str = "") -> Dict[str, Any]:
        """
        Idempotent: returns existing repo or creates a new one.
        """
        if self.repo_exists(repo_name):
            logger.info("Repository already exists: %s/%s", self.owner, repo_name)
            resp = self._request("GET", f"/repos/{self.owner}/{repo_name}")
            return resp.json()
        return self.create_repo(repo_name, private=private, description=description)

    def upload_file(self, repo_name: str, path: str, content: str, message: str = "") -> None:
        """
        Creates or updates a file in the given repo using the GitHub Contents API.
        """
        b64_content = base64.b64encode(content.encode("utf-8")).decode("ascii")
        api_path = f"/repos/{self.owner}/{repo_name}/contents/{path}"

        # Check if file exists to fetch its SHA for update
        sha = None
        resp = requests.get(f"{GITHUB_API}{api_path}", headers=self._headers)
        if resp.status_code == 200:
            sha = resp.json().get("sha")

        payload: Dict[str, Any] = {
            "message": message or f"Update {path}",
            "content": b64_content,
        }
        if sha:
            payload["sha"] = sha

        logger.debug("Uploading file to GitHub: %s/%s@%s", self.owner, repo_name, path)
        self._request("PUT", api_path, json=payload)

    def push_templates(self, repo_name: str, templates_dir: str) -> None:
        """
        Uploads all files in templates_dir (recursively) into the target repo.

        The folder structure under templates_dir is preserved.
        """
        templates_dir = os.path.abspath(templates_dir)
        if not os.path.isdir(templates_dir):
            raise FileNotFoundError(f"Templates folder not found: {templates_dir}")

        logger.info("Pushing templates from %s to %s/%s", templates_dir, self.owner, repo_name)

        files: List[str] = []
        for root, dirs, file_names in os.walk(templates_dir):
            for f in file_names:
                full = os.path.join(root, f)
                files.append(full)

        for f in files:
            rel = os.path.relpath(f, templates_dir)
            rel_posix = rel.replace(os.path.sep, "/")

            with open(f, "r", encoding="utf-8") as fh:
                content = fh.read()

            logger.info("Uploading template file: %s", rel_posix)
            self.upload_file(repo_name, rel_posix, content, message=f"Add template {rel_posix}")
            time.sleep(0.15)  # small delay to avoid rate limits
