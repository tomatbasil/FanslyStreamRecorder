import asyncio
import requests
import base64
from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.text import Text
from datetime import datetime, timedelta
from typing import Dict


class MonitorUI:
    def __init__(self):
        self.console = Console()
        self.user_states: Dict[str, dict] = {}
        self.live = None
        self.latest_version_cache = None
        self.latest_version_cache_time = None

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

    def get_version(self) -> tuple[str, str]:
        """Get the version of the application"""
        current_version = "unknown"
        try:
            with open(".ver", "r") as f:
                version_content = f.read().strip()
                current_version = version_content
        except (FileNotFoundError, IOError):
            print("Version file not found. Using 'unknown' as version.")

        # Check if we have a cached version and if it's still valid (less than 24 hours old)
        if (
            self.latest_version_cache
            and self.latest_version_cache_time
            and datetime.now() - self.latest_version_cache_time < timedelta(days=1)
        ):
            return current_version, self.latest_version_cache

        # If no cache or cache expired, fetch from GitHub
        latest_version = "unknown"
        try:
            response = requests.get("https://api.github.com/repos/tomatbasil/FanslyStreamRecorder/contents/.ver")
            if response.status_code == 200:
                version_content = response.json().get("content", "unknown")
                latest_version = base64.b64decode(version_content).decode("utf-8").strip()
                # Update cache
                self.latest_version_cache = latest_version
                self.latest_version_cache_time = datetime.now()
        except Exception:
            # If request fails, use cached version if available
            if self.latest_version_cache:
                latest_version = self.latest_version_cache
            return current_version, latest_version

        return current_version, latest_version

    def _compare_versions(self, current: str, latest: str) -> int:
        """
        Compare version numbers and return a status code:
        0: Same or up to date
        1: Close (minor version difference)
        2: Far behind (major version difference)
        """
        if current == "unknown" or latest == "unknown":
            return 1  # Default to yellow if can't compare

        try:
            # Parse versions like "0.1.0" into components
            current_parts = [int(x) for x in current.strip().split(".")]
            latest_parts = [int(x) for x in latest.strip().split(".")]

            # Pad with zeros if one version has fewer components
            while len(current_parts) < len(latest_parts):
                current_parts.append(0)
            while len(latest_parts) < len(current_parts):
                latest_parts.append(0)

            # If versions are the same, return green
            if current_parts == latest_parts:
                return 0

            # If major version is different, return red
            if current_parts[0] != latest_parts[0]:
                return 2

            # If only minor or patch versions are different, return yellow
            return 1
        except (ValueError, IndexError):
            return 1  # Default to yellow if parsing fails

    def _get_version_text(self, current: str, latest: str) -> Text:
        """Return richly formatted version text based on comparison"""
        status = self._compare_versions(current, latest)

        current_text = Text(current)
        latest_text = Text(latest)

        # Apply color to current version
        if status == 0:
            current_text.stylize("bold green")
        elif status == 1:
            current_text.stylize("bold yellow")
        else:
            current_text.stylize("bold red")

        # Apply color to latest version
        latest_text.stylize("bold green")

        return Text.assemble("Fansly Stream Monitor | Version: ", current_text, " | Latest: ", latest_text)

    def generate_streams_table(self) -> Table:
        """Generate the stream monitoring table"""
        current_version, latest_version = self.get_version()
        version_text = self._get_version_text(current_version, latest_version)

        table = Table(title=version_text)

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
