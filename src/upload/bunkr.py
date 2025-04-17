import mimetypes
import os
import math
import uuid
import requests
from typing import TypedDict, Optional, List, Dict, Any
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed


class ChunkSizeConfig(TypedDict):
    max: str
    default: str
    timeout: int


class FileIdentifierConfig(TypedDict):
    min: int
    max: int
    default: int
    force: bool


class StripTagsConfig(TypedDict):
    default: bool
    video: bool
    force: bool
    blacklistExtensions: List[str]


class BunkrConfig(TypedDict):
    maintenance: bool
    private: bool
    enableUserAccounts: bool
    maxSize: str
    chunkSize: ChunkSizeConfig
    fileIdentifierLength: FileIdentifierConfig
    stripTags: StripTagsConfig
    temporaryUploadAges: List[int]
    defaultTemporaryUploadAge: int


class UserPermissions(TypedDict):
    user: bool
    vip: bool
    vvip: bool
    moderator: bool
    admin: bool
    superadmin: bool


class VerifyResponse(TypedDict):
    success: bool
    username: str
    permissions: UserPermissions
    group: str
    retentionPeriods: List[int]
    defaultRetentionPeriod: int


class NodeResponse(TypedDict):
    success: bool
    url: str


class BunkrUploader:
    """
    A class to handle file uploads to Bunkr.
    This class provides functionality to upload single files, multiple files, and entire directories
    to Bunkr.cr. It supports both single-chunk and multi-chunk uploads, handles authentication,
    and provides methods to interact with albums.
    Attributes:
        token (str): The API token for authentication with Bunkr.cr.
        chunk_size (int): Maximum size in bytes for each chunk during upload (default: 25MB).
        headers (dict): HTTP headers used for API requests.
        verify (VerifyResponse): Response from token verification.
        check (BunkrConfig): Server configuration and limits.
        node (NodeResponse): Upload node information.
        upload_url (str): URL endpoint for file uploads.
    Example:
        >>> uploader = BunkrUploader(token="your_api_token")
        >>> url = uploader.upload_file("path/to/file.jpg")
        >>> print(url)
        'https://bunkr.cr/file/...'
    Note:
        - The token must be valid and verified with Bunkr.cr
        - File size limits and chunk sizes are enforced according to server configuration
        - Supports parallel uploads for multiple files
    """

    MAX_RETRIES = 3  # Add this constant after the class definition

    def __init__(self, token: str, config={"chunk_size": 25000000, "silent": False}) -> None:
        """
        Initialize the uploader.

        :param token: The API token for authentication.
        :param config: A dictionary containing configuration options:
                      - chunk_size: Maximum size (in bytes) for each chunk.
                      - silent: If True, suppress progress bars.
        """
        self.token = token
        self.chunk_size = config.get("chunk_size", 25000000)
        self.silent = config.get("silent", False)
        self.headers = {
            "token": self.token,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://dash.bunkr.cr",
            "Cache-Control": "no-cache",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://dash.bunkr.cr",
        }
        self.verify: VerifyResponse = requests.post(
            "https://dash.bunkr.cr/api/tokens/verify",
            headers=self.headers,
            data={"token": self.token},
        ).json()
        if not self.verify.get("success"):
            raise ValueError("Invalid API token.")

        self.check: BunkrConfig = requests.get("https://dash.bunkr.cr/api/check").json()
        self.node: NodeResponse = requests.get("https://dash.bunkr.cr/api/node", headers=self.headers).json()
        self.upload_url = self.node.get("url")

        max_chunk_size_str = self.check.get("chunkSize").get("max")
        max_chunk_size_bytes = int(max_chunk_size_str.replace("MB", "").strip()) * 1024 * 1024
        if self.chunk_size > max_chunk_size_bytes:
            print(f"Chunk size exceeds maximum allowed size ({max_chunk_size_str}). Setting to default value.")
            default_chunk_size_str = self.check.get("chunkSize").get("default")
            self.chunk_size = int(default_chunk_size_str.replace("MB", "").strip()) * 1024 * 1024

    def refresh_url(self) -> None:
        """
        Refresh the upload URL from the server.
        """
        self.node = requests.get("https://dash.bunkr.cr/api/node", headers=self.headers).json()
        self.upload_url = self.node.get("url")

    def get_albums(self) -> List[Dict[str, Any]]:
        """
        Get a list of users albums from the server.

        :return: A list of album objects.
        """
        response = requests.get("https://dash.bunkr.cr/api/albums", headers=self.headers)
        if response.status_code == 200:
            return response.json().get("albums", [])
        return []

    def get_album_by_name(self, album_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific album by name.

        :param album_name: The name of the album to search for.
        :return: The album object if found, None otherwise.
        """
        albums = self.get_albums()
        for album in albums:
            if album.get("name").lower() == album_name.lower():
                return album
        return None

    def get_album_id_by_name(self, album_name: str) -> Optional[str]:
        """
        Get the ID of a specific album by name.

        :param album_name: The name of the album to search for.
        :return: The album ID if found, None otherwise.
        """
        album = self.get_album_by_name(album_name)
        return album.get("id", None) if album else None

    def verify_file(self, file_path: str) -> bool:
        """
        Verify that the file exists, is readable and under the size limit.

        :param file_path: Path to the file to be verified.
        :return: True if the file exists and is readable, False otherwise.
        """
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return False
        if not os.access(file_path, os.R_OK):
            print(f"File not readable: {file_path}")
            return False
        # New validations using self.check
        total_filesize = os.path.getsize(file_path)

        max_size_str = self.check.get("maxSize", "2000MB")
        max_size_bytes = int(max_size_str.replace("MB", "").strip()) * 1024 * 1024
        if total_filesize > max_size_bytes:
            print(f"File size {total_filesize} exceeds maximum allowed size of {max_size_bytes} bytes.")
            return False
        return True

    def _upload_single_file(
        self,
        file_path: str,
        total_filesize: int,
        content_type: str,
        album_id: Optional[str] = None,
    ) -> Optional[str]:
        if self.silent:
            # No progress bar in silent mode
            with open(file_path, "rb") as f:
                files = {"files[]": (os.path.basename(file_path), f, content_type)}
                request_headers = self.headers.copy()
                request_headers["albumid"] = album_id if album_id else ""

                response = requests.post(self.upload_url, files=files, headers=request_headers)

                if response.status_code == 200:
                    response_data = response.json()
                    if response_data.get("success"):
                        files_data = response_data.get("files", [])
                        if files_data and len(files_data) > 0:
                            file_url = files_data[0].get("url")
                            return file_url
                else:
                    print(f"Error uploading file: HTTP {response.status_code}")
                    print("Response:", response.text)
                    return None
        else:
            with tqdm(
                total=total_filesize,
                unit="B",
                unit_scale=True,
                desc=f"Uploading {os.path.basename(file_path)}",
            ) as pbar:
                with open(file_path, "rb") as f:
                    files = {"files[]": (os.path.basename(file_path), f, content_type)}
                    request_headers = self.headers.copy()
                    request_headers["albumid"] = album_id if album_id else ""

                    response = requests.post(self.upload_url, files=files, headers=request_headers)
                    pbar.update(total_filesize)

                    if response.status_code == 200:
                        response_data = response.json()
                        if response_data.get("success"):
                            files_data = response_data.get("files", [])
                            if files_data and len(files_data) > 0:
                                file_url = files_data[0].get("url")
                                return file_url
                    else:
                        print(f"Error uploading file: HTTP {response.status_code}")
                        print("Response:", response.text)
                        return None

    def _upload_chunk_file(
        self,
        file_path: str,
        total_filesize: int,
        total_chunks: int,
        content_type: str,
        album_id: Optional[str] = None,
    ) -> Optional[str]:
        dzuuid = str(uuid.uuid4())

        # Use tqdm only if not in silent mode
        if not self.silent:
            chunks_iter = tqdm(range(total_chunks), desc=f"Uploading {os.path.basename(file_path)} chunks")
        else:
            chunks_iter = range(total_chunks)

        for chunk_index in chunks_iter:
            retries = 0
            while retries < self.MAX_RETRIES:
                try:
                    chunk_byte_offset = chunk_index * self.chunk_size
                    with open(file_path, "rb") as f:
                        f.seek(chunk_byte_offset)
                        chunk_data = f.read(self.chunk_size)

                    boundary = f"----geckoformboundary{uuid.uuid4().hex[:24]}"
                    upload_headers = self.headers.copy()
                    upload_headers.update(
                        {
                            "Content-Type": f"multipart/form-data; boundary={boundary}",
                            "Accept-Encoding": "gzip, deflate, br, zstd",
                            "Sec-GPC": "1",
                            "Connection": "keep-alive",
                            "Sec-Fetch-Dest": "empty",
                            "Sec-Fetch-Mode": "cors",
                            "Sec-Fetch-Site": "cross-site",
                            "TE": "trailers",
                        }
                    )

                    # Construct multipart form-data manually
                    form_data = []

                    # Add form fields
                    fields = {
                        "dzuuid": dzuuid,
                        "dzchunkindex": str(chunk_index),
                        "dztotalfilesize": str(total_filesize),
                        "dzchunksize": str(self.chunk_size),
                        "dztotalchunkcount": str(total_chunks),
                        "dzchunkbyteoffset": str(chunk_byte_offset),
                    }

                    for field_name, field_value in fields.items():
                        form_data.append(f"--{boundary}")
                        form_data.append(f'Content-Disposition: form-data; name="{field_name}"')
                        form_data.append("")
                        form_data.append(field_value)

                    # Add file data
                    form_data.append(f"--{boundary}")
                    form_data.append(
                        f'Content-Disposition: form-data; name="files[]"; filename="{os.path.basename(file_path)}"'
                    )
                    form_data.append("Content-Type: application/octet-stream")
                    form_data.append("")

                    # Convert form_data to bytes and combine with chunk data
                    form_bytes = "\r\n".join(form_data).encode() + b"\r\n"
                    end_boundary = f"\r\n--{boundary}--\r\n".encode()

                    # Combine all parts into final payload
                    payload = form_bytes + chunk_data + end_boundary

                    response = requests.post(self.upload_url, data=payload, headers=upload_headers)

                    if response.status_code == 200:
                        response_data = response.json()
                        if chunk_index == total_chunks - 1 and response_data.get("success"):
                            # Final chunk success, try to finalize
                            finish_retries = 0
                            while finish_retries < self.MAX_RETRIES:
                                try:
                                    finish_data = {
                                        "files": [
                                            {
                                                "uuid": dzuuid,
                                                "original": os.path.basename(file_path),
                                                "type": content_type,
                                                "albumid": album_id,
                                                "filelength": None,
                                                "age": None,
                                            }
                                        ]
                                    }

                                    finish_response = requests.post(
                                        f"{self.upload_url}/finishchunks",
                                        json=finish_data,
                                        headers=self.headers,
                                    )

                                    if finish_response.status_code == 200:
                                        finish_data = finish_response.json()
                                        if finish_data.get("success"):
                                            files_data = finish_data.get("files", [])
                                            if files_data and len(files_data) > 0:
                                                file_url = files_data[0].get("url")
                                                return file_url
                                    finish_retries += 1
                                    if finish_retries < self.MAX_RETRIES:
                                        print(f"Retrying finalization (attempt {finish_retries + 1})...")
                                except Exception as e:
                                    print(f"Error finalizing upload: {str(e)}")
                                    finish_retries += 1
                                    if finish_retries < self.MAX_RETRIES:
                                        print(f"Retrying finalization (attempt {finish_retries + 1})...")
                        break  # Success, exit retry loop
                    else:
                        raise Exception(f"HTTP {response.status_code}: {response.text}")
                except Exception as e:
                    print(f"Error uploading chunk {chunk_index + 1}: {str(e)}")
                    retries += 1
                    if retries < self.MAX_RETRIES:
                        print(f"Retrying chunk {chunk_index + 1} (attempt {retries + 1})...")
                    else:
                        print(f"Failed to upload chunk {chunk_index + 1} after {self.MAX_RETRIES} attempts")
                        return None
        return None

    def upload_file(self, file_path: str, album_id: Optional[str] = None) -> Optional[str]:
        """
        Upload a single file to Bunkr with retries.

        Args:
            file_path (str): Path to the file to be uploaded
            album_id (Optional[str], optional): Album ID to upload the file to. Defaults to None.

        Returns:
            Optional[str): The URL of the uploaded file if successful, None if the upload fails
        """
        if self.check.get("maintenance", False):
            print("Server is under maintenance. Upload aborted.")
            return None

        if not self.verify_file(file_path):
            return None

        total_filesize = os.path.getsize(file_path)
        total_chunks = math.ceil(total_filesize / self.chunk_size)
        content_type, _ = mimetypes.guess_type(file_path) or "application/octet-stream"

        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                if total_chunks == 1:
                    result = self._upload_single_file(file_path, total_filesize, content_type, album_id)
                else:
                    result = self._upload_chunk_file(file_path, total_filesize, total_chunks, content_type, album_id)

                if result:
                    return result

                raise Exception("Upload failed")
            except Exception as e:
                print(f"Error uploading file: {str(e)}")
                retries += 1
                if retries < self.MAX_RETRIES:
                    print(f"Refreshing upload URL and retrying (attempt {retries + 1})...")
                    self.refresh_url()
                else:
                    print(f"Failed to upload file after {self.MAX_RETRIES} attempts")
                    return None

        return None

    def upload_files(self, file_paths: List[str], album_id: Optional[str] = None, batch_size: int = 3) -> List[str]:
        """
        Upload multiple files to Bunkr in parallel batches.

        Args:
            file_paths (list): List of file paths to upload
            album_id (str, optional): Album ID to upload to. Defaults to None.
            batch_size (int, optional): Number of concurrent uploads. Defaults to 3.

        Returns:
            list: List of uploaded file URLs
        """
        if batch_size < 1:
            batch_size = 1

        uploaded_files = []

        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            # Submit all upload tasks
            future_to_file = {
                executor.submit(self.upload_file, file_path, album_id): file_path for file_path in file_paths
            }

            # Process completed uploads as they finish
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    if result:
                        uploaded_files.append(result)
                    else:
                        print(f"Failed to upload: {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"Error uploading {os.path.basename(file_path)}: {str(e)}")

        return uploaded_files

    def upload_directory(self, directory_path: str, album_id: Optional[str] = None, batch_size: int = 3) -> List[str]:
        """
        Upload all files in a directory to Bunkr in parallel batches.

        Args:
            directory_path (str): Path to the directory containing files to upload
            album_id (str, optional): Album ID to upload to. Defaults to None.
            batch_size (int, optional): Number of concurrent uploads. Defaults to 3.

        Returns:
            list: List of uploaded file URLs
        """
        file_paths = [
            os.path.join(directory_path, f)
            for f in os.listdir(directory_path)
            if os.path.isfile(os.path.join(directory_path, f))
        ]
        return self.upload_files(file_paths, album_id, batch_size)
