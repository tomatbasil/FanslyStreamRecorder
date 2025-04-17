import requests
import os
import uuid
import time
import argparse
import json
from bs4 import BeautifulSoup

COOKIES_FILE = "jpg5_cookies.json"


def get_token():
    """
    Get the authentication token and updated cookies from jpg5.su

    Returns:
        str: token
    """
    cookies = load_cookies(COOKIES_FILE)
    response = requests.get("https://jpg5.su/", cookies=cookies)
    soup = BeautifulSoup(response.text, "html.parser")
    scripts = soup.find_all("script")

    token = None
    for script in scripts:
        if script.string and "PF.obj.config.auth_token" in script.string:
            # Extract the token using string manipulation
            token_line = [line.strip() for line in script.string.splitlines() if "PF.obj.config.auth_token" in line][0]
            token = token_line.split("=")[1].strip().strip('";')
            break

    # Update cookies with any set-cookies from the response
    updated_cookies = cookies.copy()
    if response.cookies:
        for name, value in response.cookies.items():
            updated_cookies[name] = value

    save_cookies(updated_cookies, COOKIES_FILE)
    return token


def verify():
    cookies = load_cookies(COOKIES_FILE)
    if not cookies:
        raise ValueError(f"No cookies found in {COOKIES_FILE}")
    auth_token = get_token()
    if not auth_token:
        raise ValueError("Authentication token not found")


def save_cookies(cookies, cookies_file):
    """
    Save cookies to a JSON file

    Args:
        cookies: Dictionary of cookie name-value pairs
        cookies_file: Path to the cookies JSON file
    """
    cookie_list = [{"name": name, "value": value} for name, value in cookies.items()]
    with open(cookies_file, "w") as f:
        json.dump(cookie_list, f)


def load_cookies(cookies_file):
    """
    Load cookies from a JSON file

    Args:
        cookies_file: Path to the cookies JSON file

    Returns:
        Dictionary of cookie name-value pairs
    """
    try:
        with open(cookies_file, "r") as f:
            cookie_data = json.load(f)

        # Convert the list of cookie objects to a simple name-value dictionary
        return {cookie["name"]: cookie["value"] for cookie in cookie_data}
    except Exception:
        return {}


def upload_file(
    file_path: str,
    nsfw: bool = False,
    cookies_file=COOKIES_FILE,
) -> dict:
    """
    Upload a file to jpg5.su

    Args:
        file_path: Path to the file to upload
        nsfw: Whether the content is NSFW (Not Safe For Work)
        cookies_file: Path to the cookies JSON file

    Returns:
        The JSON response from the server
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    auth_token = get_token()
    if not auth_token:
        raise ValueError("Authentication token not found")

    # Determine file type
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()

    # Generate a UUID filename
    uuid_filename = f"{uuid.uuid4()}{ext}"

    # Get current timestamp
    timestamp = int(time.time() * 1000)

    # Define boundary for multipart form
    boundary = "----geckoformboundary1424e527941717af31b4c0c14514a0fc"

    # Prepare the headers - adding all headers from the working request
    headers = {
        "Host": "jpg5.su",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Origin": "https://jpg5.su",
        "Connection": "keep-alive",
        "Referer": "https://jpg5.su/upload",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "TE": "trailers",
    }

    # Load cookies from file
    cookies = load_cookies(cookies_file)
    # Update the timestamp cookie with current time
    cookies["__ddg10_"] = str(int(time.time()))

    # Create multipart form data manually
    with open(file_path, "rb") as f:
        file_content = f.read()

    content_type = get_content_type(ext)

    # Build the multipart body with correct line endings
    # We'll use \r\n explicitly between all parts
    body_parts = []

    # Add file part
    body_parts.append(f"--{boundary}\r\n")
    body_parts.append(f'Content-Disposition: form-data; name="source"; filename="{uuid_filename}"\r\n')
    body_parts.append(f"Content-Type: {content_type}\r\n")
    body_parts.append("\r\n")

    # Convert text parts to bytes
    body_bytes = "".join(body_parts).encode("utf-8")

    # Add binary file content
    body_bytes += file_content

    # Add form fields with proper line breaks
    form_fields = {
        "type": "file",
        "action": "upload",
        "timestamp": str(timestamp),
        "auth_token": auth_token,
        "nsfw": "1" if nsfw else "0",
    }

    for key, value in form_fields.items():
        field_part = f"\r\n--{boundary}\r\n"
        field_part += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
        field_part += f"{value}"
        body_bytes += field_part.encode("utf-8")

    # Add closing boundary
    body_bytes += f"\r\n--{boundary}--\r\n".encode("utf-8")

    # Make the request with cookies
    response = requests.post("https://jpg5.su/json", data=body_bytes, headers=headers, cookies=cookies)

    try:
        return response.json()
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Response text: {response.text}")
        return {"error": "Failed to parse server response"}


def get_content_type(extension: str) -> str:
    """Determine content type based on file extension"""
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
    }
    return content_types.get(extension, "application/octet-stream")


def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(description="Upload files to jpg5.su")
    parser.add_argument("file", help="Path to the file to upload")
    parser.add_argument("--nsfw", action="store_true", help="Mark the upload as NSFW")
    parser.add_argument("--debug", action="store_true", help="Print debug information")
    parser.add_argument("--cookies", default="cookies.json", help="Path to the cookies JSON file")
    parser.add_argument(
        "--token",
        help="Authentication token for the upload",
    )

    args = parser.parse_args()

    try:
        result = upload_file(args.file, args.token, args.nsfw, args.cookies)
        if args.debug:
            print(f"Full response: {result}")

        if "image" in result and "url" in result["image"]:
            print("Upload successful!")
            print(f"URL: {result['image']['url']}")
        else:
            print("Upload failed or returned unexpected response format")
            print(f"Response: {result}")
    except Exception as e:
        print(f"Error uploading file: {e}")


if __name__ == "__main__":
    main()
