"""Pytest collection rules for the maintained part of the legacy tree."""

from pathlib import Path


_LEGACY_ROOT = Path(__file__).resolve().parent
_NON_PYTEST_DIRECTORIES = {"legacy", "scripts"}
_OBSOLETE_PRODUCTION_TESTS = {
    "tests/test_performance_command.py",
    "tests/test_production_edge_cases.py",
    "tests/test_production_execution_flow.py",
    "tests/test_production_market_simulation.py",
    "tests/test_production_network_resilience.py",
    "tests/test_production_scanner_execution.py",
    "tests/test_production_simple.py",
    "tests/test_production_stress_extreme.py",
    "tests/test_production_system.py",
}

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

    if not relative_path.parts:
        return False

    return (
        relative_path.parts[0] in _NON_PYTEST_DIRECTORIES
        or relative_path.as_posix() in _OBSOLETE_PRODUCTION_TESTS
    )
