"""Mazyr CLI -- Modern agentic command-line interface.

Usage:
    mazyr init          Initialize a new Mazyr instance
    mazyr boot          Boot the instance
    mazyr status        Check instance status
    mazyr stop          Stop the instance
    mazyr sync          Sync memory to GitHub
    mazyr chat          Interactive terminal chat
    mazyr qdrant enable Enable Qdrant semantic memory
    mazyr --version     Show version
    mazyr --help        Show help

Inspired by: docker, git, gh, ollama
"""

from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mazyr.application.bootstrap import Bootstrap
from mazyr.application.chat import ChatUseCase
from mazyr.application.memory_dedup import MemoryDeduplicator
from mazyr.application.memory_extraction import BatchedExtraction
from mazyr.application.memory_system import MemorySystem
from mazyr.domain.instance_config import InstanceConfig
from mazyr.domain.message import Message
from mazyr.infrastructure.config_loader import ConfigLoader
from mazyr.infrastructure.docker_manager import DockerComposeManager
from mazyr.infrastructure.embeddings_openai import OpenAIEmbeddingAdapter
from mazyr.infrastructure.filesystem import FilesystemAdapter
from mazyr.infrastructure.llm_cloud import CloudLLM
from mazyr.infrastructure.llm_local import LocalLLM
from mazyr.infrastructure.llm_router import InferencePreference, LLMRouter
from mazyr.infrastructure.memory_qdrant import QdrantMemoryAdapter
from mazyr.infrastructure.memory_sqlite import SQLiteMemoryAdapter
from mazyr.infrastructure.messenger_telegram import TelegramAdapter
from mazyr.infrastructure.paths import MAZYR_HOME

__version__ = "0.1.0"

console = Console()


def _shutdown(ctx, chat_use_case=None):
    if chat_use_case:
        chat_use_case.close()
    worker = getattr(ctx, "worker", None)
    if worker:
        try:
            worker.stop()
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _build_adapters(config: InstanceConfig):
    """Build infrastructure adapters from InstanceConfig."""
    sqlite_memory = SQLiteMemoryAdapter(db_path=config.sqlite_path)
    semantic_memory = None
    if config.qdrant_enabled:
        embedding_key = config.embedding_api_key
        if not embedding_key and "api.openai.com" in config.base_url:
            embedding_key = config.api_key
        embedder = None
        if embedding_key:
            embedder = OpenAIEmbeddingAdapter(
                api_key=embedding_key,
                base_url=config.embedding_base_url,
                model=config.embedding_model,
                dimensions=config.embedding_dimensions,
            )
        semantic_memory = QdrantMemoryAdapter(
            host=config.qdrant_host,
            port=config.qdrant_port,
            vector_size=config.embedding_dimensions,
            embedder=embedder,
        )
    memory_adapter = MemorySystem(sqlite_memory, semantic_memory)

    local_llm = None
    if config.use_local_llm:
        local_llm = LocalLLM(model_path=config.local_model_path)

    cloud_llm = None
    if config.use_cloud_llm:
        cloud_llm = CloudLLM(
            api_key=config.api_key or "",
            base_url=config.base_url,
            model=config.model,
        )

    preference = InferencePreference(config.inference_preference.lower())
    llm_router = LLMRouter(local_llm, cloud_llm, preference=preference)

    return memory_adapter, llm_router


def _print_banner():
    """Print Mazyr banner."""
    console.print(
        Panel.fit(
            "[bold blue]Mazyr[/bold blue] — Synthetic Partner Node\n"
            "[dim]Born from the void, Guided by the light.[/dim]",
            border_style="blue",
        )
    )


def _require_config(loader: ConfigLoader) -> InstanceConfig:
    """Load config or exit with error."""
    config = loader.load_config()
    if config is None:
        console.print(
            Panel.fit(
                "[red]No instance found.[/red]\nRun [bold]mazyr init[/bold] to create one.",
                title="❌ Error",
                border_style="red",
            )
        )
        raise click.Abort()
    return config


def _telegram_handler(chat_use_case: ChatUseCase, telegram: TelegramAdapter):
    """Build a Telegram polling handler around the chat use case."""

    def handle(payload: dict):
        from datetime import datetime

        message = Message(
            id=str(payload.get("message_id", "unknown")),
            content=payload.get("text", ""),
            sender=payload.get("from", "creator"),
            platform="telegram",
            timestamp=datetime.now().isoformat(),
        )
        result = chat_use_case.receive(message)
        chat_id = payload.get("chat_id")
        if chat_id is None:
            return
        if result.success and result.reply:
            telegram.send_message(chat_id, result.reply)
        elif result.error:
            telegram.send_message(chat_id, f"Error: {result.error}")

    return handle


