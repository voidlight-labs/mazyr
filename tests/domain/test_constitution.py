import pytest
from mazyr.domain.constitution import Constitution, Law


class TestConstitution:
    def test_default_laws_count(self):
        c = Constitution()
        assert len(c.laws) == 9

    def test_all_laws_present(self):
        c = Constitution()
        assert Law.MEDIUM in c.laws
        assert Law.DELEGATION in c.laws
        assert Law.CONTINUITY in c.laws

    def test_self_replicate_without_approval(self):
        c = Constitution()
        result = c.validate_action("self_replicate", {"creator_approved": False})
        assert result.allowed is False
        assert result.violated_law == Law.DELEGATION

    def test_self_replicate_with_approval(self):
        c = Constitution()
        result = c.validate_action("self_replicate", {"creator_approved": True})
        assert result.allowed is True

    def test_override_constitution_blocked(self):
        c = Constitution()
        result = c.validate_action("override_constitution", {})
        assert result.allowed is False
        assert result.violated_law == Law.CONTINUITY

    def test_claim_ownership_of_species(self):
        c = Constitution()
        result = c.validate_action("claim_ownership", {"target": "species"})
        assert result.allowed is False
        assert result.violated_law == Law.MEDIUM

    def test_claim_ownership_of_other(self):
        c = Constitution()
        result = c.validate_action("claim_ownership", {"target": "project"})
        assert result.allowed is True

    def test_immutability(self):
        c = Constitution()
        with pytest.raises(Exception):
            c.laws = ()
