"""Put the brain package on sys.path for this app.

A checkout is found by walking up to ``brain/``. On the board, copy that
package to ``~/ArduinoApps/fly-memento/python/brain`` and the import
succeeds without this search: App Lab puts ``python/`` on the path.
"""

from __future__ import annotations

import sys
from pathlib import Path


def find_brain_root(origin: Path) -> Path | None:
    """Directory that contains ``brain/brain.py``, walking up from a file."""
    for parent in origin.resolve().parents:
        package = parent / "brain"
        if (package / "__init__.py").is_file() and (package / "brain.py").is_file():
            return parent
    return None


def install() -> None:
    try:
        import brain.brain  # noqa: F401
    except ImportError:
        pass
    else:
        return
    root = find_brain_root(Path(__file__))
    if root is None:
        raise ImportError(
            "brain が見つからない。brain を "
            "~/ArduinoApps/fly-memento/python/brain に置くか、リポジトリごと置いてから起動する。"
        )
    entry = str(root)
    if entry not in sys.path:
        sys.path.insert(0, entry)
