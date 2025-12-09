# deploy/repo_manager.py
import base64
import os
import time
from typing import Dict, Any, Optional

import requests

from core.utils import logger

GITHUB_API = "https://api.github.com"

# Exclude fragments (if any of these substrings appear in the repo-relative path, skip the file)
EXCLUDE_PATH_FRAGMENTS = {
    "__pycache__",
    ".pytest_cache",
    ".git",                # exclude .git folder
    ".DS_Store",
    # If you want to exclude the generator workflow (source repo), list it exactly:
    ".github/workflows/generator.yml",
}


def is_text_file(path: str) -> bool:
    """Return True if we can read a chunk as UTF-8 text; False if binary or unreadable as text."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            f.read(2048)
        return True
    except Exception:
        return False


class RepoManager:
    """
    GitHub Repository Manager (robust).

    - normalizes paths (forward slashes)
    - uploads text and binary files safely
    - supports org/user repo creation
    - supports adding repository secrets
    """

    def __init__(self, owner: Optional[str] = None, token: Optional[str] = None):
        self.owner = owner or os.getenv("GITHUB_REPOSITORY_OWNER")
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.api_url = GITHUB_API

        if not self.owner:
            raise RuntimeError("GITHUB_REPOSITORY_OWNER not configured")
        if not self.token:
            raise RuntimeError("GITHUB_TOKEN not configured")

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }

    # Internal request wrapper
    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        url = f"{self.api_url}{endpoint}"
        resp = requests.request(method, url, headers=self._headers, **kwargs)

        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            raise RuntimeError("GitHub API Rate Limit reached. Slow down or add delays.")

        if resp.status_code >= 400:
            raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text}")

        return resp

    # Org vs user
    def is_org(self) -> bool:
        resp = self._request("GET", f"/users/{self.owner}")
        return resp.json().get("type") == "Organization"

    # Ensure repo exists
    def ensure_repo(self, repo_name: str, private: bool = True, description: str = "") -> Dict[str, Any]:
        # Quick check using GET
        resp = requests.get(f"{self.api_url}/repos/{self.owner}/{repo_name}", headers=self._headers)
        if resp.status_code == 200:
            logger.info("Repository exists: %s/%s", self.owner, repo_name)
            return resp.json()
        if resp.status_code != 404:
            raise RuntimeError(f"GitHub error retrieving repo: {resp.status_code}: {resp.text}")

        payload = {
            "name": repo_name,
            "private": private,
            "description": description,
            "auto_init": False,
        }
        endpoint = f"/orgs/{self.owner}/repos" if self.is_org() else "/user/repos"
        resp = self._request("POST", endpoint, json=payload)
        logger.info("Repository created: %s", resp.json().get("html_url"))
        return resp.json()

    # Upload single file
    def upload_file(self, repo_name: str, path: str, content: bytes | str, message: str = "Add file") -> Dict[str, Any]:
        # Normalize path to forward slashes and remove only a leading './' or leading '/'
        norm_path = path.replace("\\", "/")
        if norm_path.startswith("./"):
            norm_path = norm_path[2:]
        elif norm_path.startswith("/"):
            norm_path = norm_path[1:]
        endpoint = f"/repos/{self.owner}/{repo_name}/contents/{norm_path}"

        # Check existing file to include sha in update
        resp = requests.get(f"{self.api_url}{endpoint}", headers=self._headers)
        sha = resp.json().get("sha") if resp.status_code == 200 else None

        # Encode content safely
        if isinstance(content, str):
            encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        else:
            encoded = base64.b64encode(content).decode("ascii")

        payload = {"message": message, "content": encoded}
        if sha:
            payload["sha"] = sha

        # Try with a couple retries for transient issues
        for attempt in range(3):
            resp = self._request("PUT", endpoint, json=payload)
            if resp.status_code in (200, 201):
                return resp.json()
            time.sleep(0.2)
        return resp.json()

    # Upload template folder safely
    def upload_template_folder(self, repo_name: str, folder: str) -> None:
        folder = os.path.abspath(folder)
        if not os.path.isdir(folder):
            raise FileNotFoundError(f"Templates folder does not exist: {folder}")

        logger.info("Uploading template files from: %s", folder)

        discovered = []
        for root, dirs, files in os.walk(folder):
            # keep dot-folders (like .github) unless an exact path part matches exclude fragments
            new_dirs = []
            for d in dirs:
                rel_dir = os.path.join(os.path.relpath(root, folder), d).replace(os.path.sep, "/")
                parts = [p for p in rel_dir.split("/") if p]
                if any(part in EXCLUDE_PATH_FRAGMENTS for part in parts):
                    logger.debug("Excluding directory from traversal: %s", rel_dir)
                    continue
                new_dirs.append(d)
            dirs[:] = new_dirs

            for filename in files:
                full_path = os.path.join(root, filename)
                # Build repo-relative path and normalize separators to forward slashes
                rel_path = os.path.relpath(full_path, folder).replace(os.path.sep, "/")
                rel_path = rel_path.replace("\\", "/")  # defend against literal backslashes in names

                # Skip files whose any path segment matches an excluded fragment
                parts = [p for p in rel_path.split("/") if p]
                if any(part in EXCLUDE_PATH_FRAGMENTS for part in parts):
                    logger.debug("Skipping excluded file: %s", rel_path)
                    continue

                discovered.append(rel_path)
                logger.info("Uploading: %s", rel_path)

                # Read content as text or binary
                if is_text_file(full_path):
                    with open(full_path, "r", encoding="utf-8") as fh:
                        content = fh.read()
                else:
                    with open(full_path, "rb") as fh:
                        content = fh.read()

                # Upload to GitHub
                self.upload_file(repo_name, rel_path, content, message=f"Add template file {rel_path}")

                # gentle rate-limit avoidance
                time.sleep(0.15)

        if not discovered:
            logger.warning("No template files discovered in %s", folder)

    # backward-compatible alias
    def push_templates(self, repo_name: str, folder: str) -> None:
        self.upload_template_folder(repo_name, folder)

    # -------------------------
    # GitHub Secrets Helpers
    # -------------------------
    def _get_repo_public_key(self, repo_name: str) -> Dict[str, Any]:
        endpoint = f"/repos/{self.owner}/{repo_name}/actions/secrets/public-key"
        resp = self._request("GET", endpoint)
        return resp.json()

    def _encrypt_secret(self, public_key: str, secret_value: str) -> str:
        try:
            import nacl.encoding
            import nacl.public
        except Exception as e:
            raise RuntimeError("PyNaCl is required to encrypt GitHub secrets. Install with `pip install pynacl`") from e

        pk = nacl.public.PublicKey(public_key.encode("utf-8"), encoder=nacl.encoding.Base64Encoder)
        sealed_box = nacl.public.SealedBox(pk)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")

    def add_secret(self, repo_name: str, secret_name: str, secret_value: str) -> None:
        key_info = self._get_repo_public_key(repo_name)
        encrypted_value = self._encrypt_secret(key_info["key"], secret_value)
        payload = {"encrypted_value": encrypted_value, "key_id": key_info["key_id"]}
        endpoint = f"/repos/{self.owner}/{repo_name}/actions/secrets/{secret_name}"
        self._request("PUT", endpoint, json=payload)
        logger.info("Secret '%s' added to repo %s/%s.", secret_name, self.owner, repo_name)
