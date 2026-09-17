from __future__ import annotations

from typing import Any



def build_capability_handlers(
    capability_provider: Any,
) -> dict[str, Any]:
    """Build v0.1.0 capability discovery command handlers."""

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
        "agent.get_capabilities": get_capabilities,
        "agent.get_runtime_info": get_runtime_info,
    }


__all__ = ["build_capability_handlers"]