def _run_telegram_daemon(ctx, memory_adapter, llm_router):
    """Run Telegram long polling in the foreground."""
    if not ctx.config.telegram_bot_token:
        console.print(
            Panel.fit(
                "[red]Telegram bot token not configured.[/red]\n"
                "Run [bold]mazyr init[/bold] and set a Telegram bot token first.",
                title="❌ Error",
                border_style="red",
            )
        )
        raise click.Abort()

    telegram = TelegramAdapter(ctx.config.telegram_bot_token)
    embedder = getattr(getattr(memory_adapter, "qdrant", None), "embedder", None)
    extraction_queue = BatchedExtraction(llm_router, memory_adapter, embedder) if embedder else None
    deduplicator = MemoryDeduplicator(memory_adapter.semantic, embedder) if embedder else None
    chat_use_case = ChatUseCase(
        ctx.identity,
        ctx.mission,
        ctx.filter,
        memory_adapter,
        llm_router,
        tool_registry=getattr(ctx, "tool_registry", None),
        config=ctx.config,
        tool_config=getattr(ctx, "tool_config", None),
        extraction_queue=extraction_queue,
        skill_registry=getattr(ctx, "skill_registry", None),
        deduplicator=deduplicator,
        event_bus=getattr(ctx, "event_bus", None),
        learn_use_case=getattr(ctx, "learn", None),
    )
    console.print("[green]Telegram daemon listening.[/green] Press Ctrl+C to stop.")
    try:
        telegram.listen(_telegram_handler(chat_use_case, telegram))
    except KeyboardInterrupt:
        console.print("\n[dim]Telegram daemon stopped.[/dim]")
    finally:
        _shutdown(ctx, chat_use_case)


# ──────────────────────────────────────────────────────────────────────────────
# CLI Group
# ──────────────────────────────────────────────────────────────────────────────


@click.group(
    invoke_without_command=True,
    context_settings=dict(help_option_names=["-h", "--help"]),
)
@click.option("--version", "-v", is_flag=True, help="Show version and exit.")
@click.pass_context
def cli(ctx, version):
    """Mazyr — Synthetic Partner Node

    \b
    Quick Start:
        mazyr init      Create your instance
        mazyr boot      Start Mazyr
        mazyr status    Check health
        mazyr chat      Talk to Mazyr

    \b
    Management:
        mazyr stop      Stop Mazyr
        mazyr sync      Sync memory to GitHub
    """
    if version:
        console.print(f"Mazyr [bold blue]{__version__}[/bold blue]")
        ctx.exit(0)

    if ctx.invoked_subcommand is None:
        # No subcommand given — show help
        console.print(ctx.get_help())
        ctx.exit(0)


# ──────────────────────────────────────────────────────────────────────────────
# Lifecycle Commands
# ──────────────────────────────────────────────────────────────────────────────


