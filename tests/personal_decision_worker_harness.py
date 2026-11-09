"""Isolated synthetic worker-process harness; no production data or LLM calls."""
import json
import os
import sys
from time import sleep

from app.infra.db.decision_run_repository import DecisionRunRepository
from app.operations.decision_session_service import DecisionSessionApplicationService
from tests.test_decision_session_service import IDENTITY, agent_factory, packet


def main():
    identities = [IDENTITY.model_copy(update={"asset_id": asset}) for asset in json.loads(os.environ["DECISION_LOAD_ASSETS"])]
    service = DecisionSessionApplicationService(packet, agent_factory, DecisionRunRepository(os.environ["DECISION_TEST_POSTGRES_DSN"], lease_seconds=float(os.getenv("DECISION_LOAD_LEASE_SECONDS", "3"))))
    try:
        while True:
            for identity in identities:
                service.resume_pending(identity=identity, limit=50)
            sleep(float(os.getenv("DECISION_LOAD_POLL_SECONDS", "0.1")))
    finally:
        service.stop_workers(wait=True)


if __name__ == "__main__":
    main()
