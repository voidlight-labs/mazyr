from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from mazyr.application.chat import ChatUseCase
from mazyr.domain.message import Message

app = FastAPI(title="Mazyr Webhook")

chat_uc: ChatUseCase = None


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """Receive WhatsApp webhook."""
    payload = await request.json()

    msg = Message(
        id=payload.get("id", "unknown"),
        content=payload.get("text", ""),
        sender="creator" if payload.get("from_me") == False else "unknown",
        platform="whatsapp",
        timestamp=payload.get("timestamp", ""),
    )

    result = chat_uc.receive(msg)

    return JSONResponse({
        "success": result.success,
        "reply": result.reply,
        "error": result.error,
    })


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Receive Telegram webhook."""
    payload = await request.json()
    message = payload.get("message", {})

    msg = Message(
        id=str(message.get("message_id", 0)),
        content=message.get("text", ""),
        sender="creator",
        platform="telegram",
        timestamp="",
    )

    result = chat_uc.receive(msg)
    return JSONResponse({
        "success": result.success,
        "reply": result.reply,
    })


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "instance": "Aria"}
