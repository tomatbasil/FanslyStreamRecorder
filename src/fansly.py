import sys
import aiohttp
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

AUTH_TOKEN = os.getenv("FANSLY_AUTH_TOKEN")
if not AUTH_TOKEN:
    print("Error: FANSLY_AUTH_TOKEN environment variable is not set")
    print("Please create a .env file with your Fansly authentication token")
    sys.exit(1)

headers = {
    "authority": "apiv3.fansly.com",
    "accept": "application/json, text/plain, */*",
    "accept-language": "en;q=0.8,en-US;q=0.7",
    "authorization": os.getenv("FANSLY_AUTH_TOKEN"),
    "origin": "https://fansly.com",
    "referer": "https://fansly.com/",
    "sec-ch-ua": '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
}

BASE_URL = "https://apiv3.fansly.com/api/v1/"


async def fetch_api(endpoint, max_retries: int = 5, initial_delay: float = 1.0):
    retry_count = 0
    delay = initial_delay

    while True:
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(verify_ssl=False)
            ) as session:
                async with session.get(
                    BASE_URL + endpoint, headers=headers
                ) as response:
                    if response.status == 429:
                        if retry_count >= max_retries:
                            response.raise_for_status()
                        retry_count += 1
                        # Get retry-after header or use exponential backoff
                        retry_after = float(response.headers.get("Retry-After", delay))
                        await asyncio.sleep(retry_after)
                        delay *= 2  # Exponential backoff
                        continue

                    response.raise_for_status()
                    return await response.json()
        except aiohttp.ClientError:
            if retry_count >= max_retries:
                raise
            retry_count += 1
            await asyncio.sleep(delay)
            delay *= 2


async def fetch_user_data(username: str):
    endpoint = f"account?usernames={username}&ngsw-bypass=true"
    return await fetch_api(endpoint)


async def fetch_stream_data(user_id: str):
    endpoint = f"streaming/channel/{user_id}?ngsw-bypass=true"
    response = await fetch_api(endpoint)
    if response and response.get("success"):
        stream_data = response.get("response", {}).get("stream", {})
    else:
        stream_data = {}
    return stream_data
