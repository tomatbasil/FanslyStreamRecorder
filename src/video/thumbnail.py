import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ProcessPoolExecutor


def get_frame_timestamp(cap, frame_idx):
    """Get timestamp for a specific frame in HH:MM:SS format."""
    fps = cap.get(cv2.CAP_PROP_FPS)
    seconds = frame_idx / fps
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def process_frame(frame, target_size, timestamp):
    """Process a single frame in parallel"""
    try:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame)
        pil_image.thumbnail(target_size, Image.Resampling.LANCZOS)
        return (pil_image, timestamp)
    except Exception as e:
        print(f"Error processing frame: {e}")
        return None


def seek_frame(cap, target_frame_idx, max_attempts=3):
    """Frame seeking with fallback strategies."""
    for attempt in range(max_attempts):
        # Try different seeking strategies
        if attempt == 0:
            # Try exact frame positioning
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame_idx)
        elif attempt == 1:
            # Try seeking by ratio
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            pos = target_frame_idx / total_frames
            cap.set(cv2.CAP_PROP_POS_AVI_RATIO, pos)
        else:
            # Try seeking to nearest keyframe
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, target_frame_idx - 30))
            for _ in range(min(30, target_frame_idx)):
                cap.read()

        # Read and validate frame
        ret, frame = cap.read()
        if ret and frame is not None and frame.size > 0:
            return True, frame

        # Reset position if attempt failed
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    return False, None


def extract_frames(video_path: str, num_frames=6, target_size=(640, 360)):
    """Extract evenly spaced frames from a video with improved reliability."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video: {video_path}")
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    # Adjust frame indices to avoid very start and end of video
    safe_margin = int(total_frames * 0.02)  # 2% margin
    frame_indices = np.linspace(safe_margin, total_frames - safe_margin - 1, num_frames, dtype=int)

    frames_with_timestamps = []
    frames_cache = {}
    batch_size = 2

    with ProcessPoolExecutor() as executor:
        for i in range(0, len(frame_indices), batch_size):
            batch_indices = frame_indices[i : i + batch_size]
            frames = []
            timestamps = []

            # Read batch of frames using reliable seeking
            for idx in batch_indices:
                if idx in frames_cache:
                    frames.append(frames_cache[idx])
                    timestamps.append(get_frame_timestamp(cap, idx))
                    continue

                success, frame = seek_frame(cap, idx)
                if success:
                    frames_cache[idx] = frame
                    frames.append(frame)
                    timestamps.append(get_frame_timestamp(cap, idx))
                else:
                    print(f"Warning: Could not read frame at index {idx}, trying next frame")
                    continue

            # Process batch in parallel
            if frames:  # Only process if we have valid frames
                futures = []
                for frame, timestamp in zip(frames, timestamps):
                    future = executor.submit(process_frame, frame, target_size, timestamp)
                    futures.append(future)

                # Collect results
                for future in futures:
                    result = future.result()
                    if result:
                        frames_with_timestamps.append(result)

    cap.release()

    if not frames_with_timestamps:
        print("Warning: Could not extract any valid frames from the video")

    return frames_with_timestamps


def create_thumbnail(frames_with_timestamps: list, cols=3, save_path="thumbnail.jpg", quality=85):
    """Combine frames into a single thumbnail image with timestamps."""
    if not frames_with_timestamps:
        print("No frames to process.")
        return

    rows = (len(frames_with_timestamps) + cols - 1) // cols
    frame_width, frame_height = frames_with_timestamps[0][0].size

    thumbnail = Image.new("RGB", (cols * frame_width, rows * frame_height))
    draw = ImageDraw.Draw(thumbnail)

    # Try to use Arial, fallback to default if not available
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()

    for idx, (frame, timestamp) in enumerate(frames_with_timestamps):
        row = idx // cols
        col = idx % cols
        x_offset = col * frame_width
        y_offset = row * frame_height
        thumbnail.paste(frame, (x_offset, y_offset))

        # Add timestamp
        text_width = draw.textlength(timestamp, font=font)
        text_x = x_offset + frame_width - text_width - 10
        text_y = y_offset + frame_height - 30

        # Draw text shadow
        draw.text((text_x + 1, text_y + 1), timestamp, font=font, fill="black")
        draw.text((text_x, text_y), timestamp, font=font, fill="white")

    thumbnail.save(save_path, quality=quality, optimize=True)


def auto_create_thumbnail(video_path, save_path="thumbnail.jpg"):
    """Automatically create thumbnail with optimal frame count based on video length."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video: {video_path}")
        return

    # Get video duration in minutes
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_minutes = (total_frames / fps) / 60
    cap.release()

    # Determine optimal number of frames and columns
    if duration_minutes < 10:
        num_frames, cols = 4, 2
    elif duration_minutes < 30:
        num_frames, cols = 6, 3
    elif duration_minutes < 60:
        num_frames, cols = 9, 3
    elif duration_minutes < 120:
        num_frames, cols = 12, 4
    else:
        num_frames, cols = 16, 4

    # Extract and create thumbnail
    frames_with_timestamps = extract_frames(video_path, num_frames)
    create_thumbnail(frames_with_timestamps, cols=cols, save_path=save_path)
