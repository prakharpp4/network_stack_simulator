"""
logger.py — Structured logging system for the Network Stack Simulator.

Every layer writes its events here. The GUI subscribes via a callback
so it can display logs in the scrollable Log Viewer in real time.
"""

from datetime import datetime
from typing import Callable, Optional


class Logger:
    """
    Singleton-style logger that formats messages with timestamp,
    layer, source, destination, and action fields.

    Usage:
        Logger.log("TRANSPORT", "HostA:5001", "HostB:80", "TCP Segment Created")
    """

    _subscribers: list[Callable[[str], None]] = []
    _history: list[str] = []

    @classmethod
    def subscribe(cls, callback: Callable[[str], None]) -> None:
        """Register a GUI or console callback to receive log lines."""
        cls._subscribers.append(callback)

    @classmethod
    def log(
        cls,
        layer: str,
        source: str,
        destination: str,
        action: str,
        extra: Optional[str] = None,
    ) -> None:
        """
        Build a structured log line and broadcast it to all subscribers.

        Format:
            [HH:MM:SS] [LAYER] source -> destination | action
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        arrow = f"{source} -> {destination}" if destination else source
        line = f"[{timestamp}] [{layer:<10}] {arrow:<30} | {action}"
        if extra:
            line += f"\n{'':>50}  {extra}"

        cls._history.append(line)
        for cb in cls._subscribers:
            cb(line)

    @classmethod
    def separator(cls, title: str = "") -> None:
        """Print a visual separator (used between demo sections)."""
        bar = "─" * 60
        line = f"\n{bar}"
        if title:
            line += f"\n  {title}"
            line += f"\n{bar}"
        cls._history.append(line)
        for cb in cls._subscribers:
            cb(line)

    @classmethod
    def get_history(cls) -> list[str]:
        return list(cls._history)

    @classmethod
    def clear(cls) -> None:
        cls._history.clear()
