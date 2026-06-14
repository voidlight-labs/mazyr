import asyncio
from typing import Callable

from mazyr.domain.ports import ApprovalNotifierPort
from mazyr.domain.tool import ApprovalRequest, ApprovalResponse


class TelegramApprovalNotifier(ApprovalNotifierPort):
    """Telegram-based notifier for Tier-3 approval requests.

    Sends a message with command instructions; an external handler (e.g. the
    Telegram webhook) must call :meth:`resolve` when the Creator replies.
    """

    def __init__(self, send_message: Callable, chat_id: int):
        self._send_message = send_message
        self._chat_id = chat_id
        self._pending: dict[str, asyncio.Event] = {}
        self._responses: dict[str, ApprovalResponse] = {}

    async def notify(self, request: ApprovalRequest) -> None:
        params_text = "\n".join(f"  {k}: {v}" for k, v in request.proposed_params.items())
        text = (
            f"⚠️ Tier-3 approval required\n"
            f"Tool: {request.tool_call.name}\n"
            f"Request ID: {request.id}\n"
            f"Params:\n{params_text}\n\n"
            f"Reply:\n"
            f"  /approve {request.id}\n"
            f"  /deny {request.id}\n"
            f"  /modify {request.id} key=value"
        )
        await asyncio.to_thread(self._send_message, self._chat_id, text)

    async def read_response(
        self, request: ApprovalRequest, timeout_seconds: float
    ) -> ApprovalResponse:
        event = asyncio.Event()
        self._pending[request.id] = event
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
            return self._responses.pop(request.id)
        finally:
            self._pending.pop(request.id, None)

    def resolve(self, request_id: str, response: ApprovalResponse) -> bool:
        """Resolve a pending approval request. Called by the webhook handler."""
        event = self._pending.get(request_id)
        if event is None:
            return False
        self._responses[request_id] = response
        event.set()
        return True
