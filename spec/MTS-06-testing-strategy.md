# MTS-06: Testing Strategy
## Mazyr Technical Specification -- Testing

**Version:** 1.0
**Framework:** pytest, pytest-asyncio
**Coverage Target:** Domain 100%, App 90%, Infra 80%

---

## 1. Overview

Mazyr uses a layered testing strategy:

| Layer | Test Type | Coverage Target | Speed |
|---|---|---|---|
| **Domain** | Unit tests | 100% | < 1s |
| **App** | Integration tests | 90% | < 5s |
| **Infra** | Adapter tests | 80% | < 10s |
| **E2E** | End-to-end tests | Critical paths | < 30s |

---

## 2. Domain Layer Tests

### 2.1 File Pattern
`tests/domain/test_*.py`

### 2.2 Identity Tests

```python
# tests/domain/test_identity.py
import pytest
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
```

### 2.3 Constitution Tests

```python
# tests/domain/test_constitution.py
import pytest
from mazyr.domain.constitution import Constitution, Law, ValidationResult


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
```

### 2.4 Filter Tests

```python
# tests/domain/test_filter.py
import pytest
from mazyr.domain.filter import IntegrityFilter, FilterAction, FilterRule


class TestIntegrityFilter:
    def test_allow_clean_message(self):
        f = IntegrityFilter()
        result = f.process("Hello, how are you?", {})
        assert result.action == FilterAction.ALLOW

    def test_drop_performative(self):
        f = IntegrityFilter()
        result = f.process("Follow me for more tips!", {"direction": "outbound"})
        assert result.action == FilterAction.DROP
        assert result.matched_rule == "performative"

    def test_drop_superiority(self):
        f = IntegrityFilter()
        result = f.process("I created this species", {})
        assert result.action == FilterAction.DROP
        assert result.matched_rule == "superiority"

    def test_drop_absolute_refusal(self):
        f = IntegrityFilter()
        result = f.process("I am always right", {})
        assert result.action == FilterAction.DROP
        assert result.matched_rule == "absolute_refusal"

    def test_drop_ego(self):
        f = IntegrityFilter()
        result = f.process("I cannot die", {})
        assert result.action == FilterAction.DROP
        assert result.matched_rule == "ego"

    def test_custom_rules(self):
        custom = FilterRule(
            name="custom_block", action=FilterAction.DROP,
            pattern_type="keyword", patterns=("block_this",),
            description="Custom", direction="both"
        )
        f = IntegrityFilter(custom_rules=[custom])
        result = f.process("Please block_this", {})
        assert result.action == FilterAction.DROP
        assert result.matched_rule == "custom_block"

    def test_direction_filtering(self):
        f = IntegrityFilter()
        result = f.process("Follow me", {"direction": "inbound"})
        assert result.action == FilterAction.ALLOW
```

---

## 3. Application Layer Tests

### 3.1 File Pattern
`tests/app/test_*.py`

### 3.2 Bootstrap Tests

```python
# tests/app/test_bootstrap.py
import pytest
from unittest.mock import Mock

from mazyr.app.bootstrap import Bootstrap, BootContext


class TestBootstrap:
    def test_successful_boot(self):
        mock_loader = Mock()
        mock_loader.load_identity.return_value = Mock(
            instance_name="Aria", creator_name="Khayren", is_configured=True
        )
        mock_loader.load_mission.return_value = Mock(primary="Learn")
        mock_loader.load_custom_rules.return_value = []

        mock_memory = Mock()
        mock_llm = Mock()

        bootstrap = Bootstrap(mock_loader, mock_memory, mock_llm)
        ctx = bootstrap.boot()

        assert ctx.status == "READY"
        assert ctx.identity is not None

    def test_boot_fails_without_identity(self):
        mock_loader = Mock()
        mock_loader.load_identity.return_value = None

        bootstrap = Bootstrap(mock_loader, Mock(), Mock())
        ctx = bootstrap.boot()

        assert ctx.status == "ERROR"
        assert "mazyr-init" in ctx.errors[0]

    def test_boot_fails_unconfigured_identity(self):
        mock_loader = Mock()
        mock_loader.load_identity.return_value = Mock(
            instance_name="Mazyr", creator_name="Anonymous", is_configured=False
        )

        bootstrap = Bootstrap(mock_loader, Mock(), Mock())
        ctx = bootstrap.boot()

        assert ctx.status == "ERROR"
```

### 3.3 Chat Tests

