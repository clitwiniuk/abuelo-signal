from pathlib import Path
import runpy


LEGACY_ROOT = Path(__file__).parents[1]
RUNNER_PATH = "scripts/testing/run_morning_test.py"
ARCHIVED_TEST_PATH = "legacy/archives/archive/legacy_tests/test_production_final.py"
MAINTAINED_TEST_PATH = "tests/test_gap_volume_filters.py"
OBSOLETE_PRODUCTION_TEST_PATHS = (
    "tests/test_performance_command.py",
    "tests/test_production_edge_cases.py",
    "tests/test_production_execution_flow.py",
    "tests/test_production_market_simulation.py",
    "tests/test_production_network_resilience.py",
    "tests/test_production_scanner_execution.py",
    "tests/test_production_simple.py",
    "tests/test_production_stress_extreme.py",
    "tests/test_production_system.py",
)


def test_manual_morning_runner_is_excluded_from_pytest_collection():
    config = runpy.run_path(str(LEGACY_ROOT / "conftest.py"))

    ignore_collect = config["pytest_ignore_collect"]

    assert RUNNER_PATH in config["collect_ignore"]
    assert ignore_collect(LEGACY_ROOT / RUNNER_PATH, None)
    assert ignore_collect(LEGACY_ROOT / ARCHIVED_TEST_PATH, None)
    for test_path in OBSOLETE_PRODUCTION_TEST_PATHS:
        assert ignore_collect(LEGACY_ROOT / test_path, None)
    assert not ignore_collect(LEGACY_ROOT / MAINTAINED_TEST_PATH, None)
