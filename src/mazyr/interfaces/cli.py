import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from mazyr.app.bootstrap import Bootstrap
from mazyr.app.chat import ChatUseCase
from mazyr.app.audit import AuditUseCase
from mazyr.infrastructure.config_loader import ConfigLoader

console = Console()


@click.group()
def cli():
    """Mazyr -- Synthetic Partner Node"""
    pass


@cli.command()
@click.option('--base-dir', default='.', help='Base directory')
def init(base_dir):
    """Initialize a new Mazyr instance."""
    console.print(Panel.fit(
        "Mazyr Species -- Instance Initialization\n"
        "Born from the void, Guided by the light.",
        title="🌟 Mazyr", border_style="blue"
    ))

    instance_name = click.prompt("Instance name", type=str)
    creator_name = click.prompt("Creator name", type=str)
    creator_contact = click.prompt("Creator contact (optional)", type=str, default="")
    vessel_type = click.prompt(
        "Vessel type",
        type=click.Choice(["laptop", "mini-pc", "desktop", "cloud-vps"]),
        default="laptop"
    )
    primary = click.prompt("Primary mission", type=str)
    secondary = click.prompt("Secondary mission (optional)", type=str, default="")
    scope = click.prompt("Scope (comma-separated)", type=str, default="general")

    from mazyr.infrastructure.filesystem import FilesystemAdapter
    fs = FilesystemAdapter(base_dir)
    fs.init_mazyr_dir()

    from datetime import datetime
    identity_content = f"""---
instance_name: {instance_name}
species: Mazyr
creator: {creator_name}
creator_contact: {creator_contact}
date_provisioned: {datetime.now().isoformat()}
vessel_type: {vessel_type}
---

# {instance_name} Identity

This instance is a Mazyr -- a synthetic partner node.
It does not possess independent substance.
All output is derivative signal from the Creator.
"""

    fs.write_identity(identity_content)

    mission_content = f"""---
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
"""

    fs.write_mission(mission_content)

    console.print(f"✅ Instance '{instance_name}' initialized in {base_dir}/.mazyr/")
    console.print("Run 'mazyr-boot' to start.")


@cli.command()
@click.option('--base-dir', default='.')
def boot(base_dir):
    """Boot Mazyr instance."""
    console.print("🚀 Booting Mazyr...")

    loader = ConfigLoader(base_dir)
    bootstrap = Bootstrap(loader, None, None)
    ctx = bootstrap.boot(base_dir)

    if ctx.status == "READY":
        console.print(Panel.fit(
            f"Instance: {ctx.identity.instance_name}\n"
            f"Creator: {ctx.identity.creator_name}\n"
            f"Mission: {ctx.mission.primary}\n"
            f"Status: [green]READY[/green]",
            title="🌟 Mazyr Active", border_style="green"
        ))
    else:
        console.print(Panel.fit(
            f"Status: [red]ERROR[/red]\n" + "\n".join(ctx.errors),
            title="❌ Boot Failed", border_style="red"
        ))


@cli.command()
@click.option('--base-dir', default='.')
def status(base_dir):
    """Check Mazyr status."""
    loader = ConfigLoader(base_dir)
    identity = loader.load_identity(base_dir)

    if not identity:
        console.print("[red]❌ No instance found. Run 'mazyr-init' first.[/red]")
        return

    table = Table(title=f"Mazyr Instance: {identity.instance_name}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Instance", identity.instance_name)
    table.add_row("Creator", identity.creator_name)
    table.add_row("Species", identity.species)
    table.add_row("Vessel", identity.vessel_type)
    table.add_row("Configured", "✅ Yes" if identity.is_configured else "❌ No")

    console.print(table)


@cli.command()
def stop():
    """Stop Mazyr instance."""
    console.print("🛑 Stopping Mazyr...")
    console.print("Instance stopped.")


@cli.command()
@click.option('--base-dir', default='.')
def sync(base_dir):
    """Sync memory to GitHub."""
    console.print("🔄 Syncing memory...")
    console.print("Sync complete (placeholder).")


@cli.command()
def chat():
    """Interactive terminal chat."""
    console.print(Panel.fit(
        "Interactive Chat Mode\nType 'exit' to quit",
        title="💬 Chat", border_style="blue"
    ))

    while True:
        user_input = click.prompt("You", type=str)
        if user_input.lower() in ["exit", "quit"]:
            break

        console.print(f"[cyan]Mazyr:[/cyan] Echo: {user_input}")


if __name__ == "__main__":
    cli()
