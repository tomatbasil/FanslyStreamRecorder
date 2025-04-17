from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.progress import Progress, BarColumn, TextColumn
from rich.style import Style
from rich.text import Text
from rich.console import Group
from datetime import datetime
import asyncio
from typing import Dict, List, Optional


class MonitorUI:
    def __init__(self):
        self.console = Console()
        self.user_states: Dict[str, dict] = {}
        self.live = None

    def add_user(self, username: str):
        """Add a new user to the monitoring UI"""
        self.user_states[username] = {
            "status": "Initializing...",
            "recording": False,
            "last_update": datetime.now(),
            "current_file": None,
        }
        if self.live:
            self.refresh()

    def update_user(
        self,
        username: str,
        status: str,
        recording: bool = None,
        current_file: str = None,
    ):
        """Update the status of a monitored user"""
        if username in self.user_states:
            self.user_states[username]["status"] = status
            self.user_states[username]["last_update"] = datetime.now()
            if recording is not None:
                self.user_states[username]["recording"] = recording
            if current_file is not None:
                self.user_states[username]["current_file"] = current_file
            self.refresh()

    def generate_streams_table(self) -> Table:
        """Generate the stream monitoring table"""
        table = Table(title="Fansly Stream Monitor")

        # Define columns
        table.add_column("Username", style="cyan")
        table.add_column("Status")
        table.add_column("Recording", justify="center")
        table.add_column("Current File")
        table.add_column("Last Update", justify="right")

        # Add user rows
        for username, state in self.user_states.items():
            recording_status = Text("🔴 LIVE", style="bold red") if state["recording"] else Text("⚫", style="dim")
            current_file = state["current_file"] or "-"
            last_update = state["last_update"].strftime("%H:%M:%S")

            table.add_row(username, state["status"], recording_status, current_file, last_update)

        return table

    def generate_display(self):
        """Generate the complete UI layout"""
        # Just return the streams table, no compression queue
        return self.generate_streams_table()

    def refresh(self):
        """Refresh the display"""
        if self.live:
            self.live.update(self.generate_display())

    async def start(self):
        """Start the live display"""
        self.live = Live(self.generate_display(), refresh_per_second=4)
        self.live.start()
        try:
            while True:
                await asyncio.sleep(0.25)
                self.refresh()
        except asyncio.CancelledError:
            self.live.stop()


UI = MonitorUI()
