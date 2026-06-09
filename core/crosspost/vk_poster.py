import os
import requests
import time

VK_API = "https://api.vk.com/method"


class VKPoster:
    def __init__(self, token: str, group_id: str, api_version: str = "5.199"):
        self.token = token
        self.group_id = group_id
        self.api_v = api_version
        self.owner_id = -int(group_id)

    def _call(self, method, params=None):
        if params is None:
            params = {}
        params.update({
            "access_token": self.token,
            "v": self.api_v,
        })
        resp = requests.post(f"{VK_API}/{method}", data=params, timeout=30)
        data = resp.json()
        if data.get("error"):
            raise Exception(f"VK API error [{data['error']['error_code']}]: {data['error']['error_msg']}")
        return data.get("response")

    def _get_upload_url(self) -> str:
        return self._call("photos.getWallUploadServer", {"group_id": self.group_id})

    def upload_photo(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Photo not found: {file_path}")

        upload_data = self._get_upload_url()
        upload_url = upload_data["upload_url"]

        with open(file_path, "rb") as f:
            raw = requests.post(upload_url, files={"photo": f}, timeout=60).json()

        saved = self._call("photos.saveWallPhoto", {
            "group_id": self.group_id,
            "photo": raw["photo"],
            "server": raw["server"],
            "hash": raw["hash"],
        })
        photo = saved[0]
        return f"photo{photo['owner_id']}_{photo['id']}"

    def post_to_wall(self, message: str, attachment: str = None):
        params = {
            "owner_id": self.owner_id,
            "message": message,
            "from_group": 1,
        }
        if attachment:
            params["attachments"] = attachment
        return self._call("wall.post", params)
