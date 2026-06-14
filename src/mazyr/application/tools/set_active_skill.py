from mazyr.domain.tool import ToolResult


def handle(params: dict, context: dict) -> ToolResult:
    skill_registry = context.get("skill_registry")
    if not skill_registry:
        return ToolResult(success=False, error="Skill registry not available")

    name = params.get("name", "")
    if not name:
        skill_registry.deactivate()
        return ToolResult(success=True, data="Skill deactivated")

    if skill_registry.activate(name):
        skill = skill_registry.active_skill
        return ToolResult(
            success=True,
            data=f"Activated skill '{skill.name}' ({skill.category})",
        )

    available = ", ".join(s.name for s in skill_registry.list_skills())
    return ToolResult(
        success=False, error=f"Skill '{name}' not found. Available: {available or '(none)'}"
    )
