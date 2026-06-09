from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from mazyr.domain.constitution import Constitution
from mazyr.domain.filter import IntegrityFilter
from mazyr.domain.identity import Identity, Mission
from mazyr.domain.instance_config import InstanceConfig
from mazyr.infrastructure.paths import MAZYR_HOME


@dataclass
class BootContext:
    """Context object passed through boot sequence."""

    identity: Optional[Identity] = None
    mission: Optional[Mission] = None
    constitution: Optional[Constitution] = None
    filter: Optional[IntegrityFilter] = None
    config: Optional[InstanceConfig] = None
    memory_ready: bool = False
    llm_ready: bool = False
    status: str = "INIT"  # INIT -> LOADING -> VALIDATING -> MOUNTING -> READY -> ERROR
    errors: list[str] = field(default_factory=list)


class Bootstrap:
    """Boot sequence for Mazyr instance. Each step is atomic and can be retried."""

    def __init__(self, config_loader, memory_adapter, llm_router):
        self.config_loader = config_loader
        self.memory_adapter = memory_adapter
        self.llm_router = llm_router

    def boot(self, base_dir: str | Path | None = None) -> BootContext:
        """Execute full boot sequence."""
        ctx = BootContext()

        try:
            ctx = self._load_config(ctx)
            ctx = self._load_identity(ctx, base_dir)
            ctx = self._load_mission(ctx, base_dir)
            ctx = self._load_constitution(ctx)
            ctx = self._init_filter(ctx)
            ctx = self._validate_identity(ctx)
            ctx = self._validate_constitution(ctx)
            ctx = self._validate_config(ctx)
            ctx = self._mount_memory(ctx)
            ctx = self._init_llm(ctx)
            ctx = self._start_heartbeat(ctx)
            ctx.status = "READY"
        except Exception as e:
            ctx.status = "ERROR"
            ctx.errors.append(str(e))

        return ctx

    def _load_config(self, ctx: BootContext) -> BootContext:
        ctx.status = "LOADING"
        ctx.config = self.config_loader.load_config()
        if ctx.config is None:
            raise RuntimeError("Runtime config not found. Run 'mazyr-init' first.")
        return ctx

    def _load_identity(self, ctx: BootContext, base_dir: str | Path | None) -> BootContext:
        ctx.identity = self.config_loader.load_identity(base_dir)
        return ctx

    def _load_mission(self, ctx: BootContext, base_dir: str | Path | None) -> BootContext:
        ctx.mission = self.config_loader.load_mission(base_dir)
        return ctx

    def _load_constitution(self, ctx: BootContext) -> BootContext:
        ctx.constitution = Constitution()
        return ctx

    def _init_filter(self, ctx: BootContext) -> BootContext:
        custom_rules = self.config_loader.load_custom_rules()
        if not isinstance(custom_rules, list):
            custom_rules = None
        ctx.filter = IntegrityFilter(custom_rules=custom_rules)
        return ctx

    def _validate_identity(self, ctx: BootContext) -> BootContext:
        ctx.status = "VALIDATING"
        if not ctx.identity or not ctx.identity.is_configured:
            raise RuntimeError("Identity not configured. Run 'mazyr-init' first.")
        return ctx

    def _validate_constitution(self, ctx: BootContext) -> BootContext:
        return ctx

    def _validate_config(self, ctx: BootContext) -> BootContext:
        if not ctx.config:
            raise RuntimeError("Config is required to boot.")
        if not ctx.config.use_cloud_llm and not ctx.config.use_local_llm:
            raise RuntimeError(
                "No LLM configured. Provide api_key for cloud, local_model_path for local, "
                "or both for hybrid."
            )
        return ctx

    def _mount_memory(self, ctx: BootContext) -> BootContext:
        ctx.status = "MOUNTING"
        if self.memory_adapter:
            self.memory_adapter.connect()
        ctx.memory_ready = True
        return ctx

    def _init_llm(self, ctx: BootContext) -> BootContext:
        if self.llm_router:
            self.llm_router.initialize()
        ctx.llm_ready = True
        return ctx

    def _start_heartbeat(self, ctx: BootContext) -> BootContext:
        return ctx
