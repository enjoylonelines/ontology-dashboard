"""Dedicated DecisionSession DB-polling worker process.

Usage: python -m app.operations.decision_worker_process
Requires DECISION_RESUMER_IDENTITIES (tenant-scoped identities) and configured DB.
Does not run the HTTP API or create a separate message broker.
"""
from __future__ import annotations

import logging
import os
import signal
from threading import Event

from app.dependencies import get_decision_session_service

log = logging.getLogger(__name__)


def run(*, stop: Event | None = None) -> None:
    service = get_decision_session_service()
    provider = service.pending_identity_provider
    if provider is None:
        raise RuntimeError(
            "DECISION_RESUMER_IDENTITIES is required for scoped DB worker polling"
        )
    interval = float(os.getenv("DECISION_RESUMER_INTERVAL_SECONDS", "5"))
    if not 0.1 <= interval <= 3600:
        raise ValueError("invalid DECISION_RESUMER_INTERVAL_SECONDS")
    stopped = stop or Event()
    try:
        service.start_resumer(identity_provider=provider, interval_seconds=interval)
        log.info("DecisionSession DB worker started with scoped identity provider")
        stopped.wait()
    finally:
        service.stop_workers(wait=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    run(stop=stop)


if __name__ == "__main__":
    main()
