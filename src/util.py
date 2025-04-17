from pathlib import Path


def get_base_path() -> Path:
    """Get the base path for the application (project root)"""
    return Path(__file__).parent.parent
