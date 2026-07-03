import asyncio

from backend.llm import apply_profile_updates
from framework.context.user import UserContext
from framework.persistence.sqlite import SQLiteUserRepository


def test_apply_profile_updates_merges_into_onboarding(tmp_path):
    repo = SQLiteUserRepository(str(tmp_path / "t.db"))

    async def seed():
        await repo.upsert(
            UserContext(
                user_id="+911",
                phone="+911",
                metadata={
                    "onboarding": {
                        "ac": False,
                        "roof_material": "tin",
                        "floor_level": "ground",
                        "fan": False,
                        "windows_open": False,
                        "occupants": 1,
                    },
                    "verified": True,
                },
            )
        )

    asyncio.run(seed())
    asyncio.run(apply_profile_updates(repo, "+911", {"floor_level": "top", "ac": True}))

    async def read():
        return await repo.get_by_phone("+911")

    user = asyncio.run(read())
    assert user is not None
    assert user.metadata["onboarding"]["floor_level"] == "top"
    assert user.metadata["onboarding"]["ac"] is True
    assert user.metadata["onboarding"]["roof_material"] == "tin"