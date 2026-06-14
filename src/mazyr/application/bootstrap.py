from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from mazyr.domain.constitution import Constitution
from mazyr.domain.filter import IntegrityFilter
from mazyr.domain.identity import Identity, Mission
from mazyr.domain.instance_config import InstanceConfig
from mazyr.domain.tool_config import ToolRegistryConfig


@dataclass
class BootContext:
    """Context object passed through boot sequence."""

    identity: Optional[Identity] = None
    mission: Optional[Mission] = None
    constitution: Optional[Constitution] = None
    filter: Optional[IntegrityFilter] = None
    config: Optional[InstanceConfig] = None
    tool_config: Optional[ToolRegistryConfig] = None
    tool_registry: Optional[object] = None
    skill_registry: Optional[object] = None
    approval_manager: Optional[object] = None
    event_bus: Optional[object] = None
    audit: Optional[object] = None
    sync: Optional[object] = None
    learn: Optional[object] = None
    relay_client: Optional[object] = None
    worker: Optional[object] = None
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
            ctx = self._load_tool_registry_config(ctx)
            ctx = self._init_event_bus(ctx)
            ctx = self._init_tool_registry(ctx)
            ctx = self._load_skills(ctx)
            ctx = self._init_audit(ctx)
            ctx = self._init_learn(ctx)
            ctx = self._init_relay(ctx)
            ctx = self._init_sync(ctx)
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

    def _load_tool_registry_config(self, ctx: BootContext) -> BootContext:
        ctx.tool_config = self.config_loader.load_tool_registry_config()
        return ctx

    def _init_event_bus(self, ctx: BootContext) -> BootContext:
        from mazyr.application.event_bus import EventBus

        ctx.event_bus = EventBus()
        return ctx

    def _init_tool_registry(self, ctx: BootContext) -> BootContext:
        from mazyr.application.approval_manager import ApprovalManager
        from mazyr.application.tool_registry import ToolRegistry
        from mazyr.application.tools.registry import register_all
        from mazyr.infrastructure.approval_notifier_cli import CLIApprovalNotifier

        sqlite = getattr(self.memory_adapter, "sqlite", self.memory_adapter)
        timeout_minutes = 10
        if ctx.tool_config and hasattr(ctx.tool_config, "tier3"):
            value = getattr(ctx.tool_config.tier3, "approval_timeout_minutes", timeout_minutes)
            if isinstance(value, int):
                timeout_minutes = value
        ctx.approval_manager = ApprovalManager(
            notifier=CLIApprovalNotifier(),
            timeout_seconds=timeout_minutes * 60,
        )
        registry = ToolRegistry(
            constitution=ctx.constitution,
            sqlite_adapter=sqlite,
            config=ctx.tool_config,
            approval_manager=ctx.approval_manager,
            event_bus=ctx.event_bus,
        )
        register_all(registry)
        ctx.tool_registry = registry
        return ctx

    def _load_skills(self, ctx: BootContext) -> BootContext:
        from mazyr.application.skill_registry import SkillRegistry
        from mazyr.infrastructure.skill_loader import SkillLoader

        loader = SkillLoader(
            user_dir=(
                Path(ctx.config.sqlite_path).parent.parent / "skills"
                if ctx.config and ctx.config.sqlite_path
                else None
            ),
        )
        ctx.skill_registry = SkillRegistry(loader)
        return ctx

    def _init_audit(self, ctx: BootContext) -> BootContext:
        from mazyr.application.audit import AuditUseCase

        ctx.audit = AuditUseCase(
            identity=ctx.identity,
            filter_engine=ctx.filter,
            memory=self.memory_adapter,
            constitution=ctx.constitution,
        )
        return ctx

    def _init_learn(self, ctx: BootContext) -> BootContext:
        from mazyr.application.learn import LearnUseCase

        ctx.learn = LearnUseCase(procedural_memory=ctx.skill_registry)
        return ctx

    def _init_relay(self, ctx: BootContext) -> BootContext:
        if not ctx.config or not ctx.config.relay_endpoint:
            return ctx

        from mazyr.infrastructure.relay_client import RelayClient

        ctx.relay_client = RelayClient(
            endpoint=ctx.config.relay_endpoint,
            instance_id=ctx.config.instance_id,
        )
        return ctx

    def _init_sync(self, ctx: BootContext) -> BootContext:
        from mazyr.application.sync import SyncUseCase

        github = None
        if ctx.config and ctx.config.github_token and ctx.config.github_repo:
            from mazyr.infrastructure.github_sync import GitHubSyncAdapter

            github = GitHubSyncAdapter(
                token=ctx.config.github_token,
                repo=ctx.config.github_repo,
            )
        ctx.sync = SyncUseCase(
            memory=self.memory_adapter,
            github_adapter=github,
            relay_client=ctx.relay_client,
        )
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
        if self.memory_adapter and self.llm_router:
            from mazyr.application.memory_worker import MaintenanceWorker

            worker = MaintenanceWorker(self.memory_adapter, self.llm_router)
            worker.start()
            ctx.worker = worker
        return ctx
