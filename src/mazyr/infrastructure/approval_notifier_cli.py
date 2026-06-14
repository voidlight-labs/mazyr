import asyncio
import getpass

import click
from rich.console import Console

from mazyr.domain.ports import ApprovalNotifierPort
from mazyr.domain.tool import ApprovalRequest, ApprovalResponse


class CLIApprovalNotifier(ApprovalNotifierPort):
    """Synchronous-style CLI prompt for Tier-3 approval, wrapped for async use."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    async def notify(self, request: ApprovalRequest) -> None:
        self.console.print("\n")
        self.console.print(
            f"[yellow]⚠️  Tool '{request.tool_call.name}' requires Creator approval[/yellow]"
        )
        self.console.print(f"  [dim]Request ID:[/dim] {request.id}")
        self.console.print(f"  [dim]Params:[/dim] {request.proposed_params}")
        if request.reason:
            self.console.print(f"  [dim]Reason:[/dim] {request.reason}")
        self.console.print(
            "  [bold](A)[/bold]llow once  [bold](S)[/bold]ession allow  [bold](M)[/bold]odify  [bold](D)[/bold]eny"
        )

    async def read_response(
        self, request: ApprovalRequest, timeout_seconds: float
    ) -> ApprovalResponse:
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, self._prompt, request),
            timeout=timeout_seconds,
        )

    def _prompt(self, request: ApprovalRequest) -> ApprovalResponse:
        choice = click.prompt(
            "  Choice",
            type=click.Choice(["a", "s", "m", "d"]),
            default="d",
            show_default=False,
        )

        if choice == "d":
            return ApprovalResponse(decision="deny", approved_by=getpass.getuser())

        modified_params: dict | None = None
        if choice == "m":
            modified_params = dict(request.proposed_params)
            self.console.print("  [dim]Enter new values (blank to keep current):[/dim]")
            for key, value in list(modified_params.items()):
                new_value = click.prompt(
                    f"    {key} [{value}]", default=str(value), show_default=False
                )
                if new_value != str(value):
                    modified_params[key] = new_value

        approver = getpass.getuser()
        return ApprovalResponse(
            decision="approve" if choice in ("a", "s") else "modify",
            modified_params=modified_params,
            approved_by=approver,
        )
