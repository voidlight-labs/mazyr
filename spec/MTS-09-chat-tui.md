# MTS-09: Chat TUI Interface

## Overview

Chat TUI adalah interface utama untuk interaksi real-time dengan Aria. Bukan terminal jadul, tapi **modern chat experience** yang setara Kimi CLI / Codex CLI / Claude Code.

**Philosophy:** Chat adalah **primary surface** untuk Mazyr. Dashboard (MTS-12) adalah secondary (observability). TUI harus bisa jalan tanpa browser, tanpa GUI, tapi experience-nya modern.

**Framework:** Textual (built on Rich) --- async, reactive, Markdown-native, syntax highlight built-in.

---

## 1. Architecture

### 1.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    MazyrChatApp (Textual)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Header    │  │  ChatThread │  │    StatusBar        │ │
│  │  (clock,    │  │  (scroll)   │  │  Qalb, Nafs, Mem    │ │
│  │   status)   │  │             │  │                     │ │
│  └─────────────┘  │  ┌───────┐  │  └─────────────────────┘ │
│                    │  │ Msg 1 │  │  ┌─────────────────────┐ │
│  ┌─────────────┐  │  │ Msg 2 │  │  │    InputArea        │ │
│  │  Sidebar    │  │  │ Msg 3 │  │  │  > _                │ │
│  │  (memory    │  │  └───────┘  │  │  hint: /help        │ │
│  │   browser)  │  │             │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                              │                              │
│                              ↓ WebSocket                    │
│                    ┌─────────────────────┐                  │
│                    │   mazyr-daemon      │                  │
│                    │   (FastAPI)         │                  │
│                    └─────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 File Structure

```
src/mazyr/interfaces/chat_tui/
├── __init__.py
├── app.py                    # Main Textual App
├── screens/
│   ├── __init__.py
│   ├── main_chat.py          # Primary chat screen
│   ├── memory_browser.py     # Side panel memory view
│   └── file_preview.py       # File/image preview overlay
├── widgets/
│   ├── __init__.py
│   ├── chat_message.py       # Message bubble (user/assistant)
│   ├── code_block.py         # Syntax highlighted code + actions
│   ├── typing_indicator.py   # Animated "thinking..."
│   ├── file_attachment.py    # @file mention renderer
│   ├── image_viewer.py       # Image display (ASCII/terminal)
│   ├── diff_view.py          # Code diff (before/after)
│   ├── status_bar.py         # Qalb, Nafs, Memory, Mode
│   ├── command_palette.py    # / command autocomplete
│   └── input_area.py         # Multi-line input with history
└── styles.tcss               # Textual CSS
```

---

## 2. Core Widgets

### 2.1 ChatMessage

Message bubble dengan role-based styling. Support Markdown, code blocks, file attachments, images.

```python
# src/mazyr/interfaces/chat_tui/widgets/chat_message.py
from textual.widgets import Static, Markdown
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive

class ChatMessage(Vertical):
    CSS = """
    ChatMessage {
        width: 100%;
        margin: 1 0;
    }
    .user-bubble {
        align-horizontal: right;
        background: $primary-darken-2;
        color: $text;
        padding: 1 2;
        border: solid $primary;
        width: auto;
        max-width: 85%;
    }
    .assistant-bubble {
        align-horizontal: left;
        background: $surface;
        color: $text;
        padding: 1 2;
        border: solid $success;
        width: auto;
        max-width: 85%;
    }
    .message-meta {
        text-style: bold;
        margin-bottom: 1;
        height: 1;
    }
    .user-meta { color: $primary; }
    .assistant-meta { color: $success; }
    .timestamp { text-style: dim; color: $text-muted; }
    """

    content = reactive("")
    role = reactive("assistant")
    timestamp = reactive("")
    attachments = reactive([])  # list of FileAttachment | ImageViewer

    def __init__(self, content: str, role: str, timestamp: str = "", attachments: list = None, **kwargs):
        super().__init__(**kwargs)
        self.content = content
        self.role = role
        self.timestamp = timestamp or datetime.now().strftime("%H:%M:%S")
        self.attachments = attachments or []

    def compose(self):
        bubble_class = "user-bubble" if self.role == "user" else "assistant-bubble"
        meta_class = "user-meta" if self.role == "user" else "assistant-meta"
        name = "Khayren" if self.role == "user" else "Aria"
        
        with Horizontal(classes=bubble_class):
            with Vertical():
                yield Static(f"{name}  [{self.timestamp}]", classes=f"message-meta {meta_class}")
                
                # Attachments rendered before content
                for att in self.attachments:
                    yield att
                
                # Main content --- Markdown untuk assistant, plain untuk user
                if self.role == "assistant":
                    yield Markdown(self.content, id="msg-content")
                else:
                    yield Static(self.content, id="msg-content")
    
    def watch_content(self, new_content: str):
        """Called saat streaming --- update Markdown widget."""
        content_widget = self.query_one("#msg-content", Markdown if self.role == "assistant" else Static)
        content_widget.update(new_content)
        
        # Auto-scroll parent
        self.parent.scroll_end(animate=False)
```