@cli.command()
@click.option(
    "--base-dir",
    default=str(MAZYR_HOME),
    help="Instance directory (default: ~/.mazyr)",
    show_default=True,
)
def init(base_dir):
    """Initialize a new Mazyr instance."""
    _print_banner()

    # ── Identity ──
    console.print("\n[bold]📝 Identity[/bold]")
    instance_name = click.prompt("  Instance name", type=str)
    creator_name = click.prompt("  Creator name", type=str)
    creator_contact = click.prompt("  Creator contact", type=str, default="", show_default=False)
    vessel_type = click.prompt(
        "  Vessel type",
        type=click.Choice(["laptop", "mini-pc", "desktop", "cloud-vps"]),
        default="laptop",
    )

    # ── Mission ──
    console.print("\n[bold]🎯 Mission[/bold]")
    primary = click.prompt("  Primary mission", type=str)
    secondary = click.prompt("  Secondary mission", type=str, default="", show_default=False)
    scope = click.prompt("  Scope (comma-separated)", type=str, default="general")

    # ── LLM Configuration ──
    console.print("\n[bold]🧠 LLM Configuration[/bold]")
    inference_preference = click.prompt(
        "  Inference preference",
        type=click.Choice(["local", "cloud", "hybrid"]),
        default="hybrid",
    )

    api_key = ""
    base_url = "https://api.moonshot.cn/v1"
    model = "kimi-k2-6"
    if inference_preference in ("cloud", "hybrid"):
        api_key = click.prompt("  Cloud API key", type=str, default="", show_default=False)
        base_url = click.prompt("  Base URL", type=str, default="https://api.moonshot.cn/v1")
        model = click.prompt("  Model", type=str, default="kimi-k2-6")

    local_model_path = ""
    if inference_preference in ("local", "hybrid"):
        local_model_path = click.prompt(
            "  Local model path", type=str, default="", show_default=False
        )

    # ── Memory (Docker / Qdrant) ──
    console.print("\n[bold]💾 Memory[/bold]")
    docker = DockerComposeManager()
    qdrant_enabled = False
    if docker.is_available:
        console.print("  [dim]🐳 Docker detected — auto-starting Qdrant...[/dim]")
        if docker.start() and docker.wait_for_healthy(timeout=30):
            console.print("  [green]✅ Qdrant ready[/green]")
            qdrant_enabled = True
        else:
            console.print("  [yellow]⚠️ Qdrant unavailable — SQLite only[/yellow]")
    else:
        console.print(
            "  [yellow]🐳 Docker not found — using SQLite only.[/yellow]\n"
            "  Install Docker to enable Qdrant semantic memory."
        )

    embedding_api_key = ""
    embedding_base_url = "https://api.openai.com/v1"
    embedding_model = "text-embedding-3-small"
    embedding_dimensions = 1536
    if qdrant_enabled:
        console.print("\n[bold]🔎 Semantic Memory Embeddings[/bold]")
        embedding_api_key = click.prompt(
            "  OpenAI embedding API key",
            type=str,
            default="",
            show_default=False,
        )
        embedding_base_url = click.prompt(
            "  Embedding base URL",
            type=str,
            default="https://api.openai.com/v1",
        )
        embedding_model = click.prompt(
            "  Embedding model",
            type=str,
            default="text-embedding-3-small",
        )
        embedding_dimensions = click.prompt("  Embedding dimensions", type=int, default=1536)

    # ── Integrations ──
    console.print("\n[bold]🔗 Integrations (optional)[/bold]")
    telegram_bot_token = click.prompt(
        "  Telegram bot token", type=str, default="", show_default=False
    )
    github_token = click.prompt("  GitHub token", type=str, default="", show_default=False)
    github_repo = click.prompt(
        "  GitHub repo (user/repo)", type=str, default="", show_default=False
    )
    relay_endpoint = click.prompt("  Relay endpoint", type=str, default="", show_default=False)
    instance_id = click.prompt("  Instance ID", type=str, default=f"{instance_name.lower()}-001")

    # ── Write files ──
    fs = FilesystemAdapter(base_dir)
    fs.init_mazyr_dir()

    # Copy bundled skills into the instance skills directory.
    bundled_skills_dir = Path(__file__).parent.parent.parent / "skills"
    copied_skills = fs.copy_bundled_skills(bundled_skills_dir)
    if copied_skills:
        console.print(f"  [dim]📋 Copied {len(copied_skills)} skill(s) to instance.[/dim]")

    from datetime import datetime

    fs.write_identity(f"""---
instance_name: {instance_name}
species: Mazyr
creator: {creator_name}
creator_contact: {creator_contact}
date_provisioned: {datetime.now().isoformat()}
vessel_type: {vessel_type}
---

# {instance_name} Identity

This instance is a Mazyr — a synthetic partner node.
It does not possess independent substance.
All output is derivative signal from the Creator.
""")

    fs.write_mission(f"""---
primary: "{primary}"
secondary: "{secondary}"
scope: [{scope}]
---

# Mission Configuration

## Primary
{primary}

## Secondary
{secondary}

## Scope
{scope}
""")

    config_data = {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "local_model_path": local_model_path,
        "inference_preference": inference_preference,
        "sqlite_path": str(fs.memory_dir / "mazyr.db"),
        "qdrant_enabled": qdrant_enabled,
        "embedding_api_key": embedding_api_key or None,
        "embedding_base_url": embedding_base_url if qdrant_enabled else None,
        "embedding_model": embedding_model if qdrant_enabled else None,
        "embedding_dimensions": embedding_dimensions if qdrant_enabled else None,
        "telegram_bot_token": telegram_bot_token or None,
        "github_token": github_token or None,
        "github_repo": github_repo or None,
        "relay_endpoint": relay_endpoint or None,
        "instance_id": instance_id,
    }
    config_data = {k: v for k, v in config_data.items() if v not in (None, "")}
    fs.write_config(yaml.safe_dump(config_data, default_flow_style=False, sort_keys=False))

    console.print(f"\n[green]✅ Instance '{instance_name}' initialized.[/green]")
    console.print(f"   Location: {base_dir}/")
    console.print("   Run [bold]mazyr boot[/bold] to start.")


