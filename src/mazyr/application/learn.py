"""Learning use case: extract repeatable patterns and update procedural memory."""

from typing import Optional

from mazyr.domain.message import Conversation
from mazyr.domain.ports import ProceduralMemoryPort


class LearnUseCase:
    """Extract patterns from conversations and update procedural memory (skills)."""

    def __init__(self, procedural_memory: ProceduralMemoryPort):
        self.procedural_memory = procedural_memory

    def extract_pattern(self, conversation: Conversation) -> Optional[dict]:
        """Analyze conversation for repeatable topics."""
        messages = [m for m in conversation.messages if m.sender == "creator"]
        if len(messages) < 3:
            return None

        keywords = self._extract_keywords(messages)
        if len(keywords) >= 2:
            return {
                "type": "recurring_topic",
                "keywords": keywords,
                "frequency": len(messages),
            }
        return None

    def update_skill(self, skill_name: str, new_content: str, success: bool) -> bool:
        """Update an existing skill with new learning."""
        skill = self.procedural_memory.get(skill_name)
        if skill is None:
            return False
        skill.content += f"\n\n## Updated learning\n{new_content}"
        self.procedural_memory.record_usage(skill_name, success)
        return True

    def create_skill(
        self,
        name: str,
        description: str,
        content: str,
        category: str,
    ) -> bool:
        """Create a new skill from a learned pattern.

        Returns True if created, False if a skill with that name already exists.
        """
        from mazyr.domain.skills import Skill

        if self.procedural_memory.get(name):
            return False
        skill = Skill(
            name=name,
            description=description,
            category=category,
            content=content,
        )
        self.procedural_memory.save(skill)
        self.procedural_memory.activate(name)
        return True

    def _extract_keywords(self, messages: list) -> list[str]:
        """Simple keyword extraction from creator messages."""
        all_text = " ".join([m.content.lower() for m in messages])
        words = [w.strip(".,!?;:") for w in all_text.split() if len(w) > 4]
        seen: set[str] = set()
        result: list[str] = []
        for w in words:
            if w not in seen and len(result) < 5:
                seen.add(w)
                result.append(w)
        return result