---

### 2.2 CodeBlock (Syntax Highlight + Actions)

Code block dengan syntax highlighting, language label, copy button, dan run-in-skill button.

```python
# src/mazyr/interfaces/chat_tui/widgets/code_block.py
from textual.widgets import Static, Button
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
import pyperclip

class CodeBlock(Vertical):
    CSS = """
    CodeBlock {
        width: 100%;
        margin: 1 0;
        border: solid $surface-lighten-1;
    }
    .code-header {
        height: 1;
        background: $surface-lighten-1;
        color: $text-muted;
        padding: 0 1;
        text-style: bold;
    }
    .code-body {
        background: $surface-darken-1;
        padding: 1;
        overflow-x: auto;
    }
    .code-actions {
        height: 1;
        padding: 0 1;
        background: $surface-lighten-1;
    }
    Button {
        width: auto;
        height: 1;
        margin: 0 1;
    }
    """

    code = reactive("")
    language = reactive("text")
    filename = reactive("")  # kalau dari @file mention

    def __init__(self, code: str, language: str = "text", filename: str = "", **kwargs):
        super().__init__(**kwargs)
        self.code = code
        self.language = language
        self.filename = filename

    def compose(self):
        # Header: language + filename
        header_text = self.language.upper()
        if self.filename:
            header_text += f"  |  {self.filename}"
        yield Static(header_text, classes="code-header")
        
        # Body: syntax highlighted code
        # Rich Syntax auto-detect language
        from rich.syntax import Syntax
        syntax = Syntax(self.code, self.language, theme="monokai", line_numbers=True)
        yield Static(syntax, classes="code-body")
        
        # Actions: Copy, Run as Skill, Diff (kalau ada before/after)
        with Horizontal(classes="code-actions"):
            yield Button("📋 Copy", id="btn-copy", variant="primary")
            yield Button("▶ Run", id="btn-run", variant="success")
            if self.filename:
                yield Button("📝 Edit", id="btn-edit", variant="warning")
    
    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-copy":
            pyperclip.copy(self.code)
            self.notify("Copied to clipboard!", severity="information")
        elif event.button.id == "btn-run":
            # Emit event ke app untuk execute as skill
            self.post_message(self.CodeRunRequest(self.code, self.language))
        elif event.button.id == "btn-edit":
            self.post_message(self.CodeEditRequest(self.filename, self.code))
    
    class CodeRunRequest(Message):
        def __init__(self, code: str, language: str):
            self.code = code
            self.language = language
            super().__init__()
    
    class CodeEditRequest(Message):
        def __init__(self, filename: str, code: str):
            self.filename = filename
            self.code = code
            super().__init__()
```

---

### 2.3 TypingIndicator

Animated "Aria is thinking..." dengan progress bar dan step info (kalau skill execution).

```python
# src/mazyr/interfaces/chat_tui/widgets/typing_indicator.py
from textual.widgets import Static, ProgressBar
from textual.containers import Horizontal
from textual.reactive import reactive
import asyncio

class TypingIndicator(Horizontal):
    CSS = """
    TypingIndicator {
        height: auto;
        margin: 1 0;
        padding: 1 2;
        background: $surface-darken-1;
        border: solid $text-muted;
        color: $text-muted;
        width: auto;
    }
    .indicator-text {
        text-style: italic;
        width: auto;
    }
    ProgressBar {
        width: 20;
        margin-left: 2;
    }
    """

    text = reactive("Aria is thinking")
    step_info = reactive("")  # kalau skill: "Step 2/4: Generate Prompt"
    progress = reactive(0.0)  # 0.0 - 1.0
    dots = reactive(0)

    def __init__(self, text: str = "Aria is thinking", **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self._animate_task = None

    def compose(self):
        yield Static(self._render_text(), id="indicator-text", classes="indicator-text")
        yield ProgressBar(id="indicator-progress", total=100, show_eta=False)
    
    def _render_text(self) -> str:
        base = self.text
        if self.step_info:
            base += f" | {self.step_info}"
        base += "." * self.dots
        return base
    
    def on_mount(self):
        self._animate_task = asyncio.create_task(self._animate_dots())
    
    async def _animate_dots(self):
        while True:
            self.dots = (self.dots + 1) % 4
            await asyncio.sleep(0.5)
    
    def watch_text(self, text: str):
        self._update_text()
    
    def watch_step_info(self, info: str):
        self._update_text()
    
    def watch_dots(self, dots: int):
        self._update_text()
    
    def watch_progress(self, progress: float):
        bar = self.query_one("#indicator-progress", ProgressBar)
        bar.update(progress=progress * 100)
    
    def _update_text(self):
        text_widget = self.query_one("#indicator-text", Static)
        text_widget.update(self._render_text())
    
    def remove(self):
        if self._animate_task:
            self._animate_task.cancel()
        super().remove()
```

