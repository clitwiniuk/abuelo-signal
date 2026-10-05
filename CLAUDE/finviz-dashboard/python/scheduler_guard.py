"""Failure boundary for the background snapshot scheduler."""


def run_scheduler_cycle(run_snapshot, log, add_log):
    """Run one cycle and keep transient failures inside the worker thread."""
    try:
        run_snapshot()
    except Exception as exc:
        log.exception("Scheduler cycle failed; continuing")
        add_log(f"Scheduler error: {exc}")
        return exc
    return None
