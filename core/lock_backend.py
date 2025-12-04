# core/lock_backend.py
import os
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from core.utils import logger


class DynamoLock:
    """
    DynamoDB-based distributed lock.

    Prevents multiple GitHub generator pipelines from running at the same time.

    Environment:
      - LLMOPS_LOCK_TABLE (required unless table_name is passed)
    """

    def __init__(
        self,
        table_name: Optional[str] = None,
        lock_id: str = "llmops-generator-lock",
        ttl_seconds: int = 120,
    ):
        self.table_name = table_name or os.getenv("LLMOPS_LOCK_TABLE")
        if not self.table_name:
            raise RuntimeError(
                "LLMOPS_LOCK_TABLE must be set for DynamoLock "
                "(or provide table_name explicitly)."
            )

        self.lock_id = lock_id
        self.ttl_seconds = ttl_seconds

        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)

    def acquire(self, wait_seconds: int = 60, poll_interval: int = 5) -> bool:
        """
        Try to acquire the lock. Blocks up to wait_seconds.
        Returns True if acquired, False otherwise.
        """
        deadline = time.time() + wait_seconds

        while True:
            now = int(time.time())
            expires_at = now + self.ttl_seconds
            try:
                # Either lock does not exist, or it is expired.
                self.table.put_item(
                    Item={"LockID": self.lock_id, "ExpiresAt": expires_at},
                    ConditionExpression="attribute_not_exists(LockID) OR ExpiresAt < :now",
                    ExpressionAttributeValues={":now": now},
                )
                logger.info("Lock acquired (table=%s, lock_id=%s)", self.table_name, self.lock_id)
                return True
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code")
                if code != "ConditionalCheckFailedException":
                    logger.error("Lock acquire failed with unexpected error: %s", e)
                    raise

                if time.time() >= deadline:
                    logger.error(
                        "Failed to acquire lock %s within %s seconds.",
                        self.lock_id,
                        wait_seconds,
                    )
                    return False

                logger.info("Lock is currently held; retrying in %s seconds...", poll_interval)
                time.sleep(poll_interval)

    def release(self) -> None:
        try:
            self.table.delete_item(Key={"LockID": self.lock_id})
            logger.info("Lock released (lock_id=%s)", self.lock_id)
        except Exception as e:
            logger.error("Failed to release lock %s: %s", self.lock_id, e)


class NoopLock:
    """
    Fallback lock that does nothing (for local dev without DynamoDB).
    """

    def acquire(self, *_, **__) -> bool:
        logger.warning("NoopLock used; no distributed locking in effect.")
        return True

    def release(self) -> None:
        logger.warning("NoopLock release called; no-op.")


def get_lock_backend() -> object:
    """
    Factory that returns DynamoLock when LLMOPS_LOCK_TABLE is configured,
    otherwise a no-op lock.
    """
    if os.getenv("LLMOPS_LOCK_TABLE"):
        return DynamoLock()
    logger.warning("LLMOPS_LOCK_TABLE not set; using NoopLock.")
    return NoopLock()