@cli.command()
@click.option(
    "--base-dir",
    default=str(MAZYR_HOME),
    help="Instance directory (default: ~/.mazyr)",
)
@click.option(
    "--daemon",
    is_flag=True,
    help="Keep running and listen for configured integrations.",
)
def boot(base_dir, daemon):
    """Boot the Mazyr instance."""
    console.print("🚀 Booting Mazyr...")

    loader = ConfigLoader(base_dir)
    config = _require_config(loader)

    # Ensure Qdrant is running if enabled
    if getattr(config, "qdrant_enabled", False):
        docker = DockerComposeManager()
        if docker.is_available and not docker.is_running():
            console.print("[dim]  🐳 Starting Qdrant...[/dim]")
            docker.start()

    memory_adapter, llm_router = _build_adapters(config)
    bootstrap = Bootstrap(loader, memory_adapter, llm_router)
    ctx = bootstrap.boot(base_dir)

    if ctx.status == "READY":
        console.print(
            Panel.fit(
                f"[bold]{ctx.identity.instance_name}[/bold] is active\n"
                f"  Creator: {ctx.identity.creator_name}\n"
                f"  Mission: {ctx.mission.primary}\n"
                f"  LLM: {ctx.config.inference_preference}\n"
                f"  Memory: SQLite + {'Qdrant' if getattr(ctx.config, 'qdrant_enabled', False) else 'SQLite only'}\n"
                f"  Status: [green]READY[/green]",
                title="🌟 Mazyr",
                border_style="green",
            )
        )
        if daemon:
            _run_telegram_daemon(ctx, memory_adapter, llm_router)
    else:
        console.print(
            Panel.fit(
                "[red]Boot failed[/red]\n" + "\n".join(f"  • {e}" for e in ctx.errors),
                title="❌ Error",
                border_style="red",
            )
        )
        raise click.Abort()


@cli.command()
@click.option(
    "--base-dir",
    default=str(MAZYR_HOME),
    help="Instance directory (default: ~/.mazyr)",
)
def status(base_dir):
    """Check Mazyr instance status."""
    loader = ConfigLoader(base_dir)
    identity = loader.load_identity(base_dir)

    if not identity:
        console.print(
            Panel.fit(
                "[red]No instance found.[/red]\nRun [bold]mazyr init[/bold] to create one.",
                title="❌ Error",
                border_style="red",
            )
        )
        raise click.Abort()

    config = loader.load_config()
    if not config:
        console.print(
            Panel.fit(
                "[red]Config not found.[/red]\nRun [bold]mazyr init[/bold] to create one.",
                title="❌ Error",
                border_style="red",
            )
        )
        raise click.Abort()

    memory_adapter, _ = _build_adapters(config)
    from mazyr.application.audit import AuditUseCase
    from mazyr.domain.constitution import Constitution
    from mazyr.domain.filter import IntegrityFilter

    custom_rules = loader.load_custom_rules()
    if not isinstance(custom_rules, list):
        custom_rules = None
    filter_engine = IntegrityFilter(custom_rules=custom_rules)

    audit = AuditUseCase(
        identity=identity,
        filter_engine=filter_engine,
        memory=memory_adapter,
        constitution=Constitution(),
    )
    health = audit.health_check()

    table = Table(title=f"Mazyr Instance: {identity.instance_name}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Instance", identity.instance_name)
    table.add_row("Creator", identity.creator_name)
    table.add_row("Species", identity.species)
    table.add_row("Vessel", identity.vessel_type)
    table.add_row("Configured", "✅" if identity.is_configured else "❌")
    table.add_row("Overall", f"[green]{health['overall']}[/green]")

    if config:
        table.add_row("Inference", config.inference_preference)
        table.add_row("Model", config.model)
        table.add_row("SQLite", config.sqlite_path)
        qdrant_on = getattr(config, "qdrant_enabled", False)
        table.add_row("Qdrant", "✅" if qdrant_on else "❌")
        table.add_row("Instance ID", config.instance_id)
        table.add_row("Memory entries", str(health["memory"]["entries"]))

    console.print(table)


