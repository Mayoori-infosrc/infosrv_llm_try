import os
import glob
import yaml
import requests
from core.utils import logger

def upload_prompt(prompt_path, project_id, base_url=None, api_key=None):
    base = (base_url or os.environ.get("PHOENIX_BASE_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("PHOENIX_BASE_URL required")
    headers = {"Content-Type": "application/json"}
    with open(prompt_path, "r", encoding="utf-8") as f:
        p = yaml.safe_load(f)
    payload = {"id": p.get("id") or p.get("name") or None,
               "description": p.get("description"),
               "prompt": p.get("prompt") or p.get("content") or ""}
    url = f"{base}/v1/projects/{project_id}/prompts"
    r = requests.post(url, json=payload, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()

def sync_prompts(prompts_folder, project_id, base_url=None, api_key=None):
    folder = prompts_folder or "src/llm/prompts"
    files = glob.glob(folder + "/*.yaml") + glob.glob(folder + "/*.yml")
    uploaded = []
    for f in files:
        try:
            uploaded.append(upload_prompt(f, project_id, base_url=base_url, api_key=api_key))
            logger.info("Uploaded prompt: %s", f)
        except Exception as e:
            logger.warning("Failed uploading prompt %s: %s", f, e)
    return uploaded
