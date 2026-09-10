from collections.abc import Iterator

import pytest


@pytest.fixture(scope="session", autouse=True)
def db() -> Iterator[None]:
    """Keep pure agent component tests independent from PostgreSQL."""
    yield