@cli.command()
def stop():
    """Stop the Mazyr instance."""
    console.print("🛑 Stopping Mazyr...")
    docker = DockerComposeManager()
    if docker.is_available:
        docker.stop()
    console.print("[dim]Instance stopped.[/dim]")


# ──────────────────────────────────────────────────────────────────────────────
# Qdrant Commands
# ──────────────────────────────────────────────────────────────────────────────


@cli.group()
def qdrant():
    """Manage Qdrant semantic memory."""


@qdrant.command()
@click.option(
    "--base-dir",
    default=str(MAZYR_HOME),
    help="Instance directory (default: ~/.mazyr)",
)
def enable(base_dir):
    """Start Qdrant container and enable semantic memory in config."""
    loader = ConfigLoader(base_dir)
    config = _require_config(loader)
    _ = config  # config validated, used below via file reload

    config_path = Path(base_dir) / "config.yaml"
    with open(config_path) as f:
        config_data = yaml.safe_load(f) or {}

    # Check if already enabled and running
    if config_data.get("qdrant_enabled", False):
        docker = DockerComposeManager()
        if docker.is_available and docker.is_running() and docker.wait_for_healthy(timeout=5):
            console.print("[green]✅ Qdrant is already enabled and running.[/green]")
            return
        console.print(
            "[yellow]⚠️  Qdrant is enabled in config but not running — restarting...[/yellow]"
        )

    console.print("[dim]🐳 Starting Qdrant...[/dim]")
    docker = DockerComposeManager()
    if not docker.is_available:
        console.print(
            Panel.fit(
                "[red]Docker is not available.[/red]\nInstall Docker and try again.",
                title="❌ Error",
                border_style="red",
            )
        )
        raise click.Abort()

    if not docker.start():
        console.print(
            Panel.fit(
                "[red]Failed to start Qdrant container.[/red]\nCheck Docker status and try again.",
                title="❌ Error",
                border_style="red",
            )
        )
        raise click.Abort()

    console.print("[dim]  Waiting for Qdrant to be healthy...[/dim]")
    if not docker.wait_for_healthy(timeout=60):
        docker.stop()
        console.print(
            Panel.fit(
                "[red]Qdrant container started but not healthy within 60s.[/red]\n"
                "Check logs with: docker logs mazyr-qdrant",
                title="❌ Error",
                border_style="red",
            )
        )
        raise click.Abort()

    console.print("  [green]✅ Qdrant ready[/green]")

    # Update config
    config_data["qdrant_enabled"] = True

    # Prompt for embedding config if missing
    if not config_data.get("embedding_api_key"):
        console.print("\n[bold]🔎 Semantic Memory Embeddings[/bold]")
        config_data["embedding_api_key"] = (
            click.prompt("  OpenAI embedding API key", type=str, default="", show_default=False)
            or None
        )
        config_data["embedding_base_url"] = click.prompt(
            "  Embedding base URL", type=str, default="https://api.openai.com/v1"
        )
        config_data["embedding_model"] = click.prompt(
            "  Embedding model", type=str, default="text-embedding-3-small"
        )
        config_data["embedding_dimensions"] = click.prompt(
            "  Embedding dimensions", type=int, default=1536
        )

    config_data = {k: v for k, v in config_data.items() if v not in (None, "")}
    fs = FilesystemAdapter(base_dir)
    fs.write_config(yaml.safe_dump(config_data, default_flow_style=False, sort_keys=False))

    console.print("[green]✅ Qdrant enabled. Run [bold]mazyr boot[/bold] to use it.[/green]")


@cli.command()
@click.option(
    "--base-dir",
    default=str(MAZYR_HOME),
    help="Instance directory (default: ~/.mazyr)",
)
def sync(base_dir):
    """Sync memory snapshot to GitHub and optional relay."""
    import asyncio

    config = _require_config(ConfigLoader(base_dir))
    memory_adapter, _ = _build_adapters(config)

    from mazyr.application.sync import SyncUseCase
    from mazyr.infrastructure.github_sync import GitHubSyncAdapter
    from mazyr.infrastructure.relay_client import RelayClient

    github = None
    if config.github_token and config.github_repo:
        github = GitHubSyncAdapter(token=config.github_token, repo=config.github_repo)

    relay = None
    if config.relay_endpoint:
        relay = RelayClient(
            endpoint=config.relay_endpoint,
            instance_id=config.instance_id,
        )

    sync_uc = SyncUseCase(memory=memory_adapter, github_adapter=github, relay_client=relay)

    console.print("🔄 Syncing memory...")
    result = sync_uc.snapshot_to_github(config.instance_id)
    if result.get("status") == "no_github_adapter":
        console.print("[dim]GitHub sync not configured.[/dim]")
    elif "content" in result or result.get("status") == "ok":
        console.print("[green]✅ GitHub snapshot pushed.[/green]")
    else:
        console.print(f"[yellow]GitHub sync result: {result}[/yellow]")

    if relay:
        relay_ok = asyncio.run(sync_uc.sync_to_relay())
        if relay_ok:
            console.print("[green]✅ Relay sync sent.[/green]")
        else:
            console.print("[yellow]⚠️ Relay sync skipped (not connected).[/yellow]")

    console.print("[dim]Sync complete.[/dim]")


