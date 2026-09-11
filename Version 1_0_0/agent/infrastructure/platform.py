# Path: Version 1_0_0/agent/infrastructure/platform.py

from __future__ import annotations

import os
import platform as _platform
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PlatformInfo:
    system: str
    release: str
    version: str
    machine: str
    processor: str
    python_version: str
    is_windows: bool
    is_linux: bool
    is_macos: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "system": self.system,
            "release": self.release,
            "version": self.version,
            "machine": self.machine,
            "processor": self.processor,
            "python_version": self.python_version,
            "is_windows": self.is_windows,
            "is_linux": self.is_linux,
            "is_macos": self.is_macos,
        }


class Platform:
    """
    Small platform abstraction.

    This class exposes operating-system information without introducing
    Windows Service or process-management behavior.
    """

    @staticmethod
    def system() -> str:
        return _platform.system()

    @staticmethod
    def release() -> str:
        return _platform.release()

    @staticmethod
    def version() -> str:
        return _platform.version()

    @staticmethod
    def machine() -> str:
        return _platform.machine()

    @staticmethod
    def processor() -> str:
        return _platform.processor()

    @staticmethod
    def python_version() -> str:
        return sys.version.split()[0]

    @staticmethod
    def process_id() -> int:
        return os.getpid()

    @classmethod
    def info(cls) -> PlatformInfo:
        system = cls.system().lower()

        return PlatformInfo(
            system=cls.system(),
            release=cls.release(),
            version=cls.version(),
            machine=cls.machine(),
            processor=cls.processor(),
            python_version=cls.python_version(),
            is_windows=system == "windows",
            is_linux=system == "linux",
            is_macos=system in {"darwin", "macos"},
        )

    @classmethod
    def info_dict(cls) -> dict[str, object]:
        return cls.info().to_dict()

    @classmethod
    def is_windows(cls) -> bool:
        return cls.system().lower() == "windows"

    @classmethod
    def is_linux(cls) -> bool:
        return cls.system().lower() == "linux"

    @classmethod
    def is_macos(cls) -> bool:
        return cls.system().lower() in {"darwin", "macos"}

    @staticmethod
    def environment(name: str, default: Optional[str] = None) -> Optional[str]:
        if not name:
            raise ValueError("Environment variable name cannot be empty.")

        return os.environ.get(name, default)


def is_windows() -> bool:
    return Platform.is_windows()


def is_linux() -> bool:
    return Platform.is_linux()


def is_macos() -> bool:
    return Platform.is_macos()


def get_platform_info() -> PlatformInfo:
    return Platform.info()


__all__ = [
    "Platform",
    "PlatformInfo",
    "get_platform_info",
    "is_windows",
    "is_linux",
    "is_macos",
]