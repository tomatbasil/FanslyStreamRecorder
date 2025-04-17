import os
import sys
import threading
import asyncio
import queue
import time
import discord
from src.config import CONFIG


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class DiscordBot:
    def __init__(self):
        self.enabled = False
        self.token = os.getenv("DISCORD_BOT_TOKEN")
        self.channel_id = None
        self.client = None
        self.ready = False
        self.message_queue = queue.Queue()
        self.loop = None
        self.last_message = None  # Track the last message sent
        self.processing_started = False

        self.enabled = CONFIG.discord_enable
        if self.enabled:
            self.channel_id = CONFIG.discord_channel_id
            self.client = discord.Client(intents=discord.Intents.default())

            @self.client.event
            async def on_ready():
                self.ready = True

    async def _process_messages(self):
        self.processing_started = True
        while True:
            try:
                if not self.ready:
                    await asyncio.sleep(1)
                    continue

                while not self.message_queue.empty():
                    message = self.message_queue.get_nowait()
                    channel = self.client.get_channel(int(self.channel_id))
                    if channel:
                        try:
                            # Only send if it's different from the last message
                            if message != self.last_message:
                                await channel.send(message)
                                self.last_message = message
                        except Exception as e:
                            print(f"Error sending Discord message: {e}")
                    else:
                        print(
                            f"Channel not found: {self.channel_id}. Is the bot in the server with access to this channel?"
                        )

                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Error in Discord message processing: {e}")
                await asyncio.sleep(1)

    async def _start_bot(self):
        if self.enabled and self.token:
            try:
                # Start both the client and the message processor
                await asyncio.gather(self.client.start(self.token), self._process_messages())
            except discord.LoginFailure:
                print("\033[91mERROR: Discord bot token is invalid. Discord notifications have been disabled.\033[0m")
                self.enabled = False
            except Exception as e:
                print(
                    f"\033[91mERROR: Failed to start Discord bot: {e}. Discord notifications have been disabled.\033[0m"
                )
                self.enabled = False

    def start(self):
        if not self.enabled:
            return

        if not self.token:
            print("\033[93mWARNING: Discord bot token is missing. Discord notifications have been disabled.\033[0m")
            self.enabled = False
            return

        def run_bot():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._start_bot())

        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()

        # Wait for the bot to be ready
        wait_time = 0
        while not self.processing_started and wait_time < 10:
            time.sleep(0.5)
            wait_time += 0.5

    async def send_message(self, message):
        if not self.enabled:
            return
        self.message_queue.put(message)


discord_bot = DiscordBot()
discord_bot.start()
