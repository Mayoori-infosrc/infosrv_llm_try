# core/state_backend.py
import json
import os
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError

from core.utils import logger


class S3StateBackend:
    """
    Stores generator pipeline state in an S3 object, Terraform-style.

    Environment variables:
      - LLMOPS_STATE_BUCKET (required)
      - LLMOPS_STATE_KEY (optional, default: "llmops/state.json")
    """

    def __init__(self, bucket: Optional[str] = None, key: Optional[str] = None):
        self.bucket = bucket or os.getenv("LLMOPS_STATE_BUCKET")
        self.key = key or os.getenv("LLMOPS_STATE_KEY", "llmops/state.json")

        if not self.bucket:
            raise RuntimeError(
                "LLMOPS_STATE_BUCKET must be set for S3StateBackend "
                "(or provide bucket explicitly)."
            )

        self.s3 = boto3.client("s3")

    def load_state(self, fallback_key: Optional[str] = None) -> Dict[str, Any]:
        key = fallback_key or self.key
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
            body = resp["Body"].read().decode("utf-8") or "{}"
            state = json.loads(body)
            if not isinstance(state, dict):
                logger.warning("State file is not a dict, resetting to empty.")
                return {}
            return state
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "NoSuchBucket"):
                logger.info("No existing state found in S3 (bucket=%s, key=%s).", self.bucket, key)
                return {}
            raise

    def save_state(self, state: Dict[str, Any], fallback_key: Optional[str] = None) -> None:
        key = fallback_key or self.key
        data = json.dumps(state, indent=2, sort_keys=True)
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data.encode("utf-8"),
            ContentType="application/json",
        )
        logger.info("State saved to S3 (bucket=%s, key=%s).", self.bucket, key)


class LocalStateBackend:
    """
    Simple local JSON file backend for running the generator without AWS.
    Uses .llmops/state.json in the repo root.
    """

    def __init__(self, path: str = ".llmops/state.json"):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def load_state(self, *_args, **_kwargs) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                logger.warning("Corrupted local state file, resetting.")
                return {}

    def save_state(self, state: Dict[str, Any], *_args, **_kwargs) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, sort_keys=True)
        logger.info("State saved locally at %s", self.path)


def get_state_backend() -> Any:
    """
    Factory that returns S3StateBackend when S3 is configured,
    otherwise falls back to LocalStateBackend.
    """
    if os.getenv("LLMOPS_STATE_BUCKET"):
        return S3StateBackend()
    logger.warning("LLMOPS_STATE_BUCKET not set; using local state backend.")
    return LocalStateBackend()
