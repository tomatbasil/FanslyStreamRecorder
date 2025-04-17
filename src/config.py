import yaml
from pydantic import BaseModel, Field
from typing import List
from pathlib import Path
from src.util import get_base_path


class Config(BaseModel):
    output_directory: Path = Field(
        default=Path("recordings"),
        description="Directory where recordings will be saved",
    )
    users_to_monitor: List[str] = Field(default_factory=list, description="List of Fansly usernames to monitor")
    check_interval: int = Field(
        default=60,
        description="Interval in seconds to check for live streams",
    )

    # Video settings
    generate_thumbnail: bool = Field(
        default=True,
        description="Whether to generate a thumbnail for the recorded video",
    )
    compress_videos: bool = Field(
        default=True,
        description="Whether to compress videos after recording",
    )
    delete_original: bool = Field(
        default=True,
        description="Delete original video file after compression",
    )
    delete_split_video_after_upload: bool = Field(
        default=True,
        description="Delete split video file after upload",
    )
    upload_videos: bool = Field(
        default=False,
        description="Whether to upload videos after recording",
    )
    remove_old_recordings: bool = Field(
        default=True,
        description="Remove old recordings to free up space",
    )
    min_free_disk_space: float = Field(
        default=20.0,
        description="Minimum free disk space in GB to maintain before cleanup",
    )

    # Discord settings
    discord_enable: bool = Field(
        default=False,
        description="Enable Discord notifications",
    )
    discord_channel_id: str = Field(
        default="",
        description="Discord channel ID for notifications",
    )

    # Dev settings
    dev_mode: bool = Field(
        default=False,
        description="Enable developer mode for testing",
    )

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        data["output_directory"] = str(data["output_directory"])
        return data


def get_user_output_directory() -> Path:
    base_path = get_base_path()
    default_path = base_path / "recordings"

    while True:
        path_str = input(
            f"Enter the directory path where you want to save recordings (press Enter for default '{default_path}'): "
        ).strip()
        if not path_str:
            path = default_path
        else:
            path = Path(path_str)
            if not path.is_absolute():
                path = base_path / path

        try:
            # Create the directory if it doesn't exist
            path.mkdir(parents=True, exist_ok=True)
            return path
        except Exception as e:
            print(f"Error creating directory: {e}")
            print("Please try again with a valid path")


def get_users_to_monitor() -> List[str]:
    """Ask the user for Fansly usernames to monitor"""
    users = []
    print("\nEnter Fansly usernames to monitor (one per line, leave empty to finish):")
    while True:
        username = input("Username (or press Enter to finish): ").strip()
        if not username:
            break
        users.append(username)

    if not users:
        print("Warning: No users specified for monitoring")
    return users


def get_boolean_setting(prompt: str, default: bool) -> bool:
    """Ask the user for a boolean setting with a default value"""
    default_str = "Y/n" if default else "y/N"
    while True:
        response = input(f"{prompt} ({default_str}): ").strip().lower()
        if not response:
            return default
        elif response in ("y", "yes"):
            return True
        elif response in ("n", "no"):
            return False
        else:
            print("Please enter 'y' or 'n'")


def get_check_interval() -> int:
    """Ask the user for check interval in seconds"""
    default_interval = 60
    while True:
        try:
            interval_str = input(
                f"Enter interval in seconds to check for streams (press Enter for default {default_interval}s): "
            ).strip()
            if not interval_str:
                return default_interval

            interval = int(interval_str)
            if interval < 10:
                print("Interval must be at least 10 seconds")
                continue
            return interval
        except ValueError:
            print("Please enter a valid number")


def get_discord_settings() -> tuple[bool, str]:
    """Ask the user for Discord notification settings"""
    enable = get_boolean_setting("Enable Discord notifications?", False)
    channel_id = ""

    if enable:
        while True:
            channel_id = input("Enter Discord channel ID for notifications: ").strip()
            if channel_id:
                break
            print("Discord channel ID is required if notifications are enabled")

    return enable, channel_id


def get_cleanup_settings() -> tuple[bool, float]:
    """Ask the user for disk cleanup settings"""
    remove_old = get_boolean_setting("Remove old recordings to free up disk space?", True)
    min_free_space = 20.0

    if remove_old:
        while True:
            try:
                space_str = input(
                    f"Enter minimum free disk space to maintain in GB (press Enter for default 20GB): "
                ).strip()
                if not space_str:
                    break

                min_free_space = float(space_str)
                if min_free_space <= 0:
                    print("Minimum free space must be greater than 0 GB")
                    continue
                break
            except ValueError:
                print("Please enter a valid number")

    return remove_old, min_free_space


def get_all_settings() -> Config:
    """Ask for all configuration settings interactively"""
    print("\n===== Fansly Stream Recorder Configuration =====\n")

    # Get output directory
    output_dir = get_user_output_directory()

    # Get users to monitor
    users = get_users_to_monitor()

    # Get check interval
    check_interval = get_check_interval()

    # Get video settings
    print("\n----- Video Settings -----")
    generate_thumbnail = get_boolean_setting("Generate thumbnails for recorded videos?", True)
    compress_videos = get_boolean_setting("Compress videos after recording?", True)
    delete_original = (
        get_boolean_setting("Delete original video files after compression?", True) if compress_videos else False
    )

    upload_videos = get_boolean_setting("Upload videos after recording?", False)
    delete_split = get_boolean_setting("Delete split video files after upload?", True) if upload_videos else True

    # Get cleanup settings
    print("\n----- Disk Cleanup Settings -----")
    remove_old_recordings, min_free_disk_space = get_cleanup_settings()

    # Get Discord settings
    print("\n----- Discord Notifications -----")
    discord_enable, discord_channel_id = get_discord_settings()

    print("\nConfiguration complete!")

    # Create and return config
    return Config(
        output_directory=output_dir,
        users_to_monitor=users,
        check_interval=check_interval,
        generate_thumbnail=generate_thumbnail,
        compress_videos=compress_videos,
        delete_original=delete_original,
        delete_split_video_after_upload=delete_split,
        upload_videos=upload_videos,
        discord_enable=discord_enable,
        discord_channel_id=discord_channel_id,
        remove_old_recordings=remove_old_recordings,
        min_free_disk_space=min_free_disk_space,
    )


def load_config(
    config_path: Path = Path(__file__).parent.parent / "config.yaml",
) -> Config:
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        with open(config_path, "r") as f:
            config_dict = yaml.safe_load(f)
            return Config(**config_dict)

    # First-time setup: ask for all settings
    config = get_all_settings()

    with open(config_path, "w") as f:
        yaml.dump(config.model_dump(), f)
    return config


CONFIG = load_config()
