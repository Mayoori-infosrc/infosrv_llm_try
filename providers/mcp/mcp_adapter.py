# providers/mcp/mcp_adapter.py
from typing import Dict, Any

from providers.mcp.interface import MCPInterface


class DummyMCPAdapter(MCPInterface):
    """
    Placeholder implementation. In future, this will provision MCP infra.
    """

    def provision_mcp(self, config: Dict[str, Any]) -> Dict[str, Any]:
        # For now, just echo the config.
        return {"status": "noop", "config": config}

    def destroy_mcp(self, identifier: str) -> None:
        # No-op for now.
        return None
