import asyncio
import sys
import argparse
from dotenv import load_dotenv
from src.config import CONFIG
from src.monitor import UserMonitor
from src.ui import UI
from src.upload import verify_uploaders


load_dotenv()


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main(headless: bool = False):
    if CONFIG.upload_videos:
        await verify_uploaders()

    monitors: list[UserMonitor] = []
    monitoring_tasks = []
    try:
        for username in CONFIG.users_to_monitor:
            user_monitor = UserMonitor()
            await user_monitor.initialize(username)
            monitors.append(user_monitor)

        # Stagger the start of monitoring with a delay between each user
        # Use a shorter delay if only a few users are being monitored
        stagger_delay = min(3, 15 / len(monitors) if monitors else 1)
        print(f"Starting monitors with {stagger_delay:.1f} second delay between users")

        # Start monitoring for each user with a staggered delay
        for i, monitor in enumerate(monitors):
            if i > 0:
                await asyncio.sleep(stagger_delay)
            monitoring_tasks.append(asyncio.create_task(monitor.start_monitoring()))

        if not headless:
            ui_task = asyncio.create_task(UI.start())
            await asyncio.gather(ui_task, *monitoring_tasks, return_exceptions=True)
        else:
            await asyncio.gather(*monitoring_tasks, return_exceptions=True)

    except asyncio.CancelledError:
        await shutdown(monitors, monitoring_tasks)
    except Exception as e:
        print(f"Unexpected error: {e}")
        await shutdown(monitors, monitoring_tasks)


async def shutdown(monitors, tasks=None):
    print("\nShutting down monitors gracefully...")
    await asyncio.gather(*[monitor.stop() for monitor in monitors], return_exceptions=True)
    print("All monitors stopped.")

    # Cancel any remaining tasks
    if tasks:
        for task in tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete cancellation
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fansly Stream Recorder")
    parser.add_argument("--headless", action="store_true", help="Disable the UI interface")
    args = parser.parse_args()

    try:
        asyncio.run(main(headless=args.headless))
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received")
    finally:
        print("Exiting program")
