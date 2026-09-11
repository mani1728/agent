# Path: agent/main.py

"""Package-safe bridge to the legacy console entry point.

The legacy ``main.py`` remains at the project root while the Agent
package is being migrated to the new architecture.

This module allows:

    python -m agent

to execute the same ``main()`` function used by:

    python main.py

The bridge is intentionally kept small and contains no application
business logic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


_LEGACY_MODULE_NAME = "agent_legacy_main"


def _load_legacy_main() -> ModuleType:
    """Load the project-root legacy ``main.py`` as a module."""
    project_root = Path(__file__).resolve().parent.parent
    legacy_path = project_root / "main.py"

    if not legacy_path.is_file():
        raise RuntimeError(
            f"Legacy entry point not found: {legacy_path}"
        )

    root_text = str(project_root)

    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    spec = importlib.util.spec_from_file_location(
        _LEGACY_MODULE_NAME,
        legacy_path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Cannot load legacy entry point: {legacy_path}"
        )

    module = importlib.util.module_from_spec(spec)

    # Register the dynamically loaded module so imports/introspection
    # performed by the legacy code behave like a normal module import.
    sys.modules[_LEGACY_MODULE_NAME] = module

    try:
        spec.loader.exec_module(module)
    except Exception:
        # Do not hide the original exception/traceback from the legacy
        # entry point.
        sys.modules.pop(_LEGACY_MODULE_NAME, None)
        raise

    return module


def main() -> None:
    """Execute the legacy application's ``main()`` function."""
    legacy_module = _load_legacy_main()

    legacy_main = getattr(
        legacy_module,
        "main",
        None,
    )

    if not callable(legacy_main):
        raise RuntimeError(
            "The legacy entry point does not define a callable main()"
        )

    legacy_main()


if __name__ == "__main__":
    main()