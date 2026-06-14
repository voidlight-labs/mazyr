"""Procedural Memory tier (Tier 5) implementation.

Procedural memory stores skills and standard operating procedures as
file-based, version-controlled markdown documents. The runtime registry loads
them from disk, tracks which skill is active per session, and injects the
active skill into the prompt context via :class:`ContextAssembler`.
"""

from mazyr.application.skill_registry import SkillRegistry
from mazyr.domain.ports import ProceduralMemoryPort

# SkillRegistry already satisfies ProceduralMemoryPort. The alias documents the
# architectural role: skills are Mazyr's procedural memory tier.
ProceduralMemoryStore = SkillRegistry


__all__ = ["ProceduralMemoryStore", "ProceduralMemoryPort"]
