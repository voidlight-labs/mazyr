import pytest
from dataclasses import FrozenInstanceError

from mazyr.domain.identity import Identity, Mission


class TestIdentity:
    def test_valid_creation(self):
        identity = Identity(instance_name="Aria", creator_name="Khayren")
        assert identity.instance_name == "Aria"
        assert identity.creator_name == "Khayren"
        assert identity.species == "Mazyr"
        assert identity.is_configured is True

    def test_default_values(self):
        identity = Identity(instance_name="X", creator_name="Y")
        assert identity.species == "Mazyr"
        assert identity.vessel_type == "laptop"

    def test_empty_instance_name_raises(self):
        with pytest.raises(ValueError, match="instance_name"):
            Identity(instance_name="", creator_name="Khayren")

    def test_empty_creator_name_raises(self):
        with pytest.raises(ValueError, match="creator_name"):
            Identity(instance_name="Aria", creator_name="")

    def test_invalid_vessel_type_raises(self):
        with pytest.raises(ValueError, match="vessel_type"):
            Identity(instance_name="Aria", creator_name="Khayren", vessel_type="spaceship")

    def test_immutability(self):
        identity = Identity(instance_name="Aria", creator_name="Khayren")
        with pytest.raises(Exception):
            identity.instance_name = "Sol"

    def test_unconfigured_identity(self):
        identity = Identity(instance_name="Mazyr", creator_name="Anonymous")
        assert identity.is_configured is False


class TestMission:
    def test_valid_creation(self):
        mission = Mission(primary="Learn coding")
        assert mission.primary == "Learn coding"
        assert mission.scope == ["general"]

    def test_empty_primary_raises(self):
        with pytest.raises(ValueError):
            Mission(primary="")

    def test_custom_scope(self):
        mission = Mission(primary="X", scope=["coding", "analysis"])
        assert mission.scope == ["coding", "analysis"]
