import argparse
import json
import logging
import time

from app.database import SessionLocal
from app.services.parent_email_service import (
    get_email_settings,
    process_email_queue,
)
from app.services.email_worker_health import write_worker_heartbeat


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_once() -> dict:
    db = SessionLocal()
    try:
        return process_email_queue(db)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Process parent email outbox")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one batch and exit (useful for cron and health checks)",
    )
    args = parser.parse_args()
    settings = get_email_settings()

    if not settings.enabled:
        raise SystemExit("EMAIL_NOTIFICATIONS_ENABLED is false; worker stopped")
    if not settings.provider_ready:
        raise SystemExit("Email provider configuration is incomplete; worker stopped")

    while True:
        try:
            result = run_once()
        except Exception:
            result = {"processed": 0, "sent": 0, "failed": 0, "retried": 0}
            write_worker_heartbeat(result, status="error")
            logger.exception("email_worker_cycle_failed")
            if args.once:
                raise
        else:
            write_worker_heartbeat(result)
            logger.info("email_worker_cycle %s", json.dumps(result, sort_keys=True))
        if args.once:
            return
        time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    main()