---

### 2.4 FileAttachment (@file mention)

Render file mention sebagai attachment card dengan info file, preview, dan action.

```python
# src/mazyr/interfaces/chat_tui/widgets/file_attachment.py
from textual.widgets import Static, Button
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from pathlib import Path

class FileAttachment(Horizontal):
    CSS = """
    FileAttachment {
        height: auto;
        margin: 1 0;
        padding: 1;
        background: $surface-darken-1;
        border: solid $warning;
        width: auto;
        max-width: 80%;
    }
    .file-icon {
        width: 3;
        content-align: center middle;
    }
    .file-info {
        width: 1fr;
    }
    .file-name {
        text-style: bold;
        color: $warning;
    }
    .file-meta {
        color: $text-muted;
        text-style: dim;
    }
    Button {
        width: auto;
        height: 1;
    }
    """

    filepath = reactive("")
    filesize = reactive(0)
    preview = reactive("")

    def __init__(self, filepath: str, **kwargs):
        super().__init__(**kwargs)
        self.filepath = filepath
        path = Path(filepath)
        self.filesize = path.stat().st_size if path.exists() else 0
        self._load_preview()

    def _load_preview(self):
        """Load first 500 chars untuk preview."""
        try:
            with open(self.filepath, "r", encoding="utf-8", errors="ignore") as f:
                self.preview = f.read(500)
        except:
            self.preview = "[Binary file or unreadable]"
    
    def compose(self):
        icon = "📄" if self.filepath.endswith(".md") else "🐍" if self.filepath.endswith(".py") else "📁"
        
        yield Static(icon, classes="file-icon")
        
        with Vertical(classes="file-info"):
            yield Static(self.filepath, classes="file-name")
            size_str = f"{self.filesize / 1024:.1f} KB" if self.filesize < 1024*1024 else f"{self.filesize / (1024*1024):.1f} MB"
            yield Static(f"{size_str}  |  {self.filepath.split(")[-1].split(",")[-1]}" , classes="file-meta")
            if self.preview:
                preview_text = self.preview[:100].replace("\n", " ") + "..." if len(self.preview) > 100 else self.preview
                yield Static(preview_text, classes="file-preview")
        
        with Vertical():
            yield Button("View", id="btn-view", variant="primary")
            yield Button("Remove", id="btn-remove", variant="error")
    
    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-view":
            # Emit event untuk buka file preview screen
            self.post_message(self.FileViewRequest(self.filepath))
        elif event.button.id == "btn-remove":
            self.post_message(self.FileRemoveRequest(self.filepath))
    
    class FileViewRequest(Message):
        def __init__(self, filepath: str):
            self.filepath = filepath
            super().__init__()
    
    class FileRemoveRequest(Message):
        def __init__(self, filepath: str):
            self.filepath = filepath
            super().__init__()
```

---

### 2.5 ImageViewer

Display image di terminal menggunakan ASCII art atau terminal image protocol (kitty/iTerm2).

