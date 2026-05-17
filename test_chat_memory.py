import tempfile
from pathlib import Path


def test_memory_key_prefers_chat_hash():
    from chat_memory import memory_key

    chat = {"chat": "示例群聊", "chat_hash": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d", "is_group": True}

    assert memory_key(chat) == "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d"


def test_memory_key_falls_back_to_stable_digest():
    from chat_memory import memory_key

    one = memory_key({"chat": "示例用户", "is_group": False})
    two = memory_key({"chat": "示例用户", "is_group": False})

    assert one == two
    assert one.startswith("chat_")


def test_store_loads_default_memory_when_missing():
    from chat_memory import ChatMemoryStore

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp))
        memory = store.load({"chat": "示例用户", "is_group": False})

    assert memory["chat"] == "示例用户"
    assert memory["is_group"] is False
    assert memory["summary"] == ""
    assert memory["recent_messages"] == []


def test_store_saves_and_reloads_memory():
    from chat_memory import ChatMemoryStore

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp))
        chat = {"chat": "示例用户", "chat_hash": "abc123", "is_group": False}
        memory = store.load(chat)
        memory["summary"] = "老朋友，常开玩笑。"
        memory["recent_messages"].append({"role": "user", "sender": "示例用户", "content": "你好", "time": "t"})
        store.save(chat, memory)

        reloaded = store.load(chat)

    assert reloaded["summary"] == "老朋友，常开玩笑。"
    assert reloaded["recent_messages"][0]["content"] == "你好"


def test_enrich_pending_adds_memory_to_each_chat():
    from chat_memory import ChatMemoryStore, enrich_pending_with_memory

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp))
        chat = {"chat": "示例用户", "chat_hash": "abc123", "is_group": False}
        memory = store.load(chat)
        memory["summary"] = "喜欢简短回复。"
        store.save(chat, memory)

        pending = {"chats": [{"chat": "示例用户", "chat_hash": "abc123", "is_group": False, "messages": []}]}
        enriched = enrich_pending_with_memory(pending, store)

    assert enriched["chats"][0]["memory"]["summary"] == "喜欢简短回复。"


def test_update_memory_appends_incoming_and_reply_then_trims():
    from chat_memory import ChatMemoryStore, update_memory_after_replies

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp), max_recent=3)
        pending = {
            "chats": [
                {
                    "chat": "示例用户",
                    "chat_hash": "abc123",
                    "is_group": False,
                    "messages": [
                        {"sender": "示例用户", "content": "第一句"},
                        {"sender": "示例用户", "content": "第二句"},
                    ],
                }
            ]
        }
        replies = [{"chat": "示例用户", "chat_hash": "abc123", "content": "回复", "skip": False}]

        update_memory_after_replies(pending, replies, store)
        memory = store.load({"chat": "示例用户", "chat_hash": "abc123", "is_group": False})

    assert [m["content"] for m in memory["recent_messages"]] == ["第一句", "第二句", "回复"]


if __name__ == "__main__":
    tests = [
        test_memory_key_prefers_chat_hash,
        test_memory_key_falls_back_to_stable_digest,
        test_store_loads_default_memory_when_missing,
        test_store_saves_and_reloads_memory,
        test_enrich_pending_adds_memory_to_each_chat,
        test_update_memory_appends_incoming_and_reply_then_trims,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
