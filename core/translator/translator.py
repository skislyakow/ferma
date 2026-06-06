import requests

from core.config import load_channel_config


class Translator:
    def __init__(self, cfg: dict):
        self.api_key = cfg["YC_TRANSLATE_API_KEY"]
        self.folder_id = cfg["YC_FOLDER_ID"]
        self.source_lang = cfg["SOURCE_LANG"]
        self.target_lang = cfg["TARGET_LANG"]

    def translate(self, text: str) -> str:
        if not text or not text.strip():
            return text
        if self.source_lang == self.target_lang:
            return text
        if not self.api_key:
            print("[Translator] No Yandex Translate API key")
            return text

        url = "https://translate.api.cloud.yandex.net/translate/v2/translate"
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "targetLanguageCode": self.target_lang,
            "texts": [text],
            "format": "PLAIN_TEXT",
        }
        if self.folder_id:
            body["folderId"] = self.folder_id

        try:
            resp = requests.post(url, headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            return resp.json()["translations"][0]["text"]
        except Exception as e:
            print(f"[Translator] Yandex error: {e}")
            return text
