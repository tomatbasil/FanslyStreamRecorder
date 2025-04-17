import asyncio
import re
import subprocess
import os
from datetime import datetime
from src.fansly import fetch_user_data, fetch_stream_data
from src.config import CONFIG
from src.video import (
    compress_video,
    check_disk_space_and_cleanup,
    auto_create_thumbnail,
)
from src.upload import upload_file
from src.discord_bot import discord_bot
from src.ui import UI


class UserMonitor:
    def __init__(self):
        self.username = None
        self.user_data = None
        self.user_id = None
        self.is_recording = False
        self.current_output_path = None
        self.ui = None
        self.discord_bot = discord_bot
        self._running = True

    async def initialize(self, username):
        self.username = username
        self.ui = UI
        if self.ui:
            self.ui.add_user(username)
            self.ui.update_user(username, "Fetching user data...")
        self.user_data = await fetch_user_data(username)
        self.user_id = self.user_data.get("response")[0].get("id")
        if self.ui:
            self.ui.update_user(username, "User data fetched successfully.")

    def sanitize_username(self, username):
        sanitized = re.sub(r"[^\w\-]", "", username)
        return sanitized.strip("-_")

    def update_ui(self, status, recording=None, current_file=None):
        if self.ui:
            self.ui.update_user(
                self.username,
                status,
                recording=recording,
                current_file=current_file,
            )

    async def stop(self):
        self._running = False

    async def start_monitoring(self):
        if not self.user_id:
            raise RuntimeError("UserMonitor must be initialized first")

        while self._running:
            try:
                if self.is_recording:
                    await asyncio.sleep(CONFIG.check_interval)
                    continue

                stream_data = await fetch_stream_data(self.user_id)
                if stream_data.get("access") and stream_data.get("playbackUrl"):
                    await self.start_recording(stream_data["playbackUrl"])
                else:
                    self.update_ui("Waiting for stream...", recording=False)

                await asyncio.sleep(CONFIG.check_interval)
            except asyncio.CancelledError:
                await self.stop()
                break
            except Exception as e:
                print(f"Error during monitoring: {str(e)}")
                self.update_ui("Error occurred during monitoring", recording=False)

    async def start_recording(self, url: str):
        if self.is_recording:
            return  # Skip if already recording

        if CONFIG.remove_old_recordings:
            await check_disk_space_and_cleanup(CONFIG.output_directory, CONFIG.min_free_disk_space)

        await self.discord_bot.send_message(f"🔴 {self.username}: Stream Starting")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sanitized_username = self.sanitize_username(self.username)
        output_path = os.path.join(
            CONFIG.output_directory,
            sanitized_username,
            f"{sanitized_username}_{timestamp}.mp4",
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        self.current_output_path = output_path
        self.update_ui("Recording", recording=True, current_file=os.path.basename(output_path))

        # TEMPORARY TESTING MODE - Record for just 60 seconds
        if CONFIG.dev_mode:
            ffmpeg_cmd = [
                "ffmpeg",
                "-loglevel",
                "quiet",
                "-i",
                url,
                "-c",
                "copy",
                "-f",
                "mp4",
                "-t",
                "60",  # Record for only 60 seconds
                output_path,
            ]
            print("TESTING MODE: Recording for only 60 seconds")
        else:
            ffmpeg_cmd = [
                "ffmpeg",
                "-loglevel",
                "quiet",
                "-i",
                url,
                "-c",
                "copy",
                "-f",
                "mp4",
                output_path,
            ]

        try:
            process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.is_recording = True
            while process.poll() is None:
                await asyncio.sleep(1)

            asyncio.create_task(self.handle_stream_end())
        except Exception as e:
            print(f"Error recording stream: {str(e)}")
            self.is_recording = False

    async def handle_stream_end(self):
        self.is_recording = False
        await self.discord_bot.send_message(f"⚫ {self.username}: Stream Ended")

        video_path = self.current_output_path
        thumbnail_path = None
        if not os.path.exists(video_path):
            print(f"Video file {video_path} does not exist")
            return

        if CONFIG.generate_thumbnail:
            thumbnail_name = os.path.splitext(video_path)[0] + ".jpg"
            auto_create_thumbnail(video_path, thumbnail_name)
            thumbnail_path = thumbnail_name
        if CONFIG.compress_videos:
            video_path = await compress_video(self.current_output_path, self.username)

        videos = []
        thumbnail_url = None
        if CONFIG.upload_videos:
            if video_path:
                video_uploads = await asyncio.gather(
                    upload_file(video_path, "bunkr"), upload_file(video_path, "gofile")
                )
                videos.extend(
                    [
                        {"service": "bunkr", "result": video_uploads[0]},
                        {"service": "gofile", "result": video_uploads[1]},
                    ]
                )

            if thumbnail_path:
                thumbnail_uploads = await asyncio.gather(
                    upload_file(thumbnail_path, "jpg5"),
                    upload_file(thumbnail_path, "bunkr"),
                )
                # Fixed: properly extract URL from the result dictionary
                jpg5_result = thumbnail_uploads[0]
                bunkr_result = thumbnail_uploads[1]

                # Check if jpg5 upload was successful and has a URL
                if jpg5_result and jpg5_result.get("success") and jpg5_result.get("url"):
                    thumbnail_url = jpg5_result.get("url")
                # If jpg5 failed, try bunkr result
                elif bunkr_result and bunkr_result.get("success") and bunkr_result.get("url"):
                    thumbnail_url = bunkr_result.get("url")

                # Debug output to help troubleshoot
                if not thumbnail_url:
                    print(f"Thumbnail upload failed - jpg5 result: {jpg5_result}")
                    print(f"Thumbnail upload failed - bunkr result: {bunkr_result}")

            if CONFIG.discord_enable:
                await self.send_end_message(videos, thumbnail_url=thumbnail_url)
            self.save_upload_results(videos, thumbnail_url=thumbnail_url)
        self.update_ui("Stream ended", recording=False, current_file=None)
        self.current_output_path = None

    async def send_end_message(self, videos, thumbnail_url=None):
        discord_msg = "🟢 Upload finished.\n```\n"
        current_date = datetime.now().strftime("%b %d %Y")
        discord_msg += f"{current_date}\n"
        if thumbnail_url:
            discord_msg += f"[IMG]{thumbnail_url}[/IMG]\n"
        else:
            discord_msg += "\n"
        if videos:
            sorted_uploads = sorted(
                videos,
                key=lambda u: 0 if u["service"].lower() == "gofile" else 1,
            )

            for upload in sorted_uploads:
                result = upload["result"]
                if result.get("multiple") and "urls" in result:
                    for idx, url in enumerate(result["urls"]):
                        discord_msg += f"{url}\n"
                else:
                    url = result.get("url", "No URL provided")
                    discord_msg += f"{url}\n"
        discord_msg += "```"
        await self.discord_bot.send_message(discord_msg)

    def save_upload_results(self, videos, thumbnail_url=None):
        current_date = datetime.now().strftime("%b %d %Y")
        if self.current_output_path:
            txt_file_path = os.path.splitext(self.current_output_path)[0] + ".txt"
            txt_content = f"{current_date}\n\n"

            if thumbnail_url:
                txt_content += f"Thumbnail: {thumbnail_url}\n\n"
            if videos:
                txt_content += "Video Links:\n"
                for upload in videos:
                    result = upload["result"]
                    service_name = upload["service"].capitalize()

                    if result.get("multiple") and "urls" in result:
                        for idx, url in enumerate(result["urls"]):
                            txt_content += f"{service_name} {idx + 1}: {url}\n"
                    else:
                        url = result.get("url", "No URL provided")
                        txt_content += f"{service_name}: {url}\n"

            try:
                with open(txt_file_path, "w", encoding="utf-8") as f:
                    f.write(txt_content)
                print(f"Saved upload information to {txt_file_path}")
            except Exception as e:
                print(f"Failed to save upload information: {str(e)}")
