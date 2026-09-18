from pathlib import Path
from runpy import run_path

from PyInstaller.utils.hooks import collect_dynamic_libs

project_root = Path(SPECPATH).resolve().parent
version = run_path(str(project_root / "agent" / "__init__.py"))["__version__"]
icon_path = project_root / "deployment" / "MT5Agent.ico"

numpy_binaries = collect_dynamic_libs("numpy")

analysis = Analysis(
    [str(project_root / "agent" / "__main__.py")],
    pathex=[str(project_root)],
    binaries=numpy_binaries,
    datas=[],
    hiddenimports=[
        "numpy",
        "MetaTrader5",
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[
        "numpy.tests",
        "numpy.core.tests",
        "numpy.compat.tests",
        "numpy.array_api.tests",
    ], noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz, analysis.scripts, analysis.binaries, analysis.datas, [],
    name=f"MT5Agent-v{version}", icon=str(icon_path), debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=True,
)