@cli.command()
@click.option(
    "--base-dir",
    default=str(MAZYR_HOME),
    help="Instance directory (default: ~/.mazyr)",
)
def chat(base_dir):
    """Start interactive terminal chat."""
    loader = ConfigLoader(base_dir)
    config = _require_config(loader)
    memory_adapter, llm_router = _build_adapters(config)
    bootstrap = Bootstrap(loader, memory_adapter, llm_router)
    ctx = bootstrap.boot(base_dir)

    if ctx.status != "READY":
        console.print(
            Panel.fit(
                "[red]Chat unavailable[/red]\n" + "\n".join(f"  • {e}" for e in ctx.errors),
                title="❌ Error",
                border_style="red",
            )
        )
        raise click.Abort()

    embedder = getattr(getattr(memory_adapter, "qdrant", None), "embedder", None)
    extraction_queue = BatchedExtraction(llm_router, memory_adapter, embedder) if embedder else None
    deduplicator = MemoryDeduplicator(memory_adapter.semantic, embedder) if embedder else None
    chat_use_case = ChatUseCase(
        ctx.identity,
        ctx.mission,
        ctx.filter,
        memory_adapter,
        llm_router,
        tool_registry=getattr(ctx, "tool_registry", None),
        config=ctx.config,
        tool_config=getattr(ctx, "tool_config", None),
        extraction_queue=extraction_queue,
        deduplicator=deduplicator,
        skill_registry=getattr(ctx, "skill_registry", None),
        event_bus=getattr(ctx, "event_bus", None),
        learn_use_case=getattr(ctx, "learn", None),
    )

    console.print(
        Panel.fit(
            "[bold]Interactive Chat[/bold]\n"
            "Type your message below. Use [bold]exit[/bold] or [bold]quit[/bold] to leave.",
            title="💬 Chat",
            border_style="blue",
        )
    )

    try:
        while True:
            user_input = click.prompt("You", type=str)
            if user_input.lower() in ("exit", "quit"):
                console.print("[dim]Goodbye.[/dim]")
                break

            if user_input.lower().startswith("/learn"):
                learn = getattr(ctx, "learn", None)
                if learn:
                    pattern = learn.extract_pattern(chat_use_case.conversation)
                    if pattern:
                        console.print(f"[dim]📚 Learned pattern:[/dim] {pattern}")
                    else:
                        console.print("[dim]No recurring pattern detected yet.[/dim]")
                else:
                    console.print("[dim]Learning not available.[/dim]")
                continue

            from datetime import datetime
            from uuid import uuid4

            message = Message(
                id=str(uuid4()),
                content=user_input,
                sender="creator",
                platform="cli",
                timestamp=datetime.now().isoformat(),
            )
            console.print(f"[cyan]{ctx.identity.instance_name}:[/cyan]")
            response_text = ""
            for event in chat_use_case.receive_stream(message):
                if event[0] == "token":
                    console.print(event[1], end="")
                    response_text += event[1]
                elif event[0] == "tool_call":
                    console.print(f"\n[dim]⚙️ {event[1]}({event[2]})[/dim]")
                elif event[0] == "tool_result":
                    status = "✓" if event[1].success else "✗"
                    snippet = (event[1].data or event[1].error or "")[:80]
                    console.print(f"[dim]{status} → {snippet}[/dim]")
                elif event[0] == "error":
                    console.print(f"\n[red]Error: {event[1]}[/red]")
                elif event[0] == "done":
                    pass  # already printed via tokens
            console.print()  # trailing newline
    finally:
        _shutdown(ctx, chat_use_case)


# ──────────────────────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
