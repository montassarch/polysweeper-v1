"""Kill switch. File-based so a separate program (e.g. the Telegram bot) can flip it."""
from __future__ import annotations

from pathlib import Path
from typing import Optional


class KillSwitch:
    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) if path else None
        self._active = False
        self._reason = ""

    def is_active(self) -> bool:
        if self.path is not None and self.path.exists():
            return True
        return self._active

    def reason(self) -> str:
        if self.path is not None and self.path.exists():
            return self.path.read_text().strip() or "kill file present"
        return self._reason

    def activate(self, reason: str) -> None:
        self._active = True
        self._reason = reason
        if self.path is not None:
            self.path.write_text(reason)

    def clear(self) -> None:
        self._active = False
        self._reason = ""
        if self.path is not None and self.path.exists():
            self.path.unlink()
