from abc import ABC, abstractmethod
from typing import Dict, Any


class ObservabilityProvider(ABC):
    """
    Abstract base for providers (Phoenix, Datadog, etc).
    """

    @abstractmethod
    def ensure_project(self) -> str:
        """
        Ensure project exists; return a canonical project_id string.
        """
        raise NotImplementedError

    @abstractmethod
    def send_trace(self, trace_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send trace payload; return provider response or raise on error.
        """
        raise NotImplementedError

    @abstractmethod
    def send_test_trace(self) -> Dict[str, Any]:
        """
        Send a small test trace for validation (used by the generated repo).
        """
        raise NotImplementedError
