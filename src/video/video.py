import asyncio
import os
import subprocess
import math
import json
import re
import traceback
from enum import Enum
from pathlib import Path
from typing import Dict, Any
from src.config import CONFIG
from src.discord_bot import discord_bot
from src.ui import UI


class CompressionStatus(Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def get_video_duration(input_path: str) -> str:
    """Get the duration of a video file using ffprobe"""
    try:
        format_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-print_format",
            "json",
            input_path,
        ]

        process_result = subprocess.run(format_cmd, capture_output=True, text=True, check=False)

        if process_result.returncode != 0:
            print(f"FFprobe error: {process_result.stderr}")

        try:
            info = json.loads(process_result.stdout)
            if "format" in info:
                return f"Duration: {info['format'].get('duration', '00:00:00.00')}"
        except json.JSONDecodeError as json_err:
            print(f"Error parsing JSON from ffprobe: {json_err}")
            # Fallback if JSON parsing fails
            print("Using fallback method to get duration")
            format_info = subprocess.run(["ffmpeg", "-i", input_path], capture_output=True, text=True)
            duration_match = re.search(r"Duration: (\d+:\d+:\d+\.\d+)", format_info.stderr)
            if duration_match:
                return f"Duration: {duration_match.group(1)}"

    except Exception as probe_err:
        print(f"Error running ffprobe: {probe_err}")
        print(f"Error traceback: {traceback.format_exc()}")

    return "Duration: unknown"


async def compress_video(input_path: str, username: str) -> str:
    """
    Compress a video directly without queuing and return the compressed path
    or original path if compression fails

    Args:
        input_path: Path to the video file to compress
    """
    compressed_path = input_path.rsplit(".", 1)[0] + "_compressed.mp4"
    UI.update_user(username, "Compressing video...", False)

    # Check if compression already completed
    if os.path.exists(compressed_path):
        return compressed_path

    # Check if the input file exists before proceeding
    if not os.path.exists(input_path):
        print(f"Input file does not exist: {input_path}")
        return input_path

    # Make sure output directory exists
    os.makedirs(os.path.dirname(compressed_path), exist_ok=True)

    # Get original file size for comparison later
    original_size = os.path.getsize(input_path)

    try:
        # Create ffmpeg command
        ffmpeg_cmd = [
            "ffmpeg",
            "-i",
            input_path,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "26",  # Constant Rate Factor (lower = better quality)
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            compressed_path,
        ]

        # Run compression process
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await process.communicate()

        if process.returncode == 0 and os.path.exists(compressed_path):
            # Calculate size reduction
            compressed_size = os.path.getsize(compressed_path)
            size_reduction = round((1 - (compressed_size / original_size)) * 100, 2)

            await discord_bot.send_message(
                f"🟡 Video {os.path.basename(input_path)} compressed successfully. Size reduced by {size_reduction}%."
            )

            if CONFIG.delete_original:
                try:
                    os.remove(input_path)
                except Exception as e:
                    print(f"Error removing original file {input_path}: {str(e)}")

            return compressed_path
        else:
            print(f"Compression failed for {input_path}: FFmpeg exited with code {process.returncode}")
            print(f"Error output: {process.stderr}")
            return input_path

    except Exception as e:
        print(f"Error during compression of {input_path}: {str(e)}")
        print(f"Error traceback: {traceback.format_exc()}")
        return input_path


def split_video_by_size(video_path: str, max_size_gb: float = 1.9):
    """
    Split a video file into chunks of specified maximum size.

    Args:
        video_path (str): Path to the input video file
        max_size_gb (float): Maximum size of each chunk in gigabytes (default: 1.9)
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Calculate file size in GB
    file_size_gb = os.path.getsize(video_path) / (1024**3)

    # Calculate number of segments needed
    num_segments = math.ceil(file_size_gb / max_size_gb)

    # Create output directory path
    output_dir = video_path.parent / f"{video_path.stem}_chunks"

    # Check if the exact number of chunks already exists
    if output_dir.exists():
        expected_files = [output_dir / f"{video_path.stem}_part{i + 1}{video_path.suffix}" for i in range(num_segments)]
        if all(file.exists() for file in expected_files):
            return expected_files

    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)

    list_of_created_files = []

    # Get video duration using ffprobe
    duration_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    duration = float(subprocess.check_output(duration_cmd).decode().strip())

    # Calculate segment duration
    segment_duration = duration / num_segments

    # Split video using ffmpeg
    for i in range(num_segments):
        start_time = i * segment_duration
        output_path = output_dir / f"{video_path.stem}_part{i + 1}{video_path.suffix}"
        list_of_created_files.append(output_path)

        cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-ss",
            str(start_time),
            "-t",
            str(segment_duration),
            "-c",
            "copy",  # Copy codec (no re-encoding)
            str(output_path),
        ]

        subprocess.run(cmd, check=True)

    return list_of_created_files


def get_compression_queue_status() -> Dict[str, Any]:
    """
    Stub function for UI compatibility.
    Returns empty status since queue is removed.
    """
    return {
        "queue_size": 0,
        "active_count": 0,
        "queued_count": 0,
        "completed_count": 0,
        "failed_count": 0,
        "processing_jobs": [],
        "queued_jobs": [],
    }
