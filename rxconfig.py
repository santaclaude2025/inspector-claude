import reflex as rx
from pathlib import Path

# Configuration for Inspector Claude
claude_dir = Path.home() / ".claude"

config = rx.Config(
    app_name="inspector_claude",
)
