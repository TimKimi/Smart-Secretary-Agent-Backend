import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.ssa.main import create_app


def app():
    return create_app()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
