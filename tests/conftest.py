import pytest

from backend.core.database import Database


@pytest.fixture
async def test_db(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    await db.initialize()
    yield db
    await db.close()
