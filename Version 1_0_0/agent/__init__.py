# Path: agent/__init__.py

"""MT5 Windows-side Agent package.

The package provides the Agent application and its transport abstraction.

Supported execution modes
--------------------------
Package mode::

    python -m agent

Legacy flat-file mode::

    python main.py

The legacy mode is kept for backward compatibility.
"""

from __future__ import annotations


__version__ = "0.2.0"

__all__: list[str] = []