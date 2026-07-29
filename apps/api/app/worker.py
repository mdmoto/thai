"""Cloud Run Job entrypoint for one durable simulation run."""

from __future__ import annotations

import logging
import os
import sys

from app.db.database import initialize_database
from app.services.run_worker import run_worker


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    run_job_id = os.environ.get("RUN_JOB_ID", "").strip()
    if not run_job_id:
        logging.error("RUN_JOB_ID is required")
        return 2
    initialize_database()
    report_id = run_worker(run_job_id)
    if report_id:
        logging.info(
            "Simulation job %s completed with report %s",
            run_job_id,
            report_id,
        )
        return 0
    logging.error(
        "Simulation job %s failed and its reservation was handled",
        run_job_id,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
