import asyncio
import getpass
import time
from collections import defaultdict
from typing import Any, Callable, Optional

import click
from pydantic import ValidationError

from mazyr.domain.constitution import Constitution
from mazyr.domain.events import ApprovalRequested, ApprovalResolved, ToolExecuted
from mazyr.domain.tool import (
    ApprovalRequest,
    ToolAuditEntry,
    ToolCall,
    ToolDefinition,
    ToolResult,
    ToolTier,
)
from mazyr.domain.tool_config import ToolRegistryConfig
from mazyr.infrastructure.logger import get_logger
from mazyr.infrastructure.memory_sqlite import SQLiteMemoryAdapter

log = get_logger("tool_registry")


class ToolRegistry:
    """Central tool execution engine with tier-based routing."""

    TIER0_BLACKLIST: set[str] = {
        "delete_file",
        "drop_database",
        "send_message_as_user",
        "disable_constitution_validator",
        "disable_integrity_filter",
        "escalate_own_tier",
    }

    # Keys whose values should be redacted before writing to the audit log.
    _SENSITIVE_PARAM_KEYS: frozenset[str] = frozenset(
        {
            "api_key",
            "token",
            "password",
            "secret",
            "authorization",
            "github_token",
            "telegram_bot_token",
            "embedding_api_key",
        }
    )

    def __init__(
        self,
        constitution: Constitution,
        sqlite_adapter: SQLiteMemoryAdapter,
        config: ToolRegistryConfig,
        approval_manager=None,
        event_bus=None,
    ):
        self.constitution = constitution
        self.sqlite = sqlite_adapter
        self.config = config
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable] = {}
        self._session_id: str = ""
        self._abuse_counters: dict[str, int] = defaultdict(int)
        self._consecutive_timeouts: int = 0
        self._session_whitelist: set[str] = set()
        self._approver: Optional[str] = None
        self._approval_manager = approval_manager
        self._event_bus = event_bus

    def set_session(self, session_id: str):
        self._session_id = session_id
        self._abuse_counters.clear()
        self._consecutive_timeouts = 0
        self._session_whitelist.clear()
        self._approver = None

    def register(self, definition: ToolDefinition, handler: Callable):
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler

    def get_tool_definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def is_tool_output(self, text: str) -> bool:
        return "<tool" in text and "</tool>" in text

    def execute(self, tool_call: ToolCall, context: dict) -> ToolResult:
        """Synchronous entry point. Uses the CLI-blocking Tier-3 path."""
        start = time.time()
        result = self._execute_with_tier3(tool_call, context, self._execute_tier3_sync)
        result.duration_ms = int((time.time() - start) * 1000)
        return result

    async def aexecute(self, tool_call: ToolCall, context: dict) -> ToolResult:
        """Asynchronous entry point. Supports notifications + timeouts."""
        start = time.time()
        result = await self._execute_with_tier3_async(tool_call, context, self._execute_tier3_async)
        result.duration_ms = int((time.time() - start) * 1000)
        return result

    def _execute_with_tier3(
        self,
        tool_call: ToolCall,
        context: dict,
        tier3_handler: Callable,
    ) -> ToolResult:
        td = self._validate(tool_call, context)
        if isinstance(td, ToolResult):
            return td

        if td.tier == ToolTier.SAFE:
            result = self._execute_tier1(tool_call, td, context)
        elif td.tier == ToolTier.SEMI_SAFE:
            result = self._execute_tier2(tool_call, td, context)
        elif td.tier == ToolTier.DANGEROUS:
            result = tier3_handler(tool_call, td, context)
        else:
            result = ToolResult(success=False, error=f"Unknown tier {td.tier}", status="DENIED")

        self._audit_log(tool_call, td.tier, result.status, result, context)
        self._publish_tool_executed(tool_call, result)
        return result

    async def _execute_with_tier3_async(
        self,
        tool_call: ToolCall,
        context: dict,
        tier3_handler: Callable,
    ) -> ToolResult:
        td = self._validate(tool_call, context)
        if isinstance(td, ToolResult):
            return td

        if td.tier == ToolTier.SAFE:
            result = self._execute_tier1(tool_call, td, context)
        elif td.tier == ToolTier.SEMI_SAFE:
            result = self._execute_tier2(tool_call, td, context)
        elif td.tier == ToolTier.DANGEROUS:
            result = await tier3_handler(tool_call, td, context)
        else:
            result = ToolResult(success=False, error=f"Unknown tier {td.tier}", status="DENIED")

        self._audit_log(tool_call, td.tier, result.status, result, context)
        self._publish_tool_executed(tool_call, result)
        return result

    def _validate(self, tool_call: ToolCall, context: dict) -> ToolDefinition | ToolResult:
        td = self._tools.get(tool_call.name)
        if td is None:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {tool_call.name}",
                status="DENIED",
            )

        # Tier 0 — hard reject
        if tool_call.name in self.TIER0_BLACKLIST or td.tier == ToolTier.BLACKLIST:
            self._audit_log(tool_call, td.tier, "DENIED", None, context)
            return ToolResult(
                success=False,
                error=f"Tool '{tool_call.name}' is blacklisted and cannot be executed.",
                status="DENIED",
            )

        # Constitution validation: tool intent must not violate immutable laws.
        cv = self.constitution.validate_action(
            tool_call.name,
            {
                "params": tool_call.params,
                "tier": td.tier,
                "platform": context.get("platform"),
                "creator_approved": tool_call.name in self._session_whitelist,
            },
        )
        if not cv.allowed:
            reason = cv.reason or f"violates {cv.violated_law.value}"
            self._audit_log(tool_call, td.tier, "DENIED", None, context)
            return ToolResult(
                success=False,
                error=f"Constitution check failed: {reason}",
                status="DENIED",
            )

        # Parameter validation (Pydantic when available, else schema fallback)
        param_error = self._validate_params(tool_call, td)
        if param_error:
            self._audit_log(tool_call, td.tier, "DENIED", None, context)
            return ToolResult(success=False, error=param_error, status="DENIED")

        return td

    def _execute_tier1(self, tc: ToolCall, td: ToolDefinition, context: dict) -> ToolResult:
        return self._run_handler(tc, context)

    def _execute_tier2(self, tc: ToolCall, td: ToolDefinition, context: dict) -> ToolResult:
        # Abuse check
        self._abuse_counters[tc.name] += 1
        thresholds = self.config.tier2.abuse_thresholds
        if (
            tc.name == "add_memory"
            and self._abuse_counters[tc.name] > thresholds.add_memory_per_session
        ):
            return ToolResult(
                success=False,
                error=f"add_memory blocked: exceeds {thresholds.add_memory_per_session} calls per session",
                status="DENIED",
            )

        result = self._run_handler(tc, context)
        if tc.name == "run_code" and not result.success:
            self._consecutive_timeouts += 1
            if self._consecutive_timeouts > thresholds.run_code_consecutive_timeout:
                return ToolResult(
                    success=False,
                    error="run_code suspended: too many consecutive failures",
                    status="SUSPENDED",
                )
        else:
            self._consecutive_timeouts = 0
        return result

    def _execute_tier3_sync(self, tc: ToolCall, td: ToolDefinition, context: dict) -> ToolResult:
        if context.get("platform") != "cli":
            return ToolResult(
                success=False,
                error=f"Tier 3 approval not available for platform: {context.get('platform', 'unknown')}",
                status="DENIED",
            )

        # Check session whitelist first
        if tc.name in self._session_whitelist:
            return self._run_handler(tc, context)

        from rich.console import Console

        console = Console()
        console.print(f"\n[yellow]⚠️  Tool '{tc.name}' requires Creator approval[/yellow]")
        console.print(f"  [dim]Params:[/dim] {self._redact_params(tc.params)}")
        reason = context.get("reason", "")
        if reason:
            console.print(f"  [dim]Reason:[/dim] {reason}")
        console.print(
            "  [bold](A)[/bold]llow once  [bold](S)[/bold]ession allow  [bold](D)[/bold]eny"
        )

        choice = click.prompt(
            "  Choice",
            type=click.Choice(["a", "s", "d"]),
            default="d",
            show_default=False,
        )

        if choice == "d":
            return ToolResult(success=False, error="Rejected by Creator", status="DENIED")

        self._approver = getpass.getuser()
        if choice == "s":
            self._session_whitelist.add(tc.name)
            console.print(f"  [dim]✅ '{tc.name}' approved for this session.[/dim]")

        return self._run_handler(tc, context)

    async def _execute_tier3_async(
        self, tc: ToolCall, td: ToolDefinition, context: dict
    ) -> ToolResult:
        if self._approval_manager is None:
            return ToolResult(
                success=False,
                error="No approval manager configured for async Tier-3 execution",
                status="DENIED",
            )

        if tc.name in self._session_whitelist:
            return self._run_handler(tc, context)

        request = ApprovalRequest(
            session_id=self._session_id or context.get("session_id", "unknown"),
            tool_call=tc,
            reason=context.get("reason", ""),
            proposed_params=tc.params,
        )
        self._persist_approval_request(request, "pending")
        self._publish(
            ApprovalRequested(
                request_id=request.id,
                tool_name=tc.name,
                params=self._redact_params(tc.params),
            )
        )

        try:
            response = await self._approval_manager.request_approval(request)
        except asyncio.TimeoutError:
            self._persist_approval_request(request.with_decision("timeout"), "timeout")
            self._publish(
                ApprovalResolved(
                    request_id=request.id,
                    decision="timeout",
                    approved_by=None,
                )
            )
            return ToolResult(
                success=False,
                error="Approval request timed out (auto-denied)",
                status="TIMEOUT",
            )
        except Exception as e:
            log.exception("Approval request failed for %s", tc.name)
            self._publish(
                ApprovalResolved(
                    request_id=request.id,
                    decision="error",
                    approved_by=None,
                )
            )
            return ToolResult(
                success=False,
                error=f"Approval system error: {e}",
                status="ERROR",
            )

        if response.decision == "deny":
            self._persist_approval_request(request.with_decision("denied"), "denied")
            self._publish(
                ApprovalResolved(
                    request_id=request.id,
                    decision="deny",
                    approved_by=response.approved_by,
                )
            )
            return ToolResult(success=False, error="Rejected by Creator", status="DENIED")

        if response.decision == "modify" and response.modified_params is not None:
            tc = ToolCall(name=tc.name, params=response.modified_params)
            self._persist_approval_request(
                request.with_decision("modified", response.approved_by), "modified"
            )
        else:
            self._persist_approval_request(
                request.with_decision("approved", response.approved_by), "approved"
            )

        self._approver = response.approved_by
        self._publish(
            ApprovalResolved(
                request_id=request.id,
                decision=response.decision,
                approved_by=response.approved_by,
            )
        )
        return self._run_handler(tc, context)

    def _persist_approval_request(self, request: ApprovalRequest, status: str):
        if self.sqlite is None:
            return
        try:
            self.sqlite.add_approval_request(
                {
                    "id": request.id,
                    "session_id": request.session_id,
                    "tool_name": request.tool_call.name,
                    "params": request.proposed_params,
                    "reason": request.reason,
                    "status": status,
                    "approved_by": request.approved_by,
                    "created_at": request.created_at,
                    "expires_at": request.expires_at,
                }
            )
        except Exception:
            log.exception("Failed to persist approval request %s", request.id)

    def _run_handler(self, tc: ToolCall, context: dict) -> ToolResult:
        handler = self._handlers.get(tc.name)
        if not handler:
            return ToolResult(success=False, error=f"No handler for {tc.name}", status="ERROR")
        try:
            return handler(tc.params, context)
        except Exception as e:
            log.exception("Tool handler failed for %s", tc.name)
            return ToolResult(success=False, error=str(e), status="ERROR")

    def _validate_params(self, tc: ToolCall, td: ToolDefinition) -> Optional[str]:
        # Prefer Pydantic model validation when registered.
        if td.param_model is not None:
            try:
                td.param_model(**tc.params)
                return None
            except ValidationError as e:
                return f"Parameter validation failed: {e.errors()[0]['msg']}"

        # Fallback to the legacy string schema used for LLM descriptions.
        schema = td.param_schema
        for key, expected_type in schema.items():
            if key not in tc.params:
                return f"Missing required parameter: {key}"
            value = tc.params[key]
            if expected_type == "string" and not isinstance(value, str):
                return f"Parameter '{key}' must be a string"
            if expected_type == "integer" and not isinstance(value, int):
                return f"Parameter '{key}' must be an integer"
            if expected_type == "boolean" and not isinstance(value, bool):
                return f"Parameter '{key}' must be a boolean"
        return None

    def _audit_log(
        self,
        tc: ToolCall,
        tier: int,
        status: str,
        result: Optional[ToolResult],
        context: dict,
    ):
        entry = ToolAuditEntry(
            session_id=self._session_id or context.get("session_id", "unknown"),
            tool_name=tc.name,
            tier=tier,
            params=self._redact_params(tc.params),
            result=result.model_dump_json() if result else None,
            status=status,
            approved_by=(
                self._approver if tier == ToolTier.DANGEROUS and status != "DENIED" else None
            ),
            duration_ms=result.duration_ms if result else 0,
        )
        try:
            self.sqlite.add_tool_audit_entry(entry)
        except Exception:
            log.exception("Failed to write tool audit log for %s", tc.name)
            # For dangerous tools that were actually executed, fail closed: we cannot
            # prove the operation happened. Denial/status cases are still safe, so we
            # only raise when an executed result would otherwise be returned.
            if tier == ToolTier.DANGEROUS and status not in ("DENIED",):
                raise ToolAuditError(
                    f"Audit logging failed for dangerous tool '{tc.name}'; denying execution."
                )

    def _publish(self, event) -> None:
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(event)
        except Exception:
            log.exception("Failed to publish event %s", getattr(event, "event_type", "?"))

    def _publish_tool_executed(self, tool_call: ToolCall, result: ToolResult) -> None:
        self._publish(
            ToolExecuted(
                tool_call=tool_call,
                tool_result=result,
            )
        )

    def _redact_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of params with sensitive values masked."""
        redacted: dict[str, Any] = {}
        for key, value in params.items():
            if key.lower() in self._SENSITIVE_PARAM_KEYS:
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = value
        return redacted


class ToolAuditError(Exception):
    """Raised when a dangerous tool cannot be recorded in the audit log."""
