"""Shared TestClient helpers for the workflow test suites."""
import os
import unittest

import tests._env  # noqa: F401  (isolates the test database - keep first)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from tests.fixtures import ADMIN_PW, PARENT_PW, TEACHER_PW, OTHER_PW, init_test_db  # noqa: E402


class ApiTestBase(unittest.TestCase):
    """Boots the app once and seeds synthetic data."""

    ids = {}
    client: TestClient = None
    tokens = {}

    @classmethod
    def setUpClass(cls):
        cls.ids = init_test_db()
        cls.client = TestClient(app)
        cls.tokens = {
            "admin": cls.login("ADM_TEST", ADMIN_PW, "ADMIN"),
            "teacher": cls.login("TEACH_TEST", TEACHER_PW, "TEACHER"),
            "parent": cls.login("PAR_TEST", PARENT_PW, "PARENT"),
            "other_teacher": cls.login("TEACH_OTHER", "Other@Test1!", "TEACHER"),
            "other_parent": cls.login("PAR_OTHER", "Other@Test1!", "PARENT"),
        }

    @classmethod
    def login(cls, username, password, role):
        resp = cls.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password, "role": role},
        )
        assert resp.status_code == 200, f"login failed for {username}: {resp.status_code} {resp.text}"
        return resp.json()["access_token"]

    @classmethod
    def get(cls, path, token=None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return cls.client.get(path, headers=headers)

    @classmethod
    def post(cls, path, token=None, **kwargs):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return cls.client.post(path, headers=headers, **kwargs)

    @classmethod
    def put(cls, path, token=None, **kwargs):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return cls.client.put(path, headers=headers, **kwargs)

    @classmethod
    def patch(cls, path, token=None, **kwargs):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return cls.client.patch(path, headers=headers, **kwargs)

    @classmethod
    def delete(cls, path, token=None, **kwargs):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return cls.client.delete(path, headers=headers, **kwargs)
