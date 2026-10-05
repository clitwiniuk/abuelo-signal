# Root Pytest Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make root-level `pytest` execute only the four deterministic Finviz Dashboard regression tests.

**Architecture:** Use pytest's root `testpaths` configuration as the single collection boundary. Keep project-local configurations and historical test runners unchanged, and document that those suites require explicit project-level commands.

**Tech Stack:** Python, pytest, Markdown, GitHub PR workflow.

**Spec:** `docs/superpowers/specs/2026-10-05-pytest-root-collection-design.md`

## Global Constraints

- Root `pytest` must collect only `CLAUDE/finviz-dashboard/python/tests`.
- Existing Finviz tests remain unchanged.
- Do not modify production trading or Finviz runtime modules.
- Do not install dependencies for unrelated historical or independent projects.
- Root collection must not perform network access.

## Review Focus

- A root invocation must not recurse into archived trading code — verify collection lists only Finviz tests in Task 3.
- A missing optional dependency must not break root collection — verify with the clean root command in Task 3.
- A network-backed test must not run during collection — verify no external project appears in the collected node IDs in Task 3.
- The existing README command must not point to the absent `algoplatform/tests` path — replace it in Task 2 and inspect the rendered command.
- Project-local test configuration must remain available — verify the root config only changes an invocation from the repository root in Task 3.

---

### Task 1: Establish the failing root-collection baseline

**Files:**
- No files modified.

**Interfaces:**
- Consumes: current repository root and existing pytest installation.
- Produces: recorded baseline proving that bare root pytest currently discovers unrelated projects and fails during collection.

- [ ] **Step 1: Run the baseline collection command**

Run from the repository root:

```bash
pytest --collect-only -q
```

Expected before the fix: collection reports errors from at least one non-Finviz project and does not produce a Finviz-only four-test collection.

- [ ] **Step 2: Confirm the baseline failure is collection scope**

Check that the error output names at least one non-Finviz project or external dependency. Do not change code in this step; this confirms the root cause before adding configuration.

### Task 2: Add the root collection boundary and documentation

**Files:**
- Create: `pytest.ini`
- Modify: `README.md` under `## Tests`

**Interfaces:**
- Consumes: pytest's repository-root configuration discovery.
- Produces: `pytest -q` as the documented root smoke-suite command, collecting `CLAUDE/finviz-dashboard/python/tests` only.

- [ ] **Step 1: Create the root pytest configuration**

Add:

```ini
[pytest]
testpaths =
    CLAUDE/finviz-dashboard/python/tests
addopts = -ra
```

Keep the configuration limited to collection scope and existing report verbosity; do not add dependency-specific plugins or warning suppression globally.

- [ ] **Step 2: Update the root README test instructions**

Replace the stale `USE_DUMMY_BROKER=true pytest -v algoplatform/tests/` command with:

```bash
pytest -q
```

Explain that this root command covers the Finviz Dashboard Python smoke suite and that historical/independent project tests must be run from their own project directories with their own dependencies.

- [ ] **Step 3: Check formatting and scope**

Run:

```bash
git diff --check
git diff -- pytest.ini README.md
```

Expected: only the new pytest configuration and the README test section are changed.

### Task 3: Verify deterministic root testing

**Files:**
- Test: `CLAUDE/finviz-dashboard/python/tests/test_sqlite_resilience.py` (unchanged)

**Interfaces:**
- Consumes: root `pytest.ini` from Task 2.
- Produces: four collected and four passing Finviz tests, with no unrelated import or network collection errors.

- [ ] **Step 1: Verify exact collection scope**

Run:

```bash
pytest --collect-only -q
```

Expected: exactly four node IDs, all under `CLAUDE/finviz-dashboard/python/tests/test_sqlite_resilience.py`.

- [ ] **Step 2: Run the root smoke suite**

Run:

```bash
pytest -q
```

Expected: `4 passed` and no collection errors.

- [ ] **Step 3: Run the existing Finviz regression command explicitly**

Run:

```bash
pytest -q CLAUDE/finviz-dashboard/python/tests/test_sqlite_resilience.py
python3 -m compileall -q CLAUDE/finviz-dashboard/python
```

Expected: four tests pass and Python compilation succeeds.

### Task 4: Finalize the branch and PR

**Files:**
- No additional files.

**Interfaces:**
- Consumes: verified configuration and documentation from Tasks 2–3.
- Produces: a clean pushed branch and PR targeting `feature/scanner-backtest`.

- [ ] **Step 1: Review the final diff**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: no whitespace errors and only intended files changed.

- [ ] **Step 2: Commit the implementation**

```bash
git add pytest.ini README.md
git commit -m "test: scope root pytest collection to finviz suite"
```

- [ ] **Step 3: Push the branch and verify synchronization**

```bash
git push -u origin fix/pytest-root-collection
git status --short --branch
```

Expected: the remote branch is updated and the worktree is clean.
