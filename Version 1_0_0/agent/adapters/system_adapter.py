# Path: Version 1_0_0/agent/adapters/system_adapter.py

"""System adapter.

This module provides a small abstraction boundary for system-level
information required by the Agent.

Responsibilities
----------------
- Provide basic host/platform information.
- Provide process/runtime information.
- Keep direct standard-library system access outside the core layer.

This module intentionally does not implement:
- Windows Service management
- process termination
- service installation/removal
- configuration management
- logging configuration
- transport
- persistence
- security
"""

from __future__ import annotations

import os
import platform
import socket
import sys
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SystemInfo:
    """Basic information about the host running the Agent."""

    hostname: str
    platform: str
    platform_release: str
    architecture: str
    python_version: str
    process_id: int

    def to_dict(self) -> dict[str, Any]:
        """Convert system information to a serializable dictionary."""
        return {
            "hostname": self.hostname,
            "platform": self.platform,
            "platform_release": self.platform_release,
            "architecture": self.architecture,
            "python_version": self.python_version,
            "process_id": self.process_id,
        }


class SystemAdapter:
    """Adapter for basic operating-system/runtime information."""

    # ------------------------------------------------------------------
    # Host information
    # ------------------------------------------------------------------

    def get_hostname(self) -> str:
        """Return the current host name."""
        return socket.gethostname()

    def get_platform(self) -> str:
        """Return the operating-system/platform name."""
        return platform.system()

    def get_platform_release(self) -> str:
        """Return the operating-system release."""
        return platform.release()

    def get_architecture(self) -> str:
        """Return the host architecture."""
        return platform.machine()

    def get_python_version(self) -> str:
        """Return the running Python version."""
        return platform.python_version()

    # ------------------------------------------------------------------
    # Process information
    # ------------------------------------------------------------------

    def get_process_id(self) -> int:
        """Return the current process ID."""
        return os.getpid()

    # ------------------------------------------------------------------
    # Aggregate information
    # ------------------------------------------------------------------

    def get_system_info(self) -> SystemInfo:
        """Return a snapshot of basic system information."""
        return SystemInfo(
            hostname=self.get_hostname(),
            platform=self.get_platform(),
            platform_release=self.get_platform_release(),
            architecture=self.get_architecture(),
            python_version=self.get_python_version(),
            process_id=self.get_process_id(),
        )

    def get_system_info_dict(self) -> dict[str, Any]:
        """Return system information as a dictionary."""
        return self.get_system_info().to_dict()

    # ------------------------------------------------------------------
    # Runtime information
    # ------------------------------------------------------------------

    def get_runtime_info(self) -> Mapping[str, Any]:
        """Return basic Agent runtime information."""
        return {
            "pid": self.get_process_id(),
            "python_version": self.get_python_version(),
            "executable": sys.executable,
            "argv": list(sys.argv),
        }

    # ------------------------------------------------------------------
    # Capability helpers
    # ------------------------------------------------------------------

    def is_windows(self) -> bool:
        """Return True when the Agent is running on Windows."""
        return platform.system().lower() == "windows"

    def is_linux(self) -> bool:
        """Return True when the Agent is running on Linux."""
        return platform.system().lower() == "linux"

    def is_macos(self) -> bool:
        """Return True when the Agent is running on macOS."""
        return platform.system().lower() == "darwin"


__all__ = [
    "SystemInfo",
    "SystemAdapter",
]