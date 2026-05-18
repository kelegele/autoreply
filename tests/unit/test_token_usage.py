import _path  # noqa: F401

import json
import tempfile
from pathlib import Path


def test_record_single_chat_usage_exact():
    from token_usage import record_token_usage

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "token_usage.json"
        pending = {
            "chats": [
                {
                    "chat": "示例用户",
                    "chat_hash": "abc123",
                    "is_group": False,
                    "messages": [{"sender": "示例用户", "content": "你好"}],
                }
            ]
        }
        usage = {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}

        record_token_usage(path, usage, pending=pending, model="deepseek-v4-flash")
        data = json.loads(path.read_text(encoding="utf-8"))

    assert data["total"]["requests"] == 1
    assert data["total"]["prompt_tokens"] == 10
    assert data["total"]["completion_tokens"] == 4
    assert data["total"]["total_tokens"] == 14
    assert data["by_chat"]["abc123"]["allocation"] == "exact"
    assert data["by_chat"]["abc123"]["total_tokens"] == 14
    assert data["events"][0]["chats"][0]["allocated_total_tokens"] == 14


def test_record_multi_chat_usage_estimated_by_message_size():
    from token_usage import record_token_usage

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "token_usage.json"
        pending = {
            "chats": [
                {
                    "chat": "短",
                    "chat_hash": "short",
                    "is_group": False,
                    "messages": [{"sender": "A", "content": "1"}],
                },
                {
                    "chat": "长",
                    "chat_hash": "long",
                    "is_group": False,
                    "messages": [{"sender": "B", "content": "123456789"}],
                },
            ]
        }
        usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}

        record_token_usage(path, usage, pending=pending, model="deepseek-v4-flash")
        data = json.loads(path.read_text(encoding="utf-8"))

    assert data["total"]["total_tokens"] == 150
    assert data["by_chat"]["short"]["allocation"] == "estimated"
    assert data["by_chat"]["long"]["allocation"] == "estimated"
    assert data["by_chat"]["long"]["total_tokens"] > data["by_chat"]["short"]["total_tokens"]
    assert data["by_chat"]["long"]["total_tokens"] + data["by_chat"]["short"]["total_tokens"] == 150


def test_record_system_usage_separately_from_chats():
    from token_usage import record_token_usage

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "token_usage.json"
        usage = {
            "prompt_tokens": 20,
            "completion_tokens": 5,
            "total_tokens": 25,
            "completion_tokens_details": {"reasoning_tokens": 3},
        }

        record_token_usage(path, usage, source="system.memory_summarize", model="deepseek-v4-flash")
        data = json.loads(path.read_text(encoding="utf-8"))

    assert data["total"]["total_tokens"] == 25
    assert data["total"]["reasoning_tokens"] == 3
    assert data["by_chat"] == {}
    assert data["by_source"]["system.memory_summarize"]["total_tokens"] == 25


if __name__ == "__main__":
    tests = [
        test_record_single_chat_usage_exact,
        test_record_multi_chat_usage_estimated_by_message_size,
        test_record_system_usage_separately_from_chats,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