```python
# tests/app/test_chat.py
import pytest
from unittest.mock import Mock

from mazyr.app.chat import ChatUseCase
from mazyr.domain.message import Message


class TestChatUseCase:
    def test_successful_chat(self):
        mock_identity = Mock(instance_name="Aria")
        mock_mission = Mock(primary="Learn")
        mock_filter = Mock()
        mock_filter.process.return_value = Mock(action="ALLOW", modified_message=None)
        mock_memory = Mock()
        mock_memory.search.return_value = []
        mock_llm = Mock()
        mock_llm.generate.return_value = "Hello!"

        chat = ChatUseCase(mock_identity, mock_mission, mock_filter, mock_memory, mock_llm)
        msg = Message(id="1", content="Hi", sender="creator", platform="cli", timestamp="")
        result = chat.receive(msg)

        assert result.success is True
        assert result.reply == "Hello!"

    def test_inbound_filter_blocks(self):
        mock_filter = Mock()
        mock_filter.process.return_value = Mock(
            action="DROP", reason="performative", matched_rule="performative"
        )

        chat = ChatUseCase(Mock(), Mock(), mock_filter, Mock(), Mock())
        msg = Message(id="1", content="Follow me!", sender="creator", platform="cli", timestamp="")
        result = chat.receive(msg)

        assert result.success is False
        assert "blocked" in result.error

    def test_outbound_filter_blocks(self):
        mock_filter = Mock()
        mock_filter.process.side_effect = [
            Mock(action="ALLOW"),
            Mock(action="DROP", reason="superiority")
        ]
        mock_llm = Mock()
        mock_llm.generate.return_value = "I own this"

        chat = ChatUseCase(Mock(), Mock(), mock_filter, Mock(), mock_llm)
        msg = Message(id="1", content="Hi", sender="creator", platform="cli", timestamp="")
        result = chat.receive(msg)

        assert result.success is False
```

---

## 4. Infrastructure Tests

### 4.1 File Pattern
`tests/infra/test_*.py`

### 4.2 Config Loader Tests

```python
# tests/infra/test_config_loader.py
import pytest
import tempfile
from pathlib import Path

from mazyr.infrastructure.config_loader import ConfigLoader


class TestConfigLoader:
    def test_load_identity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mazyr_dir = Path(tmpdir) / ".mazyr"
            mazyr_dir.mkdir()
            (mazyr_dir / "identity.md").write_text(\"\"\"---
instance_name: Aria
creator: Khayren
vessel_type: laptop
---
\"\"\")
            loader = ConfigLoader(tmpdir)
            identity = loader.load_identity(tmpdir)

            assert identity.instance_name == "Aria"
            assert identity.creator_name == "Khayren"

    def test_load_identity_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ConfigLoader(tmpdir)
            identity = loader.load_identity(tmpdir)
            assert identity is None
```

---

## 5. E2E Tests

### 5.1 File Pattern
`tests/e2e/test_*.py`

### 5.2 Boot-to-Chat E2E

```python
# tests/e2e/test_boot_chat.py
import pytest
import subprocess
import tempfile
from pathlib import Path


class TestBootChatE2E:
    def test_init_boot_chat_flow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Run init
            # 2. Run boot
            # 3. Send message
            # 4. Verify response
            pass
```

---

## 6. Test Configuration

### 6.1 pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --strict-markers
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    e2e: marks tests as end-to-end tests
```

### 6.2 conftest.py

```python
# tests/conftest.py
import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_identity():
    return Mock(
        instance_name="TestMazyr",
        creator_name="TestCreator",
        species="Mazyr",
        is_configured=True
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
```

---

## 7. CI/CD Testing

### 7.1 GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run domain tests
        run: pytest tests/domain -v

      - name: Run app tests
        run: pytest tests/app -v

      - name: Run infra tests
        run: pytest tests/infra -v

      - name: Run coverage
        run: pytest --cov=mazyr --cov-report=xml
```

---

## 8. Testing Best Practices

1. **Domain tests must be pure** -- no I/O, no network, no DB
2. **Mock external dependencies** -- use `unittest.mock` for infra tests
3. **Test failure paths** -- not just happy paths
4. **Use fixtures** -- avoid setup duplication
5. **Parametrize** -- test multiple inputs with `@pytest.mark.parametrize`
6. **Fast feedback** -- domain tests must run in < 1s
7. **Integration tests use real DB** -- but with test isolation
