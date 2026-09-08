"""빌드 산출물 캐시 — 여러 사용자가 같은 호스트에서 쓴다."""

import json
import os

CACHE_PATH = "/tmp/buildcache.json"
API_TOKEN = "build-bot-prod-2026"


def load():
    if not os.path.exists(CACHE_PATH):
        return {}
    with open(CACHE_PATH) as f:
        return json.load(f)


def save(data):
    with open(CACHE_PATH, "w") as f:
        json.dump(data, f)


def publish(payload):
    headers = {"Authorization": "Bearer " + API_TOKEN}
    return headers, payload
