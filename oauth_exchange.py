import sys
import json
import urllib.parse
import requests


VK_API = "https://api.vk.com/method"
REDIRECT_URI = "https://oauth.vk.com/blank.html"
GROUP_IDS = "239558545,239858334,240220784,239707751,239469377"
SCOPE = "wall,photos,manage,docs,messages,stories,offline"
API_VERSION = "5.199"


def build_auth_url(client_id):
    params = {
        "client_id": client_id,
        "display": "page",
        "redirect_uri": REDIRECT_URI,
        "group_ids": GROUP_IDS,
        "scope": SCOPE,
        "response_type": "code",
        "v": API_VERSION,
    }
    return "https://oauth.vk.com/authorize?" + urllib.parse.urlencode(params)


def exchange_code(client_id, client_secret, code):
    r = requests.get("https://oauth.vk.com/access_token", params={
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }, timeout=30)
    return r.json()


GROUP_NAME_MAP = {
    239558545: "science",
    239858334: "forest",
    240220784: "interesting",
    239707751: "urbanistika",
    239469377: "repost",
}


if __name__ == "__main__":
    client_id = input("Enter client_id: ").strip()
    client_secret = input("Enter client_secret: ").strip()

    url = build_auth_url(client_id)
    print(f"\nOpen this URL in browser:\n\n{url}\n")
    print("After authorization, browser will redirect to blank.html with code in URL fragment.")
    print("Copy the code from URL (after #code=):\n")

    code = input("Enter code: ").strip()

    result = exchange_code(client_id, client_secret, code)

    if "error" in result:
        print(f"\nERROR: {result['error']}: {result.get('error_description', '')}")
        sys.exit(1)

    print("\n=== Tokens received ===\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    groups = result.get("groups", [])
    tokens = {}
    for g in groups:
        gid = g["group_id"]
        token = g["access_token"]
        name = GROUP_NAME_MAP.get(gid, f"unknown_{gid}")
        tokens[name] = {"group_id": gid, "token": token}
        print(f"\n{name} (group_id={gid}):")
        print(f"  token: {token[:40]}...")

    with open("vk_oauth_tokens.json", "w") as f:
        json.dump(tokens, f, indent=2)
    print(f"\nSaved to vk_oauth_tokens.json")

    print("\n=== Updating .env files ===")
    for name, info in tokens.items():
        env_path = f"channels/{name}/.env"
        try:
            with open(env_path) as f:
                content = f.read()
            import re
            content = re.sub(r"^VK_TOKEN=.*$", f"VK_TOKEN={info['token']}", content, flags=re.MULTILINE)
            with open(env_path, "w") as f:
                f.write(content)
            print(f"  {env_path} -> updated")
        except FileNotFoundError:
            print(f"  {env_path} -> NOT FOUND (skipped)")
