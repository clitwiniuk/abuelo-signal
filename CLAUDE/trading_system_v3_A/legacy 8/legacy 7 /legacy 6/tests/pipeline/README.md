
# MidCap Pipeline Test Battery

This directory contains unittests and integration tests for the MidCap Scanner Pipeline.
These tests verify the "Reactive Approach" logic without depending on external systems (IBKR TWS, FinBERT remote, etc).

## Included Tests

1.  **`test_catalyst_analyzer.py`**
    *   **Unit Test** for `CatalystAnalyzer`.
    *   Verifies initialization, config handling, and sentiment validation.

2.  **`test_midcap_scanner_mocked.py`**
    *   **Integration Test** for `MidCapDailyScanner`.
    *   Verifies end-to-end flow from IBKR Result to MidCapPlay.

3.  **`test_midcap_worker_logic.py`**
    *   **Unit Test** for `DailyPlaysMidCapWorkerLogic`.
    *   Verifies SWING mode override and config loading.

## How to Run

From the project root:

```bash
export PYTHONPATH=$PYTHONPATH:.
python3 -m unittest discover tests/pipeline
```
