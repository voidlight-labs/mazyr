import asyncio

from mazyr.domain.ports import ApprovalNotifierPort
from mazyr.domain.tool import ApprovalRequest, ApprovalResponse
from mazyr.infrastructure.logger import get_logger

log = get_logger("approval")


class ApprovalManager:
    """Coordinates pending Tier-3 approval requests and Creator responses."""

    def __init__(
        self,
        notifier: ApprovalNotifierPort,
        timeout_seconds: float = 600.0,
    ):
        self._notifier = notifier
        self._timeout_seconds = timeout_seconds

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """Send approval request and wait for a Creator decision or timeout."""
        await self._notifier.notify(request)
        return await asyncio.wait_for(
            self._notifier.read_response(request, self._timeout_seconds),
            timeout=self._timeout_seconds,
        )
