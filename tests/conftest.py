import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_identity():
    return Mock(
        instance_name="TestMazyr",
        creator_name="TestCreator",
        species="Mazyr",
        is_configured=True,
    )


@pytest.fixture
def mock_mission():
    return Mock(primary="Test mission", scope=["test"])


@pytest.fixture
def mock_constitution():
    from mazyr.domain.constitution import Constitution

    return Constitution()


@pytest.fixture
def mock_filter():
    from mazyr.domain.filter import IntegrityFilter

    return IntegrityFilter()
