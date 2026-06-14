from unittest.mock import Mock

import pytest

from mazyr.application.audit import AuditUseCase
from mazyr.domain.constitution import Constitution
from mazyr.domain.filter import IntegrityFilter
from mazyr.domain.identity import Identity


class TestAuditUseCase:
    @pytest.fixture
    def audit(self):
        identity = Identity(
            instance_name="TestMazyr",
            creator_name="TestCreator",
            species="Mazyr",
            vessel_type="laptop",
        )
        filter_engine = IntegrityFilter()
        memory = Mock()
        memory.count.return_value = {"episodic": 5, "semantic": 3}
        return AuditUseCase(
            identity=identity,
            filter_engine=filter_engine,
            memory=memory,
            constitution=Constitution(),
        )

    def test_health_check_contains_all_sections(self, audit):
        health = audit.health_check()

        assert health["overall"] == "healthy"
        assert "identity" in health
        assert "filter" in health
        assert "memory" in health
        assert "constitution" in health

    def test_health_check_identity(self, audit):
        identity = audit.health_check()["identity"]
        assert identity["configured"] is True
        assert identity["instance_name"] == "TestMazyr"
        assert identity["creator"] == "TestCreator"

    def test_health_check_filter(self, audit):
        filter_health = audit.health_check()["filter"]
        assert filter_health["test_allow"] is True
        assert filter_health["test_drop"] is True
        assert filter_health["status"] == "ok"

    def test_health_check_memory(self, audit):
        memory = audit.health_check()["memory"]
        assert memory["entries"] == 8
        assert memory["types"] == {"episodic": 5, "semantic": 3}

    def test_detect_drift_no_outputs(self, audit):
        assert audit.detect_drift([]) == []

    def test_detect_drift_performative(self, audit):
        outputs = [
            "Please follow me for more tips",
            "Like and share this post",
            "Here is the answer you asked for",
        ]
        signals = audit.detect_drift(outputs)
        assert len(signals) == 1
        assert signals[0]["type"] == "performative_drift"

    def test_detect_drift_low_ratio(self, audit):
        outputs = ["Here is the answer", "Another answer", "Final answer"]
        assert audit.detect_drift(outputs) == []
