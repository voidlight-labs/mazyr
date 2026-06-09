from dataclasses import dataclass, field


@dataclass
class Skill:
    """A learned capability."""

    name: str
    description: str
    category: str
    content: str
    version: str = "1.0"
    created_at: str = ""
    updated_at: str = ""
    usage_count: int = 0
    success_rate: float = 1.0

    def record_usage(self, success: bool):
        self.usage_count += 1
        alpha = 0.1
        self.success_rate = (1 - alpha) * self.success_rate + alpha * (1.0 if success else 0.0)


@dataclass
class SkillEvolution:
    """Log of how a skill has evolved over time."""

    skill_name: str
    events: list[dict] = field(default_factory=list)

    def add_event(self, event_type: str, description: str, timestamp: str):
        self.events.append(
            {
                "type": event_type,
                "description": description,
                "timestamp": timestamp,
            }
        )
