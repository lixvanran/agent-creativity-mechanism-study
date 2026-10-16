"""题库。题目由外部注入（文件或 --question），本模块不含任何「标准答案」。
题目的**判据**也由外部注入，且只用于事后扫描，不进任何提示词。"""
from __future__ import annotations
import json, os

DEFAULT_TOPIC_FILE = os.path.join(os.path.dirname(__file__), "data", "topics.json")


def load(path: str | None = None) -> list[dict]:
    return json.load(open(path or DEFAULT_TOPIC_FILE, encoding="utf-8"))
