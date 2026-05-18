import _path  # noqa: F401

import json
import tempfile
from pathlib import Path


def test_on_done_backfills_chat_hash_from_pending_data():
    import reflect_wxchatbot_reply as reflect

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        old_reply_file = reflect.REPLY_FILE
        old_exchange_dir = reflect.EXCHANGE_DIR
        old_pending_data = reflect._pending_data
        old_pending_chats = reflect._pending_chats
        try:
            reflect.REPLY_FILE = tmp_path / "reply.json"
            reflect.EXCHANGE_DIR = tmp_path
            reflect._pending_data = {
                "chats": [
                    {
                        "chat": "测试群",
                        "chat_hash": "group123456789",
                        "is_group": True,
                        "messages": [{"sender": "示例用户", "content": "hello"}],
                    }
                ]
            }
            reflect._pending_chats = []

            reflect.on_done(
                json.dumps(
                    {
                        "replies": [
                            {
                                "chat": "测试群",
                                "content": "收到",
                                "is_group": True,
                                "sender": "",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            )

            replies = json.loads(reflect.REPLY_FILE.read_text(encoding="utf-8"))
        finally:
            reflect.REPLY_FILE = old_reply_file
            reflect.EXCHANGE_DIR = old_exchange_dir
            reflect._pending_data = old_pending_data
            reflect._pending_chats = old_pending_chats

    assert replies[0]["chat_hash"] == "group123456789"


if __name__ == "__main__":
    tests = [
        test_on_done_backfills_chat_hash_from_pending_data,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
