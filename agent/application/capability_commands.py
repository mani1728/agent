from __future__ import annotations

from typing import Any

GET_CAPABILITIES = "agent.get_capabilities"
GET_RUNTIME_INFO = "agent.get_runtime_info"



def build_capability_handlers(
    capability_provider: Any,
) -> dict[str, Any]:
    """Build capability discovery command handlers."""

    def get_capabilities(_command: Any) -> Any:
        return {
            "schema_version": "1",
            "capabilities": [
                capability.to_dict()
                for capability in capability_provider.get_capabilities()
            ],
        }

    def get_runtime_info(_command: Any) -> Any:
        return capability_provider.get_runtime_information().to_dict()

    return {
        GET_CAPABILITIES: get_capabilities,
        GET_RUNTIME_INFO: get_runtime_info,
    }


__all__ = ["GET_CAPABILITIES", "GET_RUNTIME_INFO", "build_capability_handlers"]
