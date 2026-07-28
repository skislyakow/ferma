import os
import time
import requests

VK_API = "https://api.vk.com/method"
RETRYABLE_CODES = {6, 9, 10}


class VKPoster:
    def __init__(self, token: str, group_id: str, api_version: str = "5.199"):
        self.token = token
        self.group_id = group_id
        self.api_v = api_version
        self.owner_id = -int(group_id)

    def _call(self, method, params=None, _retries=0):
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
            code = data["error"]["error_code"]
            if code in RETRYABLE_CODES and _retries < 3:
                delay = data["error"].get("retry_after", 1 * (_retries + 1))
                print(f"[VK] Rate limited (code {code}), retry {_retries+1}/3 in {delay}s")
                time.sleep(delay)
                return self._call(method, params, _retries + 1)
            raise Exception(f"VK API error [{code}]: {data['error']['error_msg']}")
        return data.get("response")

    def upload_photo(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Photo not found: {file_path}")

        upload_data = self._call("photos.getWallUploadServer", {"group_id": self.group_id})
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

        try:
            return self._upload_video_via_stories(file_path)
        except Exception:
            return self._upload_video_via_wall(file_path)

    def _upload_video_via_stories(self, file_path: str) -> str:
        upload_data = self._call("stories.getVideoUploadServer", {
            "group_id": self.group_id,
        })
        upload_url = upload_data["upload_url"]

        with open(file_path, "rb") as f:
            resp = requests.post(upload_url, files={"video_file": f}, timeout=120)
            try:
                raw = resp.json()
            except ValueError:
                raise Exception(f"VK video upload returned non-JSON (HTTP {resp.status_code}): {resp.text[:200]}")

        upload_result = raw.get("response", {}).get("upload_result") or raw.get("upload_result")
        if not upload_result:
            raise Exception(f"No upload_result in stories upload response: {raw}")

        saved = self._call("stories.save", {"upload_results": upload_result})
        items = saved.get("items", [])
        if not items:
            raise Exception("stories.save returned no items")

        story = items[0]
        video = story.get("video") or story.get("photo")
        vid = video.get("id")
        vowner = video.get("owner_id", self.owner_id)

        attach = f"video{vowner}_{vid}"
        ak = video.get("access_key")
        if ak:
            attach += f"_{ak}"
        return attach

    def _upload_video_via_wall(self, file_path: str) -> str:
        save_data = self._call("video.save", {
            "group_id": self.group_id,
            "name": "Video",
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
