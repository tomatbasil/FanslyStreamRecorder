import os
import subprocess
import math
import json
import re
import traceback
from pathlib import Path


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

        process_result = subprocess.run(
            format_cmd, capture_output=True, text=True, check=False
        )

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
            format_info = subprocess.run(
                ["ffmpeg", "-i", input_path], capture_output=True, text=True
            )
            duration_match = re.search(
                r"Duration: (\d+:\d+:\d+\.\d+)", format_info.stderr
            )
            if duration_match:
                return f"Duration: {duration_match.group(1)}"

    except Exception as probe_err:
        print(f"Error running ffprobe: {probe_err}")
        print(f"Error traceback: {traceback.format_exc()}")

    return "Duration: unknown"


def split_video_by_size(video_path_input: str, max_size_gb: float = 1.9):
    """
    Split a video file into chunks of specified maximum size.

    Args:
        video_path (str): Path to the input video file
        max_size_gb (float): Maximum size of each chunk in gigabytes (default: 1.9)
    """
    video_path = Path(video_path_input)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Calculate file size in GB
    file_size_gb = os.path.getsize(video_path) / (1024**3)
    num_segments = math.ceil(file_size_gb / max_size_gb)
    output_dir = video_path.parent / f"{video_path.stem}_chunks"

    if output_dir.exists():
        expected_files = [
            output_dir / f"{video_path.stem}_part{i + 1}{video_path.suffix}"
            for i in range(num_segments)
        ]
        if all(file.exists() for file in expected_files):
            return expected_files

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

    segment_duration = duration / num_segments
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
            "copy",
            str(output_path),
        ]

        subprocess.run(cmd, check=True)

    return list_of_created_files
