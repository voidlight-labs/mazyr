import hashlib
import hmac
import logging
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from mazyr.application.chat import ChatUseCase
from mazyr.domain.message import Message

app = FastAPI(title="Mazyr Webhook")
log = logging.getLogger(__name__)

chat_uc: ChatUseCase = None


class WhatsAppMessagePayload(BaseModel):
    id: str = Field(default="unknown")
    text: str = Field(default="")
    from_me: bool = Field(default=True)
    timestamp: str = Field(default="")


class WhatsAppWebhookPayload(BaseModel):
    message: Optional[WhatsAppMessagePayload] = Field(default=None)


class TelegramChatPayload(BaseModel):
    id: int = Field(default=0)


class TelegramMessagePayload(BaseModel):
    message_id: int = Field(default=0)
    text: str = Field(default="")
    chat: TelegramChatPayload = Field(default_factory=TelegramChatPayload)


class TelegramWebhookPayload(BaseModel):
    message: Optional[TelegramMessagePayload] = Field(default=None)


def _get_webhook_secret(config) -> Optional[str]:
    """Retrieve the configured webhook verification secret, if any."""
    if config is None:
        return None
    return getattr(config, "webhook_secret", None)


def _verify_signature(payload: bytes, signature: Optional[str], secret: Optional[str]) -> bool:
    """Verify an HMAC-SHA256 signature when a secret is configured."""
    if not secret:
        return False
    if not signature:
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _build_message_from_whatsapp(payload: WhatsAppWebhookPayload) -> Message:
    msg = payload.message or WhatsAppMessagePayload()
    return Message(
        id=msg.id,
        content=msg.text,
        sender="creator" if not msg.from_me else "unknown",
        platform="whatsapp",
        timestamp=msg.timestamp,
    )


def _build_message_from_telegram(payload: TelegramWebhookPayload) -> Message:
    msg = payload.message or TelegramMessagePayload()
    return Message(
        id=str(msg.message_id),
        content=msg.text,
        sender="creator",
        platform="telegram",
        timestamp="",
    )


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    x_signature: Optional[str] = Header(default=None, alias="X-Signature"),
):
    """Receive WhatsApp webhook."""
    body = await request.body()
    config = getattr(chat_uc, "_config", None)
    secret = _get_webhook_secret(config)

    if secret and not _verify_signature(body, x_signature, secret):
        raise HTTPException(status_code=401, detail="Invalid signature")
    if not secret:
        log.warning("No webhook_secret configured; skipping WhatsApp signature verification")

    try:
        payload = WhatsAppWebhookPayload.model_validate_json(body)
    except Exception as e:
        log.warning("Invalid WhatsApp payload: %s", e)
        raise HTTPException(status_code=422, detail="Invalid payload") from e

    if payload.message is None:
        return JSONResponse({"success": True, "reply": None, "error": None})

    msg = _build_message_from_whatsapp(payload)
    result = await chat_uc.areceive(msg)

    return JSONResponse(
        {
            "success": result.success,
            "reply": result.reply,
            "error": result.error,
        }
    )


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_signature: Optional[str] = Header(default=None, alias="X-Signature"),
):
    """Receive Telegram webhook."""
    body = await request.body()
    config = getattr(chat_uc, "_config", None)
    secret = _get_webhook_secret(config)

    if secret and not _verify_signature(body, x_signature, secret):
        raise HTTPException(status_code=401, detail="Invalid signature")
    if not secret:
        log.warning("No webhook_secret configured; skipping Telegram signature verification")

    try:
        payload = TelegramWebhookPayload.model_validate_json(body)
    except Exception as e:
        log.warning("Invalid Telegram payload: %s", e)
        raise HTTPException(status_code=422, detail="Invalid payload") from e

    if payload.message is None:
        return JSONResponse({"success": True, "reply": None})

    msg = _build_message_from_telegram(payload)
    result = await chat_uc.areceive(msg)

    return JSONResponse(
        {
            "success": result.success,
            "reply": result.reply,
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "instance": "Aria"}
