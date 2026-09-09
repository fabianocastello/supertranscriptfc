#!/usr/bin/env python3
"""Generates a long-lived DROPBOX_REFRESH_TOKEN (no expiration) via the
Dropbox OAuth2 flow, and updates the project's .env automatically.

Unlike the App Console's "Generate access token" button (which gives a
token valid for only a few hours), this flow produces a refresh token: the
Dropbox SDK uses it together with the app key/secret to renew the access
token by itself on every call, so VOXEL FC can run unattended for
hours/days.

Usage:
    python scripts/dropbox_oauth.py
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from dotenv import dotenv_values

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_app_credentials() -> tuple[str, str]:
    values = dotenv_values(ENV_PATH)
    app_key = values.get("DROPBOX_APP_KEY")
    app_secret = values.get("DROPBOX_APP_SECRET")
    if not app_key or not app_secret:
        raise SystemExit(
            f"DROPBOX_APP_KEY/DROPBOX_APP_SECRET not found in {ENV_PATH}. "
            "Fill them in before running this script."
        )
    return app_key, app_secret


def build_authorize_url(app_key: str) -> str:
    params = {
        "client_id": app_key,
        "response_type": "code",
        "token_access_type": "offline",
    }
    return "https://www.dropbox.com/oauth2/authorize?" + urllib.parse.urlencode(params)


def exchange_code_for_tokens(code: str, app_key: str, app_secret: str) -> dict:
    data = urllib.parse.urlencode(
        {
            "code": code,
            "grant_type": "authorization_code",
            "client_id": app_key,
            "client_secret": app_secret,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.dropboxapi.com/oauth2/token", data=data, method="POST"
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def update_env_file(refresh_token: str) -> None:
    text = ENV_PATH.read_text(encoding="utf-8")
    if re.search(r"^DROPBOX_REFRESH_TOKEN=.*$", text, flags=re.MULTILINE):
        text = re.sub(
            r"^DROPBOX_REFRESH_TOKEN=.*$",
            f"DROPBOX_REFRESH_TOKEN={refresh_token}",
            text,
            flags=re.MULTILINE,
        )
    else:
        text = text.rstrip("\n") + f"\nDROPBOX_REFRESH_TOKEN={refresh_token}\n"
    ENV_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    app_key, app_secret = load_app_credentials()
    url = build_authorize_url(app_key)

    print("Open this URL, log in, and click Allow:")
    print(url)
    print()
    webbrowser.open(url)  # on a machine without a browser (SSH), this simply does nothing

    code = input("Paste the code shown by Dropbox after authorizing here: ").strip()
    tokens = exchange_code_for_tokens(code, app_key, app_secret)

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise SystemExit(f"API response without refresh_token: {tokens}")

    update_env_file(refresh_token)
    print()
    print(f"DROPBOX_REFRESH_TOKEN successfully updated in {ENV_PATH}")
    print("Scopes granted:", tokens.get("scope", "(not reported by the API)"))


if __name__ == "__main__":
    main()
