import os
from src.upload.bunkr import BunkrUploader
from src.upload.jpg5 import upload_file as jpg5_upload_file, verify as jpg5_verify
from src.upload.gofile import (
    uploadFile as gofile_upload_file,
    checkApi as gofile_check_api,
)
from src.video import split_video_by_size
from src.config import CONFIG


verified_uploaders = []


async def upload_file(path: str, service: str) -> dict:
    """
    Upload a file to the specified service.

    Args:
        path (str): Path to the file to upload.
        service (str): The service to upload to ('jpg5', 'gofile', 'bunkr').

    Returns:
        dict: A dictionary containing upload results including URLs.
    """
    result = {"success": False, "url": None, "multiple": False, "urls": []}

    try:
        if service == "jpg5":
            if "jpg5" not in verified_uploaders:
                return result
            url = jpg5_upload_file(path)
            if url.get("status_code", 200) == 500:
                return result
            if url:
                result["success"] = True
                result["url"] = url.get("image", {}).get("url", None)

        elif service == "gofile":
            if "gofile" not in verified_uploaders:
                return result
            upload_result = gofile_upload_file(path)
            if upload_result and "downloadPage" in upload_result:
                result["success"] = True
                result["url"] = upload_result["downloadPage"]
            else:
                print(f"GoFile upload result: {upload_result}")

        elif service == "bunkr":
            if "bunkr" not in verified_uploaders:
                return result
            # Split the video into chunks if it's too large
            file_size = os.path.getsize(path)
            uploader = BunkrUploader(os.environ.get("BUNKR_TOKEN"), config={"silent": True})

            if file_size > uploader.max_file_size:
                max_size_gb = uploader.max_file_size / (1024 * 1024 * 1024)
                split_paths = split_video_by_size(path, max_size_gb * 0.9)

                if isinstance(split_paths, list):
                    # Use non-async method (run synchronously)
                    urls = uploader.upload_files(split_paths, None, 1)

                    if urls:
                        result["success"] = True
                        result["multiple"] = True
                        result["urls"] = urls

                    if CONFIG.delete_split_video_after_upload:
                        try:
                            for p in split_paths:
                                os.remove(p)
                        except Exception as e:
                            print(f"Error removing split video files {split_paths}: {str(e)}")
            else:
                # Use non-async method (run synchronously)
                url = uploader.upload_file(path)

                if url:
                    result["success"] = True
                    result["url"] = url
        else:
            raise ValueError(f"Unsupported upload service: {service}")

    except Exception as e:
        print(f"Error uploading to {service}: {str(e)}")
        result["error"] = str(e)

    return result


async def verify_uploaders():
    """
    Verify the uploaders by checking if they can upload a test file.
    """
    try:
        BunkrUploader(os.environ.get("BUNKR_TOKEN"), config={"silent": True})
        verified_uploaders.append("bunkr")
    except Exception as e:
        print(f"Error verifying bunkr uploader: {e}")

    try:
        jpg5_verify()
        verified_uploaders.append("jpg5")
    except Exception as e:
        print(f"Error verifying jpg5 uploader: {e}")

    try:
        gofile_check_api()
        verified_uploaders.append("gofile")
    except Exception as e:
        print(f"Error verifying gofile uploader: {e}")

    return verified_uploaders
