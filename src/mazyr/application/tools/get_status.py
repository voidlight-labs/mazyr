from datetime import datetime

from mazyr.domain.tool import ToolResult


def handle(params: dict, context: dict) -> ToolResult:
    identity = context.get("identity")
    mission = context.get("mission")
    config = context.get("config")

    lines = []
    if identity:
        lines.append(f"Instance: {identity.instance_name}")
        lines.append(f"Creator: {identity.creator_name}")
        lines.append(f"Vessel: {identity.vessel_type}")
    if mission:
        lines.append(f"Mission: {mission.primary}")
    if config:
        lines.append(f"Inference: {config.inference_preference}")
        lines.append(f"Qdrant: {'enabled' if config.qdrant_enabled else 'disabled'}")

    now = datetime.now().isoformat()
    lines.append(f"Timestamp: {now}")

    return ToolResult(success=True, data="\n".join(lines))