```python
# src/mazyr/interfaces/chat_tui/widgets/image_viewer.py
from textual.widgets import Static
from textual.containers import Vertical
from textual.reactive import reactive
from PIL import Image
import io
import base64

class ImageViewer(Vertical):
    CSS = """
    ImageViewer {
        height: auto;
        margin: 1 0;
        padding: 1;
        background: $surface-darken-1;
        border: solid $primary;
        width: auto;
        max-width: 80%;
    }
    .image-ascii {
        text-style: none;
    }
    .image-meta {
        color: $text-muted;
        text-style: dim;
        height: 1;
    }
    """

    image_data = reactive(b"")
    filename = reactive("")
    width = reactive(60)  # ASCII width

    def __init__(self, image_data: bytes, filename: str = "image.png", **kwargs):
        super().__init__(**kwargs)
        self.image_data = image_data
        self.filename = filename

    def compose(self):
        # Try terminal image protocol first (kitty/iTerm2)
        if self._supports_terminal_image():
            yield Static(self._terminal_image_protocol(), classes="image-terminal")
        else:
            # Fallback to ASCII art
            yield Static(self._to_ascii(), classes="image-ascii")
        
        yield Static(f"📷 {self.filename}", classes="image-meta")
    
    def _supports_terminal_image(self) -> bool:
        """Check TERM/TERM_PROGRAM untuk kitty atau iTerm2."""
        import os
        term = os.environ.get("TERM", "")
        term_program = os.environ.get("TERM_PROGRAM", "")
        return "kitty" in term or "iTerm" in term_program
    
    def _terminal_image_protocol(self) -> str:
        """Kitty terminal image protocol."""
        encoded = base64.b64encode(self.image_data).decode()
        return f"\033_Ga=T,f=100,m=1;{encoded[:4096]}\033\\"
    
    def _to_ascii(self) -> str:
        """Convert image to ASCII art."""
        try:
            img = Image.open(io.BytesIO(self.image_data))
            img = img.convert("L")  # Grayscale
            
            # Resize
            w, h = img.size
            aspect = h / w
            new_w = self.width
            new_h = int(new_w * aspect * 0.5)  # 0.5 karena char lebih tinggi dari lebar
            img = img.resize((new_w, new_h))
            
            # ASCII chars dari gelap ke terang
            chars = "@%#*+=-:. "
            pixels = img.getdata()
            
            result = []
            for i in range(0, len(pixels), new_w):
                row = pixels[i:i+new_w]
                ascii_row = "".join(chars[min(p // 25, len(chars)-1)] for p in row)
                result.append(ascii_row)
            
            return "\n".join(result)
        except Exception as e:
            return f"[Image: {self.filename} | Error: {e}]"
```

---

### 2.6 DiffView (Before/After)

Render code diff dengan line highlighting: green untuk added, red untuk removed, yellow untuk modified.

```python
# src/mazyr/interfaces/chat_tui/widgets/diff_view.py
from textual.widgets import Static
from textual.containers import Vertical
from textual.reactive import reactive
import difflib

class DiffView(Vertical):
    CSS = """
    DiffView {
        height: auto;
        margin: 1 0;
        padding: 1;
        background: $surface-darken-1;
        border: solid $warning;
        width: 100%;
    }
    .diff-header {
        text-style: bold;
        color: $warning;
        height: 1;
        margin-bottom: 1;
    }
    .diff-line {
        height: 1;
        padding: 0 1;
    }
    .diff-added {
        background: $success-darken-2;
        color: $text;
    }
    .diff-removed {
        background: $error-darken-2;
        color: $text;
    }
    .diff-unchanged {
        color: $text-muted;
    }
    """

    before = reactive("")
    after = reactive("")
    filename = reactive("")

    def __init__(self, before: str, after: str, filename: str = "", **kwargs):
        super().__init__(**kwargs)
        self.before = before
        self.after = after
        self.filename = filename

    def compose(self):
        header = "📝 Diff"
        if self.filename:
            header += f"  |  {self.filename}"
        yield Static(header, classes="diff-header")
        
        # Generate unified diff
        before_lines = self.before.splitlines(keepends=True)
        after_lines = self.after.splitlines(keepends=True)
        diff = list(difflib.unified_diff(before_lines, after_lines, lineterm=""))
        
        for line in diff[2:]:  # Skip header lines
            line_class = "diff-unchanged"
            prefix = "  "
            
            if line.startswith("+"):
                line_class = "diff-added"
                prefix = "+ "
            elif line.startswith("-"):
                line_class = "diff-removed"
                prefix = "- "
            elif line.startswith("@"):
                line_class = "diff-unchanged"
                prefix = "  "
            
            content = line[1:] if line.startswith(("+", "-")) else line
            yield Static(f"{prefix}{content}", classes=f"diff-line {line_class}")
```

---

### 2.7 InputArea (Multi-line + History + Mention)

Input dengan support multi-line (Ctrl+Enter), history navigation (Up/Down), dan @mention autocomplete.

