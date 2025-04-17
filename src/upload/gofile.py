import requests


def response_handler(response):
    if response["status"] == "ok":
        return response["data"]

    elif "error-" in response["status"]:
        error = response["status"].split("-")[1]
        raise Exception(error)


def checkAccountExists(token):
    """
    Check if account exists using the updated API endpoint.

    Args:
        token: GoFile API token

    Returns:
        bool: True if account exists, False otherwise
    """
    try:
        checkAccountExists_response = requests.get(
            url="https://api.gofile.io/accounts/getid", headers={"Authorization": f"Bearer {token}"}
        ).json()

        if checkAccountExists_response["status"] == "ok":
            return True
        else:
            return False
    except Exception:
        return False


def getAccountId(token):
    """
    Get account ID using the updated API endpoint.

    Args:
        token: GoFile API token

    Returns:
        str: Account ID if successful
    """
    getAccountId_response = requests.get(
        url="https://api.gofile.io/accounts/getid", headers={"Authorization": f"Bearer {token}"}
    ).json()

    return response_handler(getAccountId_response)


def getAccountInfo(token, accountId=None):
    """
    Get account information using the updated API endpoint.

    Args:
        token: GoFile API token
        accountId: Account ID (optional, will be fetched if not provided)

    Returns:
        dict: Account information
    """
    if not accountId:
        accountId = getAccountId(token)

    getAccountInfo_response = requests.get(
        url=f"https://api.gofile.io/accounts/{accountId}", headers={"Authorization": f"Bearer {token}"}
    ).json()

    return response_handler(getAccountInfo_response)


def checkApi():
    checkApi_response = requests.get(url="https://api.gofile.io/").json()

    return response_handler(checkApi_response)


def getServer(zone: str = "eu"):
    """
    Get a server for uploading files.

    Args:
        zone: Server zone ('eu', 'na', 'ap'). Defaults to 'eu'.

    Returns:
        Server information dictionary with 'name' and 'zone' keys.
    """
    getServer_response = requests.get(url="https://api.gofile.io/servers").json()
    server_data = response_handler(getServer_response)

    # Try to find servers in the requested zone
    available_servers = [s for s in server_data["serversAllZone"] if s["zone"] == zone]

    # If no servers in requested zone, use any available server
    if not available_servers and server_data["serversAllZone"]:
        available_servers = server_data["serversAllZone"]

    # If servers are available, return the first one
    if available_servers:
        return available_servers[0]

    # Fallback in case of unexpected response format
    raise Exception("noServersAvailable")


def uploadFile(
    file: str,
    token: str = None,
    folderId: str = None,
    server: str = None,
):
    if server is None:
        server = getServer()["name"]

    # Prepare the multipart form data
    files = {"file": open(file, "rb")}

    # Prepare optional parameters
    data = {}
    if folderId:
        data["folderId"] = folderId
    if token:
        # If token is provided, add it as Authorization header
        headers = {"Authorization": f"Bearer {token}"}
    else:
        headers = {}

    # Make the request
    uploadFile_response = requests.post(
        url=f"https://{server}.gofile.io/uploadFile", files=files, data=data, headers=headers
    ).json()

    return response_handler(uploadFile_response)


def getContent(contentId, token):
    getContent_response = requests.get(url=f"https://api.gofile.io/getContent?contentId={contentId}&token={token}")

    return response_handler(getContent_response)


def createFolder(parentFolderId, folderName, token):
    createFolder_response = requests.put(
        url="https://api.gofile.io/createFolder",
        data={"parentFolderId": parentFolderId, "folderName": folderName, "token": token},
    ).json()

    return response_handler(createFolder_response)


def setFolderOption(token, folderId, option, value):
    setFolderOptions_response = requests.put(
        url="https://api.gofile.io/setFolderOption",
        data={"token": token, "folderId": folderId, "option": option, "value": value},
    ).json()

    return response_handler(setFolderOptions_response)


def copyContent(contentsId, folderIdDest, token):
    copyContent_reponse = requests.put(
        url="https://api.gofile.io/copyContent",
        data={"contentsId": contentsId, "folderIdDest": folderIdDest, "token": token},
    ).json()

    return response_handler(copyContent_reponse)


def deleteFolder(folderId, token):  # deprecated
    print("Deprecated, use deleteContent() instead")
    deleteFolder_response = requests.delete(
        url="https://api.gofile.io/deleteContent", data={"folderId": folderId, "token": token}
    ).json()

    return response_handler(deleteFolder_response)


def deleteFile(fileId, token):  # deprecated
    print("Deprecated, use deleteContent() instead")
    deleteFile_response = requests.delete(
        url="https://api.gofile.io/deleteContent", data={"fileId": fileId, "token": token}
    ).json()

    return response_handler(deleteFile_response)


def deleteContent(contentId, token):
    deleteContent_response = requests.delete(
        url="https://api.gofile.io/deleteContent", data={"contentId": contentId, "token": token}
    ).json()

    return response_handler(deleteContent_response)


def getAccountDetails(token: str, allDetails: bool = False):
    if allDetails:
        getAccountDetails_response = requests.get(
            url=f"https://api.gofile.io/getAccountDetails?token={token}&allDetails=true"
        ).json()
    else:
        getAccountDetails_response = requests.get(url=f"https://api.gofile.io/getAccountDetails?token={token}").json()

    return response_handler(getAccountDetails_response)
