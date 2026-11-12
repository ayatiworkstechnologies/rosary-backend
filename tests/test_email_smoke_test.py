"""The SMTP smoke command is tested with mock transport only."""

import os
import unittest
from unittest.mock import patch

import tests._env  # noqa: F401

from app.commands.email_smoke_test import CONFIRMATION, run_smoke_test


class EmailSmokeTestCommandTests(unittest.TestCase):
    def test_blank_allowlist_fails_closed(self):
        env = {
            "EMAIL_NOTIFICATIONS_ENABLED": "true",
            "EMAIL_TRANSPORT": "mock",
            "EMAIL_SMOKE_TEST_RECIPIENTS": "",
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(ValueError, "empty"):
                run_smoke_test(confirmation=CONFIRMATION)

    def test_confirmation_is_required(self):
        env = {
            "EMAIL_NOTIFICATIONS_ENABLED": "true",
            "EMAIL_TRANSPORT": "mock",
            "EMAIL_SMOKE_TEST_RECIPIENTS": "authorized@example.com",
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(ValueError, "confirmation"):
                run_smoke_test(confirmation="NO")

    def test_mock_smoke_test_masks_recipient_and_reports_acceptance(self):
        env = {
            "EMAIL_NOTIFICATIONS_ENABLED": "true",
            "EMAIL_TRANSPORT": "mock",
            "EMAIL_SMOKE_TEST_RECIPIENTS": "authorized@example.com",
        }
        with patch.dict(os.environ, env, clear=False):
            report = run_smoke_test(confirmation=CONFIRMATION)
        self.assertEqual(report["application_status"], "COMPLETED")
        self.assertEqual(report["application_delivery_status"], "SMTP_ACCEPTED")
        self.assertEqual(report["outbox_status"], "NOT_APPLICABLE_DIRECT_SMOKE_TEST")
        self.assertEqual(report["recipient_count"], 1)
        self.assertEqual(report["results"][0]["smtp_acceptance"], "ACCEPTED")
        self.assertEqual(report["results"][0]["inbox_delivery"], "PENDING_MANUAL_VERIFICATION")
        self.assertNotIn("authorized@example.com", str(report))

    def test_real_smtp_needs_second_explicit_switch(self):
        env = {
            "EMAIL_NOTIFICATIONS_ENABLED": "true",
            "EMAIL_TRANSPORT": "smtp",
            "EMAIL_SMOKE_TEST_RECIPIENTS": "authorized@example.com",
            "SMTP_HOST": "smtp.example.test",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "synthetic-user",
            "SMTP_PASSWORD": "synthetic-secret",
            "SMTP_FROM_EMAIL": "sender@example.com",
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(ValueError, "--allow-real-smtp"):
                run_smoke_test(confirmation=CONFIRMATION)
