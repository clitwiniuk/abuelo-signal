# Root Pytest Collection Design

## Goal

Make `pytest` run from the repository root deterministic and useful for the maintained Finviz Dashboard code, without importing archived trading scripts, unrelated repositories, optional GUI dependencies, or tests that perform network calls during collection.

## Context

The repository is a monorepo containing the maintained Finviz Dashboard plus historical trading-system trees and independent projects. A root-level pytest invocation currently discovers all of them. The resulting collection errors are heterogeneous: missing modules from archived code, missing optional dependencies, duplicate test module names, and external network access during import.

The maintained Finviz regression suite is located at `CLAUDE/finviz-dashboard/python/tests/` and currently contains four deterministic tests for SQLite and scheduler resilience.

## Approved Scope

### Root test policy

Add a root `pytest.ini` that sets the default `testpaths` to:

```text
CLAUDE/finviz-dashboard/python/tests
```

The root command therefore exercises the maintained Finviz smoke suite only. It must not recursively discover `CLAUDE/antiguo_trading_system`, `CLAUDE/twitter_studio`, `Interactive-Brokers-Trading-Bot-master`, `quanttrader-master`, or ad-hoc root scripts.

Existing project-local pytest configurations remain responsible for their own explicit test commands.

### Documentation

Update the root README with:

1. The supported root command: `pytest -q`.
2. The expected scope: Finviz Dashboard Python tests.
3. A note that historical and independent project tests are not part of root collection and must be run from their project directory with their own dependencies.

### Verification

The implementation must prove that:

- `pytest --collect-only -q` from the repository root collects exactly the four Finviz tests.
- `pytest -q` from the repository root passes those four tests.
- No test imports a network client during root collection.
- Existing Finviz resilience tests remain unchanged and passing.

## Non-Goals

- Repairing archived trading-system imports.
- Recreating removed modules such as `core.dynamic_position_sizing`.
- Installing dependencies for Twitter Studio, QuantTrader, or the Interactive Brokers sample project.
- Refactoring tests that require external services or network access.
- Changing production code, deployment configuration, or VPS behavior.

## Files

- Create: `pytest.ini` at repository root for default collection scope.
- Modify: `README.md` to document root and project-local test commands.
- Test: use the existing `CLAUDE/finviz-dashboard/python/tests/test_sqlite_resilience.py` suite and root collection verification.

## Acceptance Criteria

1. A clean checkout of the branch runs `pytest -q` successfully from the repository root.
2. Root collection reports four tests, all under `CLAUDE/finviz-dashboard/python/tests/`.
3. The branch contains no changes to production trading or Finviz runtime modules.
4. The root working tree is clean after commit and the branch is pushed for PR review.
