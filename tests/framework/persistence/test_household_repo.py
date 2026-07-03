import unittest
import os
import asyncio
from framework.persistence.sqlite import SQLiteHouseholdRepository

class TestSQLiteHouseholdRepository(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db_path = "test_household.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.repo = SQLiteHouseholdRepository(f"sqlite:///{self.db_path}")

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_add_list_delete(self):
        user_id = "user_123"
        # Add 
        id1 = await self.repo.add(user_id, "Alice", "child", False)
        id2 = await self.repo.add(user_id, "Bob", "elderly", True)
        
        self.assertTrue(id1 > 0)
        self.assertTrue(id2 > id1)

        # List
        members = await self.repo.list_for_user(user_id)
        self.assertEqual(len(members), 2)
        self.assertEqual(members[0]["name"], "Alice")
        self.assertEqual(members[0]["tag"], "child")
        self.assertEqual(members[0]["outdoor_worker"], 0)
        self.assertEqual(members[1]["name"], "Bob")
        self.assertEqual(members[1]["tag"], "elderly")
        self.assertEqual(members[1]["outdoor_worker"], 1)

        # Update
        ok = await self.repo.update(id1, "Alice Updated", "teen", True)
        self.assertTrue(ok)
        
        members = await self.repo.list_for_user(user_id)
        self.assertEqual(members[0]["name"], "Alice Updated")
        self.assertEqual(members[0]["tag"], "teen")
        self.assertEqual(members[0]["outdoor_worker"], 1)

        # Delete
        ok = await self.repo.delete(id1)
        self.assertTrue(ok)
        
        members = await self.repo.list_for_user(user_id)
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0]["id"], id2)

if __name__ == "__main__":
    unittest.main()
