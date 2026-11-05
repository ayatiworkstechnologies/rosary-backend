"""Health endpoint behavior and information-disclosure regression tests."""
import unittest
from unittest.mock import patch

import tests._env  # noqa: F401  (isolate DB before importing the app)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from app.main import app  # noqa: E402


class HealthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_reports_connected_database(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "healthy", "database": "connected"},
        )

    def test_database_failure_returns_503_without_internal_error(self):
        internal_message = "database host and credentials must stay private"

        with patch(
            "app.main.engine.connect",
            side_effect=SQLAlchemyError(internal_message),
        ):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Database unavailable"})
        self.assertNotIn(internal_message, response.text)
