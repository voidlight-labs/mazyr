# MTS-04: Interfaces
## Mazyr Technical Specification -- Interfaces

**Version:** 1.0
**Dependencies:** Application Layer, Infrastructure Layer
**Python Version:** 3.11+

---

## 1. Overview

The Interface Layer provides entry points for human and system interaction with Mazyr. All interfaces are thin adapters that delegate to the Application Layer.

---

## 2. CLI Interface

### 2.1 File
`src/mazyr/interfaces/cli.py`

### 2.2 Commands

| Command | Purpose | Phase |
|---|---|---|
| `mazyr-init` | Interactive instance initialization | Setup |
| `mazyr-boot` | Boot sequence and start daemon | Runtime |
| `mazyr-status` | Health check and status report | Monitoring |
| `mazyr-stop` | Graceful shutdown | Runtime |
| `mazyr-sync` | Manual memory sync to GitHub | Maintenance |
| `mazyr-chat` | Interactive terminal chat | Development |

### 2.3 Implementation

```python
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
    \"\"\"Mazyr -- Synthetic Partner Node\"\"\"
    pass

@cli.command()
@click.option('--base-dir', default='.', help='Base directory')
def init(base_dir):
    \"\"\"Initialize a new Mazyr instance.\"\"\"
    console.print(Panel.fit(
        "Mazyr Species -- Instance Initialization\\n"
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
    identity_content = f\"\"\"---
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
\"\"\"

    fs.write_identity(identity_content)

    mission_content = f\"\"\"---
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
\"\"\"

    fs.write_mission(mission_content)

    console.print(f"✅ Instance '{instance_name}' initialized in {base_dir}/.mazyr/")
    console.print("Run 'mazyr-boot' to start.")

@cli.command()
@click.option('--base-dir', default='.')
def boot(base_dir):
    \"\"\"Boot Mazyr instance.\"\"\"
    console.print("🚀 Booting Mazyr...")

    loader = ConfigLoader(base_dir)
    bootstrap = Bootstrap(loader, None, None)
    ctx = bootstrap.boot(base_dir)

    if ctx.status == "READY":
        console.print(Panel.fit(
            f"Instance: {ctx.identity.instance_name}\\n"
            f"Creator: {ctx.identity.creator_name}\\n"
            f"Mission: {ctx.mission.primary}\\n"
            f"Status: [green]READY[/green]",
            title="🌟 Mazyr Active", border_style="green"
        ))
    else:
        console.print(Panel.fit(
            f"Status: [red]ERROR[/red]\\n" + "\\n".join(ctx.errors),
            title="❌ Boot Failed", border_style="red"
        ))

@cli.command()
@click.option('--base-dir', default='.')
def status(base_dir):
    \"\"\"Check Mazyr status.\"\"\"
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
def chat():
    \"\"\"Interactive terminal chat.\"\"\"
    console.print(Panel.fit(
        "Interactive Chat Mode\\nType 'exit' to quit",
        title="💬 Chat", border_style="blue"
    ))

    while True:
        user_input = click.prompt("You", type=str)
        if user_input.lower() in ["exit", "quit"]:
            break

        console.print(f"[cyan]Mazyr:[/cyan] Echo: {user_input}")

if __name__ == "__main__":
    cli()
```

### 2.4 Entry Points (pyproject.toml)

```toml
[project.scripts]
mazyr-init = "mazyr.interfaces.cli:init"
mazyr-boot = "mazyr.interfaces.cli:boot"
mazyr-status = "mazyr.interfaces.cli:status"
mazyr-stop = "mazyr.interfaces.cli:stop"
mazyr-sync = "mazyr.interfaces.cli:sync"
mazyr-chat = "mazyr.interfaces.cli:chat"
```

---

## 3. Webhook Interface

### 3.1 File
`src/mazyr/interfaces/whatsapp_webhook.py`

### 3.2 FastAPI Webhook

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from mazyr.app.chat import ChatUseCase
from mazyr.domain.message import Message

app = FastAPI(title="Mazyr Webhook")

chat_uc: ChatUseCase = None

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    \"\"\"Receive WhatsApp webhook.\"\"\"
    payload = await request.json()

    msg = Message(
        id=payload.get("id", "unknown"),
        content=payload.get("text", ""),
        sender="creator" if payload.get("from_me") == False else "unknown",
        platform="whatsapp",
        timestamp=payload.get("timestamp", "")
    )

    result = chat_uc.receive(msg)

    return JSONResponse({
        "success": result.success,
        "reply": result.reply,
        "error": result.error
    })

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    \"\"\"Receive Telegram webhook.\"\"\"
    payload = await request.json()
    message = payload.get("message", {})

    msg = Message(
        id=str(message.get("message_id", 0)),
        content=message.get("text", ""),
        sender="creator",
        platform="telegram",
        timestamp=""
    )

    result = chat_uc.receive(msg)
    return JSONResponse({
        "success": result.success,
        "reply": result.reply
    })

@app.get("/health")
async def health_check():
    \"\"\"Health check endpoint.\"\"\"
    return {"status": "ok", "instance": "Aria"}
```

---

## 4. Relay Client

### 4.1 File
`src/mazyr/interfaces/relay_client.py`

### 4.2 WebSocket Relay

```python
import asyncio
import websockets
import json
from typing import Callable


class RelayClient:
    \"\"\"WebSocket client for cloud relay.\"\"\"

    def __init__(self, endpoint: str, instance_id: str):
        self.endpoint = endpoint
        self.instance_id = instance_id
        self.ws = None
        self.running = False
        self.on_message: Callable = None

    async def connect(self):
        uri = f"{self.endpoint}/ws/{self.instance_id}"
        self.ws = await websockets.connect(uri)
        self.running = True
        asyncio.create_task(self._heartbeat())
        await self._listen()

    async def _listen(self):
        while self.running:
            try:
                message = await self.ws.recv()
                data = json.loads(message)
                if self.on_message:
                    self.on_message(data)
            except websockets.exceptions.ConnectionClosed:
                self.running = False
                break

    async def _heartbeat(self):
        while self.running:
            await asyncio.sleep(60)
            if self.ws:
                await self.ws.send(json.dumps({"type": "heartbeat"}))

    async def send(self, data: dict):
        if self.ws:
            await self.ws.send(json.dumps(data))

    async def disconnect(self):
        self.running = False
        if self.ws:
            await self.ws.close()
```

---

## 5. Systemd Service

### 5.1 File
`/etc/systemd/system/mazyr.service`

```ini
[Unit]
Description=Mazyr Instance -- Synthetic Partner Node
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=%I
WorkingDirectory=/home/%I/mazyr-core
ExecStart=/home/%I/mazyr-core/.venv/bin/mazyr-boot
ExecStop=/home/%I/mazyr-core/.venv/bin/mazyr-stop
Restart=always
RestartSec=10

MemoryMax=28G
CPUQuota=80%

Environment=PYTHONPATH=/home/%I/mazyr-core/src
Environment=MAZYR_MODE=daemon
Environment=MAZYR_LOG_LEVEL=info

[Install]
WantedBy=multi-user.target
```

### 5.2 Enable

```bash
sudo cp mazyr.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mazyr@khayren
sudo systemctl start mazyr@khayren
sudo systemctl status mazyr@khayren
```
