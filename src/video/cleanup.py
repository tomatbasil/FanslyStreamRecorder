import os
import shutil
from pathlib import Path
from src.discord_bot import discord_bot


async def check_disk_space_and_cleanup(output_dir, min_free_gb=20.0):
    """
    Check available disk space and remove oldest recordings if below threshold

    Args:
        output_dir (str): Directory where recordings are stored
        min_free_gb: Minimum free space in GB to maintain on disk
    """
    try:
        if not os.path.exists(output_dir):
            return  # Nothing to clean if directory doesn't exist

        # Get the drive/partition where the recordings are stored
        if os.name == "nt":  # Windows
            drive = os.path.splitdrive(output_dir)[0] + "\\"
        else:  # Linux/MacOS
            drive = output_dir
            while not os.path.ismount(drive):
                parent = os.path.dirname(drive)
                if parent == drive:  # Reached root
                    drive = "/"
                    break
                drive = parent

        # Get disk usage statistics
        disk_usage = shutil.disk_usage(drive)
        free_gb = disk_usage.free / (1024 * 1024 * 1024)

        # If free space is below threshold, start cleaning up
        if free_gb < min_free_gb:
            # Get all video files in the output directory
            video_files = []
            for ext in [".mp4", ".mkv", ".avi", ".mov"]:
                video_files.extend(list(Path(output_dir).glob(f"*{ext}")))

            if not video_files:
                print(f"No videos found in {output_dir} to clean up")
                return

            # Sort by creation time, oldest first
            video_files.sort(key=lambda x: os.path.getctime(x))

            # Calculate how many files we need to remove
            target_free_gb = min_free_gb
            to_free_gb = target_free_gb - free_gb

            bytes_freed = 0
            files_removed = 0

            # Remove oldest files until we free up enough space or run out of files
            for file_path in video_files:
                # Check file size and add to deletion list
                file_size = os.path.getsize(file_path)
                file_size_gb = file_size / (1024 * 1024 * 1024)

                # Remove the file and its thumbnail if exists
                try:
                    # Try to find and remove any associated thumbnail
                    thumbnail_path = str(file_path).rsplit(".", 1)[0] + ".jpg"
                    if os.path.exists(thumbnail_path):
                        os.remove(thumbnail_path)
                        print(f"Removed thumbnail: {thumbnail_path}")

                    # Remove the video file
                    os.remove(file_path)
                    bytes_freed += file_size
                    files_removed += 1
                    print(f"Removed video: {file_path} ({file_size_gb:.2f}GB)")

                    # Check if we've freed enough space
                    if bytes_freed / (1024 * 1024 * 1024) >= to_free_gb:
                        break

                except Exception as e:
                    print(f"Error removing file {file_path}: {str(e)}")

            # Log cleanup results
            gb_freed = bytes_freed / (1024 * 1024 * 1024)

            # Notify via Discord if enabled
            if discord_bot.enabled:
                await discord_bot.send_message(
                    f"♻️ **Auto-cleanup triggered**\n"
                    f"Low disk space: {free_gb:.2f}GB free\n"
                    f"Removed {files_removed} oldest video(s), freed {gb_freed:.2f}GB"
                )

    except Exception as e:
        print(f"Error during disk space check and cleanup: {str(e)}")