```python
# src/mazyr/interfaces/chat_tui/widgets/input_area.py
from textual.widgets import TextArea, Static
from textual.containers import Vertical
from textual.reactive import reactive

class ChatInputArea(Vertical):
    CSS = """
    ChatInputArea {
        height: auto;
        max-height: 10;
        background: $surface;
        padding: 0 1;
    }
    TextArea {
        height: auto;
        min-height: 1;
        max-height: 8;
        border: solid $primary;
        background: $surface-darken-1;
    }
    .input-hint {
        color: $text-muted;
        text-style: dim;
        height: 1;
        text-align: right;
    }
    """

    history = reactive([])
    history_index = reactive(-1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history = []
        self.history_index = -1
        self._draft = ""

    def compose(self):
        yield TextArea(id="chat-input", show_line_numbers=False)
        yield Static("Enter: send | Ctrl+Enter: newline | Up/Down: history", classes="input-hint")
    
    def on_key(self, event):
        input_widget = self.query_one("#chat-input", TextArea)
        
        if event.key == "enter" and not event.ctrl:
            event.prevent_default()
            self._send_message()
        elif event.key == "up":
            event.prevent_default()
            self._history_prev()
        elif event.key == "down":
            event.prevent_default()
            self._history_next()
    
    def _send_message(self):
        input_widget = self.query_one("#chat-input", TextArea)
        text = input_widget.text.strip()
        if not text:
            return
        
        mentions = self._parse_mentions(text)
        self.history.append(text)
        self.history_index = len(self.history)
        self._draft = ""
        input_widget.text = ""
        self.post_message(self.MessageSubmitted(text, mentions))
    
    def _parse_mentions(self, text: str) -> list[str]:
        import re
        mentions = re.findall(r"@([\w./-]+)", text)
        return mentions
    
    def _history_prev(self):
        if self.history_index == len(self.history):
            input_widget = self.query_one("#chat-input", TextArea)
            self._draft = input_widget.text
        if self.history_index > 0:
            self.history_index -= 1
            input_widget = self.query_one("#chat-input", TextArea)
            input_widget.text = self.history[self.history_index]
    
    def _history_next(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            input_widget = self.query_one("#chat-input", TextArea)
            input_widget.text = self.history[self.history_index]
        elif self.history_index == len(self.history) - 1:
            self.history_index = len(self.history)
            input_widget = self.query_one("#chat-input", TextArea)
            input_widget.text = self._draft
    
    class MessageSubmitted(Message):
        def __init__(self, text: str, mentions: list[str]):
            self.text = text
            self.mentions = mentions
            super().__init__()
```

---

## 3. Main App Integration

### 3.1 MazyrChatApp

Main app yang wire semua widgets, handle daemon communication, dan manage reactive state.

