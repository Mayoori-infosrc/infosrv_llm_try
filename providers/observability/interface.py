# providers/observability/interface.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class ObservabilityInterface(ABC):
    """
    Pluggable observability provider interface (Phoenix, Datadog, etc.)
    """

    @abstractmethod
    def create_project(self, name: str, description: str = "") -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_projects(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_project(self, project_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def delete_project(self, project_id: str) -> None:
        raise NotImplementedError
