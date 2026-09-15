from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project_root = Path(SPECPATH).parent
icon_path = project_root / "deployment" / "MT5Agent.ico"
numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all("numpy")
mt5_datas, mt5_binaries, mt5_hiddenimports = collect_all("MetaTrader5")

analysis = Analysis(
    [str(project_root / "agent" / "__main__.py")],
    pathex=[str(project_root)],
    binaries=numpy_binaries + mt5_binaries,
    datas=numpy_datas + mt5_datas,
    hiddenimports=["numpy", "numpy._core", "numpy._core.multiarray", "MetaTrader5"] + numpy_hiddenimports + mt5_hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz, analysis.scripts, analysis.binaries, analysis.datas, [],
    name="MT5Agent-v0.0.6", icon=str(icon_path), debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=True,
)