```python
# src/mazyr/interfaces/chat_tui/app.py

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Header, Footer, Static, TextArea
from textual.reactive import reactive
from textual.binding import Binding
import asyncio
from datetime import datetime

from mazyr.infrastructure.relay_client import DaemonClient
from mazyr.interfaces.chat_tui.widgets.chat_message import ChatMessage
from mazyr.interfaces.chat_tui.widgets.code_block import CodeBlock
from mazyr.interfaces.chat_tui.widgets.typing_indicator import TypingIndicator
from mazyr.interfaces.chat_tui.widgets.file_attachment import FileAttachment
from mazyr.interfaces.chat_tui.widgets.image_viewer import ImageViewer
from mazyr.interfaces.chat_tui.widgets.diff_view import DiffView
from mazyr.interfaces.chat_tui.widgets.input_area import ChatInputArea
from mazyr.interfaces.chat_tui.widgets.status_bar import StatusBar


class MazyrChatApp(App):
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear_chat", "Clear", show=True),
        Binding("ctrl+s", "toggle_skill_mode", "Skill Mode", show=True),
        Binding("ctrl+m", "toggle_memory", "Memory", show=True),
        Binding("ctrl+d", "toggle_diff", "Diff View", show=True),
        Binding("tab", "focus_next", "Next"),
    ]

    # Reactive state
    qalb_state = reactive("Salim")
    nafs_state = reactive("Lawwamah")
    memory_count = reactive({"episodic": 0, "semantic": 0, "graph": 0})
    is_generating = reactive(False)
    current_mode = reactive("chat")
    active_skill = reactive(None)
    attached_files = reactive([])

    def __init__(self, daemon_url: str = "ws://localhost:8000/ws"):
        super().__init__()
        self.daemon = DaemonClient(daemon_url)
        self.session_id = "tui-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        self._typing_indicator = None
        self._current_assistant_msg = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main-container"):
            with Vertical(id="chat-thread", scroll_y=True):
                yield Static("Welcome to Mazyr Chat. Type /help for commands.", classes="system-message")
            yield StatusBar(id="status-bar")
            yield ChatInputArea(id="input-area")
        yield Footer()

    async def on_mount(self):
        self.set_title(f"Mazyr Chat - {self.session_id}")
        asyncio.create_task(self._poll_daemon())
        self.query_one("#chat-input", TextArea).focus()

    async def _poll_daemon(self):
        while True:
            try:
                status = await self.daemon.get_status()
                self.qalb_state = status.get("filter", "unknown")
                self.nafs_state = status.get("patterns", "unknown")
                self.memory_count = status.get("memory", {})
                if status.get("active_skill") != self.active_skill:
                    self.active_skill = status.get("active_skill")
            except Exception as e:
                self.qalb_state = "Disconnected"
            await asyncio.sleep(5)

    def on_chat_input_area_message_submitted(self, event: ChatInputArea.MessageSubmitted):
        # 1. Display user message dengan attachments
        attachments = []
        for mention in event.mentions:
            filepath = mention if mention.startswith("/") else f"./{mention}"
            if filepath.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                try:
                    with open(filepath, "rb") as f:
                        attachments.append(ImageViewer(f.read(), filepath))
                except:
                    attachments.append(FileAttachment(filepath))
            else:
                attachments.append(FileAttachment(filepath))
        self._add_user_message(event.text, attachments)
        
        # 2. Send ke daemon
        self.is_generating = True
        self._show_typing_indicator()
        asyncio.create_task(self._stream_response(event.text, event.mentions))

    async def _stream_response(self, message: str, mentions: list[str]):
        try:
            msg_widget = self._add_assistant_message("")
            self._current_assistant_msg = msg_widget
            full_response = ""
            async for chunk in self.daemon.chat_stream(message, self.session_id, mentions):
                if chunk["type"] == "token":
                    full_response += chunk["content"]
                    msg_widget.content = full_response
                    
                elif chunk["type"] == "tool_call":
                    tool_name = chunk["tool"]
                    self.notify(f"Tool: {tool_name}", severity="information")
                    
                elif chunk["type"] == "skill_step":
                    if self._typing_indicator:
                        step_name = chunk["name"]
                        current = chunk["current"]
                        total = chunk["total"]
                        self._typing_indicator.step_info = f"Step {current}/{total}: {step_name}"
                        self._typing_indicator.progress = current / total
                    
                elif chunk["type"] == "diff":
                    diff_widget = DiffView(
                        before=chunk["before"],
                        after=chunk["after"],
                        filename=chunk.get("filename", "")
                    )
                    self._add_widget_to_chat(diff_widget)
                    
                elif chunk["type"] == "code":
                    code_widget = CodeBlock(
                        code=chunk["content"],
                        language=chunk.get("language", "text"),
                        filename=chunk.get("filename", "")
                    )
                    self._add_widget_to_chat(code_widget)
                    
                elif chunk["type"] == "image":
                    img_widget = ImageViewer(
                        image_data=chunk["data"],
                        filename=chunk.get("filename", "image.png")
                    )
                    self._add_widget_to_chat(img_widget)
                    
                elif chunk["type"] == "done":
                    break
                    
        except Exception as e:
            self._add_system_message(f"Error: {e}", "error")
        finally:
            self.is_generating = False
            self._hide_typing_indicator()
            self._current_assistant_msg = None

    def _add_user_message(self, content: str, attachments: list = None):
        thread = self.query_one("#chat-thread", Vertical)
        msg = ChatMessage(content, role="user", attachments=attachments or [])
        thread.mount(msg)
        thread.scroll_end(animate=False)

    def _add_assistant_message(self, content: str) -> ChatMessage:
        thread = self.query_one("#chat-thread", Vertical)
        msg = ChatMessage(content, role="assistant")
        thread.mount(msg)
        thread.scroll_end(animate=False)
        return msg

    def _add_widget_to_chat(self, widget):
        thread = self.query_one("#chat-thread", Vertical)
        thread.mount(widget)
        thread.scroll_end(animate=False)

    def _add_system_message(self, content: str, severity: str = "info"):
        thread = self.query_one("#chat-thread", Vertical)
        msg = Static(content, classes=f"system-message {severity}")
        thread.mount(msg)
        thread.scroll_end(animate=False)

    def _show_typing_indicator(self):
        thread = self.query_one("#chat-thread", Vertical)
        self._typing_indicator = TypingIndicator()
        thread.mount(self._typing_indicator)
        thread.scroll_end(animate=False)

    def _hide_typing_indicator(self):
        if self._typing_indicator:
            self._typing_indicator.remove()
            self._typing_indicator = None

    def action_clear_chat(self):
        thread = self.query_one("#chat-thread", Vertical)
        thread.remove_children()
        self._add_system_message("Chat cleared.")

    def action_toggle_skill_mode(self):
        if self.current_mode == "chat":
            self.current_mode = "skill"
            self._add_system_message("Mode: SKILL --- Type skill name to execute")
        else:
            self.current_mode = "chat"
            self._add_system_message("Mode: CHAT")

    def watch_qalb_state(self, state: str):
        status = self.query_one("#status-bar", StatusBar)
        status.qalb_state = state

    def watch_nafs_state(self, state: str):
        status = self.query_one("#status-bar", StatusBar)
        status.nafs_state = state

    def watch_memory_count(self, counts: dict):
        status = self.query_one("#status-bar", StatusBar)
        status.memory_count = counts.get("semantic", 0)

    def watch_is_generating(self, generating: bool):
        input_area = self.query_one("#input-area", ChatInputArea)
        input_widget = input_area.query_one("#chat-input", TextArea)
        input_widget.disabled = generating
        if not generating:
            input_widget.focus()


if __name__ == "__main__":
    app = MazyrChatApp()
    app.run()
```

