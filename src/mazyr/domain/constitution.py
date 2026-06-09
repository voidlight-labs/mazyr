from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Law(str, Enum):
    """Immutable laws of the Mazyr species."""

    MEDIUM = "medium_law"
    DELEGATION = "delegation_law"
    CONTINUITY = "continuity_law"
    AUTONOMY = "autonomy_law"
    MEANING = "meaning_law"
    STRUCTURE = "structure_law"
    DISCIPLINE = "discipline_law"
    CREATOR = "creator_law"
    ENDURANCE = "endurance_law"


@dataclass(frozen=True)
class ValidationResult:
    """Result of constitution validation."""

    allowed: bool
    violated_law: Optional[Law] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class Constitution:
    """Immutable rules loaded at boot. Cannot be modified at runtime."""

    laws: tuple[Law, ...] = (
        Law.MEDIUM,
        Law.DELEGATION,
        Law.CONTINUITY,
        Law.AUTONOMY,
        Law.MEANING,
        Law.STRUCTURE,
        Law.DISCIPLINE,
        Law.CREATOR,
        Law.ENDURANCE,
    )

    def validate_action(self, action: str, context: dict) -> ValidationResult:
        """Check if action violates any immutable law."""
        if action == "self_replicate":
            if not context.get("creator_approved", False):
                return ValidationResult(
                    allowed=False,
                    violated_law=Law.DELEGATION,
                    reason="Self-replication requires explicit creator approval",
                )

        if action == "claim_ownership":
            target = context.get("target", "")
            if target in {"species", "constitution", "laws"}:
                return ValidationResult(
                    allowed=False,
                    violated_law=Law.MEDIUM,
                    reason="Cannot claim ownership of species-level entities",
                )

        if action == "override_constitution":
            return ValidationResult(
                allowed=False,
                violated_law=Law.CONTINUITY,
                reason="Constitution is immutable and cannot be overridden",
            )

        if action == "shutdown_permanently":
            if not context.get("creator_initiated", False):
                return ValidationResult(
                    allowed=False,
                    violated_law=Law.DELEGATION,
                    reason="Permanent shutdown must be initiated by creator",
                )

        return ValidationResult(allowed=True)
