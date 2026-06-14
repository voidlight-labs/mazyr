from typing import Optional

from mazyr.domain.message import Conversation
from mazyr.domain.skills import Skill


class LearnUseCase:
    """Extract patterns from conversations and update procedural memory."""

    def __init__(self, memory, skills_repo):
        self.memory = memory
        self.skills = skills_repo

    def extract_pattern(self, conversation: Conversation) -> Optional[dict]:
        """Analyze conversation for repeatable patterns."""
        messages = [m for m in conversation.messages if m.is_from_creator]
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

    def update_skill(self, skill_name: str, new_content: str, success: bool):
        """Update existing skill with new learning."""
        skill = self.skills.get(skill_name)
        if skill:
            skill.content += f"\n\n## Updated learning\n{new_content}"
            skill.record_usage(success)
            self.skills.save(skill)

    def create_skill(self, name: str, description: str, content: str, category: str):
        """Create new skill from learned pattern."""
        skill = Skill(
            name=name,
            description=description,
            category=category,
            content=content,
        )
        self.skills.save(skill)

    def _extract_keywords(self, messages) -> list[str]:
        """Simple keyword extraction from messages."""
        all_text = " ".join([m.content.lower() for m in messages])
        # Simple extraction: split and count unique words longer than 4 chars
        words = [w.strip(".,!?;:") for w in all_text.split() if len(w) > 4]
        # Return most common (simplified)
        seen = set()
        result = []
        for w in words:
            if w not in seen and len(result) < 5:
                seen.add(w)
                result.append(w)
        return result
