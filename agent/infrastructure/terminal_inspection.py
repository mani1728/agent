"""Inspection only: never initialize MT5, read accounts or launch a terminal.

The vendor's initialize() auto-discovery has no inspection-only API. This
bounded Windows inventory is shared by diagnostics and startup telemetry; it
is advisory and does not change initialize()'s automatic terminal selection.
"""
import csv
import importlib
import io
import os
from pathlib import Path
import subprocess
import sys
from dataclasses import dataclass, asdict


TERMINAL_NAMES = ("terminal64.exe", "terminal.exe", "metatrader64.exe", "metatrader.exe")


@dataclass(frozen=True)
class TerminalInspection:
    supported: bool
    paths: tuple[str, ...] = ()
    process_running: bool | None = None
    dependency_available: bool = False
    errors: tuple[str, ...] = ()
    searched_locations: tuple[str, ...] = ()

    def to_dict(self):
        return asdict(self)


def dependency_available():
    try:
        module = importlib.import_module("MetaTrader5")
        return all(callable(getattr(module, name, None))
                   for name in ("initialize", "shutdown", "terminal_info"))
    except Exception:
        return False


def process_running():
    result = subprocess.run(
        [str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/tasklist.exe"),
         "/FO", "CSV", "/NH"], capture_output=True, text=True, errors="replace",
        timeout=10, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    rows = list(csv.reader(io.StringIO(result.stdout)))
    if not rows or not all(len(row) >= 2 and row[1].isdigit() for row in rows):
        raise ValueError("Process inventory is unavailable")
    return any(row[0].lower() in TERMINAL_NAMES for row in rows)


def registry_locations():
    import winreg
    locations = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            for name in TERMINAL_NAMES:
                try:
                    with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}",
                                        0, winreg.KEY_READ | view) as key:
                        locations.append(Path(winreg.QueryValueEx(key, None)[0].strip('"')).parent)
                except FileNotFoundError:
                    pass
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                                    0, winreg.KEY_READ | view) as parent:
                    for i in range(winreg.QueryInfoKey(parent)[0]):
                        with winreg.OpenKey(parent, winreg.EnumKey(parent, i)) as key:
                            try:
                                name = winreg.QueryValueEx(key, "DisplayName")[0].lower()
                                if "metatrader" in name or "mt5" in name:
                                    locations.append(Path(winreg.QueryValueEx(key, "InstallLocation")[0]))
                            except FileNotFoundError:
                                pass
            except FileNotFoundError:
                pass
    return locations


def user_profiles():
    profiles = [Path.home()]
    users = Path(os.environ.get("SystemDrive", "C:") + os.sep) / "Users"
    if users.is_dir():
        profiles.extend(p for p in users.iterdir() if p.name not in ("All Users", "Default User")
                        and p.is_dir() and not p.is_symlink())
    return list(dict.fromkeys(profiles))


def fixed_drives():
    import ctypes
    kernel32 = ctypes.windll.kernel32
    mask = kernel32.GetLogicalDrives()
    return [Path(f"{letter}:/") for i, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            if mask & (1 << i) and kernel32.GetDriveTypeW(f"{letter}:\\") == 3]


def default_roots():
    # Search immediate children of installation/portable locations, not entire disks.
    roots = [Path.cwd(), Path(sys.executable).parent]
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        if os.environ.get(key):
            roots.append(Path(os.environ[key]))
    # CI services run as SYSTEM; inspect other users' obvious portable locations too.
    roots += [profile / part for profile in user_profiles()
              for part in ("Desktop", "Downloads", "Documents", "AppData/Local/Programs")]
    # Avoid probing disconnected network/removable drives (which can block).
    roots += fixed_drives()
    if os.environ.get("LOCALAPPDATA"):
        roots.append(Path(os.environ["LOCALAPPDATA"]) / "Programs")
    return roots


def inspect_terminal(*, roots=None, registry_reader=registry_locations,
                     process_probe=process_running, dependency_probe=dependency_available,
                     platform=None):
    supported = (os.name if platform is None else platform) == "nt"
    if not supported:
        return TerminalInspection(False, errors=("unsupported_platform",))
    errors, found, searched = [], set(), set()
    candidates = list(default_roots() if roots is None else roots)
    try:
        candidates.extend(registry_reader())
    except Exception:
        errors.append("registry_inspection_failed")
    # MetaQuotes records the installation directory in origin.txt, not account data.
    origin_bases = []
    if roots is None:
        origin_bases = [p / "AppData/Roaming/MetaQuotes/Terminal" for p in user_profiles()]
        if os.environ.get("APPDATA"):
            origin_bases.append(Path(os.environ["APPDATA"]) / "MetaQuotes/Terminal")
    for base in dict.fromkeys(origin_bases):
        try:
            if base.is_dir():
                for origin in base.glob("*/origin.txt"):
                    raw = origin.read_bytes()
                    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
                    candidates.append(Path(raw.decode(encoding).strip().rstrip("\x00")))
        except (OSError, UnicodeError, ValueError):
            errors.append("origin_inspection_failed")
    for root in dict.fromkeys(candidates):
        try:
            searched.add(str(root))
            if not root.is_dir():
                continue
            directories = [root]
            # Common portable folders inside Desktop/Downloads and broker install dirs.
            directories.extend(p for p in root.iterdir() if p.is_dir() and not p.is_symlink())
            for directory in directories:
                for name in TERMINAL_NAMES:
                    terminal = directory / name
                    if terminal.is_file():
                        found.add(str(terminal.resolve()))
        except (OSError, ValueError):
            errors.append("filesystem_inspection_failed")
    try:
        running = process_probe()
        if not isinstance(running, bool):
            raise ValueError("invalid process probe")
    except Exception:
        running = None
        errors.append("process_inspection_failed")
    try:
        available = bool(dependency_probe())
    except Exception:
        available = False
    return TerminalInspection(True, tuple(sorted(found)), running, available,
                              tuple(sorted(set(errors))), tuple(sorted(searched)))
