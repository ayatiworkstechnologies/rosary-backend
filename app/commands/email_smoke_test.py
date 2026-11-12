"""Fail-closed SMTP smoke test for explicitly allowlisted addresses only."""

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.services.parent_email_service import (
    MockEmailTransport,
    SMTPEmailTransport,
    _safe_provider_error,
    get_email_settings,
    mask_email,
    normalize_email,
)


CONFIRMATION = "SEND-AUTHORIZED-TEST-EMAIL"


def _allowed_recipients() -> list[str]:
    recipients = []
    for value in os.getenv("EMAIL_SMOKE_TEST_RECIPIENTS", "").split(","):
        if value.strip():
            recipients.append(normalize_email(value))
    return sorted(set(recipients))


def run_smoke_test(*, confirmation: str, allow_real_smtp: bool = False) -> dict:
    settings = get_email_settings()
    recipients = _allowed_recipients()
    if confirmation != CONFIRMATION:
        raise ValueError(f"confirmation must equal {CONFIRMATION}")
    if not recipients:
        raise ValueError("EMAIL_SMOKE_TEST_RECIPIENTS is empty; refusing to send")
    if not settings.enabled or not settings.provider_ready:
        raise ValueError("email delivery is disabled or provider configuration is incomplete")
    if settings.transport == "smtp" and not allow_real_smtp:
        raise ValueError("real SMTP requires the explicit --allow-real-smtp option")
    if settings.transport not in {"smtp", "mock"}:
        raise ValueError("EMAIL_TRANSPORT must be smtp or mock")

    transport = (
        SMTPEmailTransport(settings)
        if settings.transport == "smtp"
        else MockEmailTransport()
    )
    test_id = f"ROSARY-SMOKE-{uuid.uuid4().hex[:12].upper()}"
    results = []
    for recipient in recipients:
        message_id = transport.send(
            recipient,
            f"Rosary email smoke test {test_id}",
            (
                f"Authorized delivery test ID: {test_id}. "
                "No student or parent data is included in this message."
            ),
            category="GENERAL",
        )
        results.append(
            {
                "recipient": mask_email(recipient),
                "smtp_acceptance": "ACCEPTED",
                "provider_message_id": message_id,
                "inbox_delivery": "PENDING_MANUAL_VERIFICATION",
            }
        )
    return {
        "test_id": test_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "transport": settings.transport,
        "application_status": "COMPLETED",
        "application_delivery_status": "SMTP_ACCEPTED",
        "outbox_status": "NOT_APPLICABLE_DIRECT_SMOKE_TEST",
        "recipient_count": len(results),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", required=True, help=f"must equal {CONFIRMATION}")
    parser.add_argument(
        "--allow-real-smtp",
        action="store_true",
        help="required in addition to --confirm when EMAIL_TRANSPORT=smtp",
    )
    parser.add_argument("--report", help="optional JSON result file")
    args = parser.parse_args()
    try:
        report = run_smoke_test(
            confirmation=args.confirm,
            allow_real_smtp=args.allow_real_smtp,
        )
    except Exception as exc:
        settings = get_email_settings()
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "transport": settings.transport,
            "application_status": "FAILED",
            "application_delivery_status": "NOT_ACCEPTED",
            "error": _safe_provider_error(
                exc,
                settings,
                *os.getenv("EMAIL_SMOKE_TEST_RECIPIENTS", "").split(","),
            ),
        }
        rendered = json.dumps(report, indent=2)
        if args.report:
            Path(args.report).write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        raise SystemExit(1) from None
    rendered = json.dumps(report, indent=2)
    if args.report:
        Path(args.report).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
