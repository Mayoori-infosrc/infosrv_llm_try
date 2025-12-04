# providers/mcp/interface.py
from abc import ABC, abstractmethod
from typing import Dict, Any


class MCPInterface(ABC):
    """
    Minimal interface for MCP provisioning.

    Not yet wired into the engine, but ready for future use.
    """

    @abstractmethod
    def provision_mcp(self, config: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def destroy_mcp(self, identifier: str) -> None:
        raise NotImplementedError