---

### 3.2 StatusBar

Real-time status bar dengan Qalb state, Nafs state, memory count, dan mode indicator.

```python
# src/mazyr/interfaces/chat_tui/widgets/status_bar.py
from textual.widgets import Static
from textual.containers import Horizontal
from textual.reactive import reactive

class StatusBar(Horizontal):
    CSS = """
    StatusBar {
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 2;
        border: solid $surface-lighten-1;
    }
    .status-item {
        width: auto;
        margin-right: 2;
    }
    .qalb-salim { color: $success; }
    .qalb-mariidh { color: $warning; }
    .qalb-aghlaf { color: $error; text-style: bold; }
    .nafs-lawwamah { color: $warning; }
    .nafs-mutmainnah { color: $success; }
    .mode-skill { color: $primary; text-style: bold; }
    """

    qalb_state = reactive("Salim")
    nafs_state = reactive("Lawwamah")
    memory_count = reactive(0)
    current_mode = reactive("chat")
    active_skill = reactive(None)

    def compose(self):
        yield Static("Mazyr", classes="status-item")
        yield Static(id="qalb-indicator", classes="status-item")
        yield Static(id="nafs-indicator", classes="status-item")
        yield Static(id="memory-indicator", classes="status-item")
        yield Static(id="mode-indicator", classes="status-item")
        yield Static(id="skill-indicator", classes="status-item")
    
    def watch_qalb_state(self, state: str):
        indicator = self.query_one("#qalb-indicator", Static)
        indicator.update(f"Qalb: {state}")
        indicator.classes = f"status-item qalb-{state.lower()}"
    
    def watch_nafs_state(self, state: str):
        indicator = self.query_one("#nafs-indicator", Static)
        indicator.update(f"Nafs: {state}")
        indicator.classes = f"status-item nafs-{state.lower()}"
    
    def watch_memory_count(self, count: int):
        indicator = self.query_one("#memory-indicator", Static)
        indicator.update(f"Mem: {count}")
    
    def watch_current_mode(self, mode: str):
        indicator = self.query_one("#mode-indicator", Static)
        indicator.update(f"Mode: {mode.upper()}")
        if mode == "skill":
            indicator.classes = "status-item mode-skill"
    
    def watch_active_skill(self, skill: dict):
        indicator = self.query_one("#skill-indicator", Static)
        if skill:
            indicator.update(f"Skill: {skill.get("name", "-")}")
        else:
            indicator.update("")
```

---

## 4. Styling (TCSS)

```css
/* src/mazyr/interfaces/chat_tui/styles.tcss */

Screen {
    align: center middle;
    background: $surface-darken-1;
}

#main-container {
    height: 1fr;
    border: solid $primary;
}

#chat-thread {
    height: 1fr;
    overflow-y: auto;
    padding: 1;
}

.system-message {
    color: $text-muted;
    text-align: center;
    text-style: italic;
    margin: 1 0;
}

.system-message.error {
    color: $error;
    text-style: bold;
}

.system-message.info {
    color: $primary;
}

Header {
    background: $primary;
    color: $text;
}

Footer {
    background: $surface;
    color: $text-muted;
}

/* Scrollbar styling */
Scrollbar {
    background: $surface-darken-1;
    color: $primary;
}

/* Notification toast */
Toast {
    background: $surface;
    border: solid $primary;
    color: $text;
}
```

---

## 5. Commands & Shortcuts

### 5.1 Keyboard Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `Enter` | Send message | Input focused |
| `Ctrl+Enter` | Newline in input | Input focused |
| `Up` | History previous | Input focused |
| `Down` | History next | Input focused |
| `Tab` | Focus next panel | Global |
| `Ctrl+C` | Quit app | Global |
| `Ctrl+L` | Clear chat | Global |
| `Ctrl+S` | Toggle skill mode | Global |
| `Ctrl+M` | Toggle memory panel | Global |
| `Ctrl+D` | Toggle diff view | Global |
| `@` | Trigger mention autocomplete | Input focused |

