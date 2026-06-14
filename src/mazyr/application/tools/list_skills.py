from mazyr.domain.tool import ToolResult


def handle(params: dict, context: dict) -> ToolResult:
    skill_registry = context.get("skill_registry")
    if not skill_registry:
        return ToolResult(success=False, error="Skill registry not available")

    skills = skill_registry.list_skills()
    active = skill_registry.active_skill

    lines = []
    if active:
        lines.append(f"Active: {active.name} (v{active.version}) - {active.category}")
    else:
        lines.append("Active: (none)")

    lines.append("\nAvailable skills:")
    for skill in skills:
        marker = " *" if active and active.name == skill.name else ""
        lines.append(f"  - {skill.name} (v{skill.version}) [{skill.category}]{marker}")

    return ToolResult(success=True, data="\n".join(lines))
