"""Pytest collection rules for the maintained part of the legacy tree."""

from pathlib import Path


_LEGACY_ROOT = Path(__file__).resolve().parent
_NON_PYTEST_DIRECTORIES = {"legacy", "scripts"}

# Also cover an explicit pytest invocation of this historical runner. The
# directory hook below handles normal recursive collection.
collect_ignore = ["scripts/testing/run_morning_test.py"]


def pytest_ignore_collect(collection_path, config):
    """Do not import archived code or manual runners during pytest collection.

    The directories are still available for their documented command-line
    runners; they simply are not pytest modules and several of them terminate
    the process when an optional historical dependency is unavailable.
    """

    try:
        relative_path = Path(str(collection_path)).resolve().relative_to(_LEGACY_ROOT)
    except ValueError:
        return False

    return bool(relative_path.parts) and relative_path.parts[0] in _NON_PYTEST_DIRECTORIES