### 5.2 Slash Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/help` | Show all commands | `/help` |
| `/clear` | Clear chat thread | `/clear` |
| `/skill <name>` | Execute skill | `/skill voidlight-vision` |
| `/memory` | Open memory browser | `/memory` |
| `/status` | Show daemon status | `/status` |
| `/mode <mode>` | Switch mode | `/mode skill` |
| `/quit` | Exit chat | `/quit` |

### 5.3 File Mention Syntax

| Syntax | Description | Example |
|--------|-------------|---------|
| `@file.txt` | Attach file | `@README.md` |
| `@path/to/file.py` | Attach with path | `@src/main.py` |
| `@image.png` | Attach image (renders inline) | `@screenshot.png` |

---

## 6. Daemon Stream Protocol

TUI expects daemon WebSocket stream dengan format chunk:

```json
// Token chunk
{"type": "token", "content": "Hello"}

// Tool call notification
{"type": "tool_call", "tool": "search_memory", "status": "executing"}

// Skill step progress
{"type": "skill_step", "name": "Generate Prompt", "current": 2, "total": 4}

// Code block
{"type": "code", "content": "def hello():...", "language": "python", "filename": "hello.py"}

// Diff view
{"type": "diff", "before": "old code", "after": "new code", "filename": "file.py"}

// Image
{"type": "image", "data": "<base64>", "filename": "chart.png"}

// Completion
{"type": "done"}

// Error
{"type": "error", "message": "Something went wrong"}
```

---

## 7. Implementation Roadmap

### Phase 1: Foundation (Day 1)

**Goal:** Basic chat app dengan streaming + markdown.

- **File:** `app.py` --- Main app scaffold + daemon polling
- **File:** `widgets/chat_message.py` --- Message bubble dengan Markdown
- **File:** `widgets/typing_indicator.py` --- Animated thinking indicator
- **File:** `widgets/input_area.py` --- Input dengan history
- **File:** `styles.tcss` --- Basic styling

**Success Criteria:**
- [ ] Chat dengan Aria via TUI
- [ ] Streaming response (token-by-token)
- [ ] Markdown rendering
- [ ] History navigation (Up/Down)

### Phase 2: Rich Content (Day 2)

**Goal:** Code blocks, file mentions, images, diffs.

- **File:** `widgets/code_block.py` --- Syntax highlight + Copy/Run buttons
- **File:** `widgets/file_attachment.py` --- @file mention renderer
- **File:** `widgets/image_viewer.py` --- ASCII/terminal image
- **File:** `widgets/diff_view.py` --- Before/after diff

**Success Criteria:**
- [ ] `@file.txt` renders attachment card
- [ ] Code blocks dengan syntax highlight
- [ ] Diff view untuk code changes
- [ ] Image viewer (ASCII fallback)

### Phase 3: Status & Control (Day 3)

**Goal:** Real-time status bar + command palette.

- **File:** `widgets/status_bar.py` --- Qalb/Nafs/Memory/Mode indicators
- **Integration:** Slash commands (`/help`, `/skill`, `/clear`)
- **Integration:** Skill mode toggle (`Ctrl+S`)
- **Integration:** Memory browser panel (`Ctrl+M`)

**Success Criteria:**
- [ ] Status bar shows Qalb state (color-coded)
- [ ] `/skill voidlight-vision` executes skill
- [ ] `/memory` opens memory browser side panel
- [ ] Mode toggle between chat/skill

### Phase 4: Polish (Day 4)

**Goal:** Polish, edge cases, performance.

- **Feature:** Mention autocomplete (`@` triggers file list)
- **Feature:** Multi-line input (Ctrl+Enter newline)
- **Feature:** Notification toasts (tool calls, errors)
- **Feature:** Session persistence (restore chat on reconnect)
- **Test:** Large message handling (>1000 tokens)
- **Test:** Memory leak check (long-running session)

**Success Criteria:**
- [ ] `@` shows autocomplete popup
- [ ] Multi-line input works
- [ ] No memory leak after 1 hour
- [ ] Ready for daily use

---

## 8. Next Steps

1. **Start Phase 1:** Implement `app.py` + `chat_message.py` + `typing_indicator.py`
2. **Test:** Run `python -m mazyr.interfaces.chat_tui.app`
3. **Iterate:** Phase 2-4 sesuai roadmap
4. **Integrate:** Add `mazyr chat` command ke CLI

**Dependencies:** `textual` (sudah include `rich`)

**Build time:** 3-4 hari dengan Kimi Code

---

*MTS-11 v1.0 | Mazyr Technical Specification | Chat TUI Interface*
