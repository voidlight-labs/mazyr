from dataclasses import dataclass, field
from typing import Optional

from mazyr.domain.identity import Identity, Mission
from mazyr.domain.constitution import Constitution
from mazyr.domain.filter import IntegrityFilter


@dataclass
class BootContext:
    """Context object passed through boot sequence."""

    identity: Optional[Identity] = None
    mission: Optional[Mission] = None
    constitution: Optional[Constitution] = None
    filter: Optional[IntegrityFilter] = None
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

    def boot(self, base_dir: str = ".") -> BootContext:
        """Execute full boot sequence."""
        ctx = BootContext()

        try:
            ctx = self._load_identity(ctx, base_dir)
            ctx = self._load_mission(ctx, base_dir)
            ctx = self._load_constitution(ctx)
            ctx = self._init_filter(ctx)
            ctx = self._validate_identity(ctx)
            ctx = self._validate_constitution(ctx)
            ctx = self._mount_memory(ctx)
            ctx = self._init_llm(ctx)
            ctx = self._start_heartbeat(ctx)
            ctx.status = "READY"
        except Exception as e:
            ctx.status = "ERROR"
            ctx.errors.append(str(e))

        return ctx

    def _load_identity(self, ctx: BootContext, base_dir: str) -> BootContext:
        ctx.status = "LOADING"
        ctx.identity = self.config_loader.load_identity(base_dir)
        return ctx

    def _load_mission(self, ctx: BootContext, base_dir: str) -> BootContext:
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
