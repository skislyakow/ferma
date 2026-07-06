import os
import requests

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
        try:
            data = resp.json()
        except ValueError:
            raise Exception(f"VK API returned non-JSON (HTTP {resp.status_code}): {resp.text[:200]}")
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
            resp = requests.post(upload_url, files={"photo": f}, timeout=60)
            try:
                raw = resp.json()
            except ValueError:
                raise Exception(f"VK upload returned non-JSON (HTTP {resp.status_code}): {resp.text[:200]}")

        saved = self._call("photos.saveWallPhoto", {
            "group_id": self.group_id,
            "photo": raw["photo"],
            "server": raw["server"],
            "hash": raw["hash"],
        })
        photo = saved[0]
        return f"photo{photo['owner_id']}_{photo['id']}"

    def post_to_wall(self, message: str, attachment: str | None = None):
        params = {
            "owner_id": self.owner_id,
            "message": message,
            "from_group": 1,
        }
        if attachment:
            params["attachments"] = attachment
        return self._call("wall.post", params)

    def upload_video(self, file_path: str, title: str = "") -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Video not found: {file_path}")

        save_data = self._call("video.save", {
            "group_id": self.group_id,
            "name": title or "Video",
            "wallpost": 0,
        })
        upload_url = save_data["upload_url"]

        with open(file_path, "rb") as f:
            resp = requests.post(upload_url, files={"video_file": f}, timeout=120)
            try:
                result = resp.json()
            except ValueError:
                raise Exception(f"VK video upload returned non-JSON (HTTP {resp.status_code}): {resp.text[:200]}")

        video_id = result.get("video_id")
        owner_id = result.get("owner_id", self.owner_id)
        return f"video{owner_id}_{video_id}"
