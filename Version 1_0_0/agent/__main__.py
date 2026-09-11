# Path: agent/__main__.py

"""Package entry point for ``python -m agent``.

Delegates execution to the same ``main()`` function used by the
legacy flat entry point so both execution modes remain consistent.
"""

from __future__ import annotations

from .main import main


if __name__ == "__main__":
    main()