import unittest
import os
from fastapi.testclient import TestClient
from backend.main import app
from prana.bot.bootstrap import build_household_repo
from prana.config import DATABASE_URL

class TestHouseholdEndpoints(unittest.TestCase):
    def setUp(self):
        # We use the real app but it connects to the DATABASE_URL.
        # For tests, we'd ideally mock the repo or use a test DB.
        # But here we'll just check if the endpoints are wired correctly.
        self.client = TestClient(app)
        self.user_id = "test_user_api"
        # Cleanup existing members for this test user if any
        repo = build_household_repo()
        # Note: listing and deleting is async in the repo, but here we can
        # just let the endpoints handle the persistence and we check the responses.

    def test_household_lifecycle(self):
        # 1. Add member
        payload = {
            "user_id": self.user_id,
            "name": "Test Child",
            "tag": "child",
            "outdoor_worker": False
        }
        resp = self.client.post("/household/members", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["name"], "Test Child")
        self.assertEqual(data["tag"], "child")
        member_id = data["id"]

        # 2. List members
        resp = self.client.get(f"/household/members?user_id={self.user_id}")
        self.assertEqual(resp.status_code, 200)
        members = resp.json()
        self.assertTrue(any(m["id"] == member_id for m in members))

        # 3. Invalid tag validation
        payload["tag"] = "invalid_tag"
        resp = self.client.post("/household/members", json=payload)
        self.assertEqual(resp.status_code, 422) # Fast API Pydantic validation

        # 4. Delete member
        resp = self.client.delete(f"/household/members/{member_id}")
        self.assertEqual(resp.status_code, 200)
        
        # 5. Verify deletion
        resp = self.client.get(f"/household/members?user_id={self.user_id}")
        members = resp.json()
        self.assertFalse(any(m["id"] == member_id for m in members))

if __name__ == "__main__":
    unittest.main()
