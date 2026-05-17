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
        store = ChatMemoryStore(Path(tmp), max_recent=3, summarize_fn=lambda summary, messages, chat: summary)
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

def test_default_store_keeps_latest_50_messages():
    from chat_memory import ChatMemoryStore

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp), summarize_fn=lambda summary, messages, chat: summary + " summarized")
        chat = {"chat": "示例用户", "chat_hash": "abc123", "is_group": False}
        memory = store.load(chat)
        memory["recent_messages"] = [
            {"role": "user", "sender": "示例用户", "content": f"消息{i}", "time": "t"}
            for i in range(55)
        ]

        store.save(chat, memory)
        reloaded = store.load(chat)

    assert len(reloaded["recent_messages"]) == 50
    assert reloaded["recent_messages"][0]["content"] == "消息5"
    assert reloaded["summary"] == "summarized"

def test_update_memory_records_skipped_chat_messages_without_reply():
    from chat_memory import ChatMemoryStore, update_memory

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp))
        update_memory(
            {
                "chat": "示例群聊",
                "chat_hash": "group123",
                "is_group": True,
            },
            [
                {
                    "sender": "Kat",
                    "sender_wxid": "wxid_kat",
                    "content": "不用回复但要记住",
                    "timestamp": "2026-05-18 01:02:03",
                }
            ],
            store=store,
        )

        memory = store.load({"chat": "示例群聊", "chat_hash": "group123", "is_group": True})

    assert memory["recent_messages"] == [
        {
            "role": "user",
            "sender": "Kat",
            "sender_wxid": "wxid_kat",
            "content": "不用回复但要记住",
            "time": "2026-05-18 01:02:03",
        }
    ]

def test_update_memory_records_self_messages_as_assistant():
    from chat_memory import ChatMemoryStore, update_memory

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp))
        update_memory(
            {"chat": "示例用户", "chat_hash": "abc123", "is_group": False},
            [
                {
                    "sender": "我",
                    "content": "之前我已经回过了",
                    "timestamp": "2026-05-18 01:02:03",
                    "is_self": True,
                }
            ],
            store=store,
        )
        memory = store.load({"chat": "示例用户", "chat_hash": "abc123", "is_group": False})

    assert memory["recent_messages"][0]["role"] == "assistant"
    assert memory["recent_messages"][0]["sender"] == "bot"

def test_replace_recent_memory_uses_database_snapshot_instead_of_appending():
    from chat_memory import ChatMemoryStore, replace_recent_memory

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp))
        chat = {"chat": "示例用户", "chat_hash": "abc123", "is_group": False}
        memory = store.load(chat)
        memory["summary"] = "保留长期摘要"
        memory["recent_messages"] = [
            {"role": "user", "sender": "示例用户", "content": "旧缓存消息", "time": "old"}
        ]
        store.save(chat, memory)

        replace_recent_memory(
            chat,
            [
                {
                    "sender": "示例用户",
                    "content": "DB 最新消息",
                    "timestamp": "2026-05-18 02:00:00",
                }
            ],
            store=store,
        )
        reloaded = store.load(chat)

    assert reloaded["summary"] == ""
    assert [m["content"] for m in reloaded["recent_messages"]] == ["DB 最新消息"]

def test_llm_summary_disables_console_logging():
    import reply_worker
    from chat_memory import summarize_memory_with_llm

    captured = {}
    original_call_llm = reply_worker.call_llm
    original_load_llm_config = reply_worker.load_llm_config

    def fake_call_llm(prompt, config, log_func="not-none"):
        captured["log_func"] = log_func
        return "摘要"

    try:
        reply_worker.call_llm = fake_call_llm
        reply_worker.load_llm_config = lambda: object()

        result = summarize_memory_with_llm(
            "",
            [{"sender": "示例用户", "content": "你好", "time": "2026-05-18 02:00:00"}],
            {"chat": "示例用户", "is_group": False},
        )
    finally:
        reply_worker.call_llm = original_call_llm
        reply_worker.load_llm_config = original_load_llm_config

    assert result == "摘要"
    assert captured["log_func"] is None

def test_summarizes_overflow_before_trimming():
    from chat_memory import ChatMemoryStore

    calls = []

    def fake_summarize(summary, messages, chat):
        calls.append((summary, [m["content"] for m in messages], chat["chat"]))
        return "旧摘要 + 前2条"

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp), max_recent=50, summarize_fn=fake_summarize)
        chat = {"chat": "示例用户", "chat_hash": "abc123", "is_group": False}
        memory = store.load(chat)
        memory["summary"] = "旧摘要"
        memory["recent_messages"] = [
            {"role": "user", "sender": "示例用户", "content": f"消息{i}", "time": "t"}
            for i in range(52)
        ]

        store.save(chat, memory)
        reloaded = store.load(chat)

    assert calls == [("旧摘要", ["消息0", "消息1"], "示例用户")]
    assert reloaded["summary"] == "旧摘要 + 前2条"
    assert len(reloaded["recent_messages"]) == 50
    assert reloaded["recent_messages"][0]["content"] == "消息2"


if __name__ == "__main__":
    tests = [
        test_memory_key_prefers_chat_hash,
        test_memory_key_falls_back_to_stable_digest,
        test_store_loads_default_memory_when_missing,
        test_store_saves_and_reloads_memory,
        test_enrich_pending_adds_memory_to_each_chat,
        test_update_memory_appends_incoming_and_reply_then_trims,
        test_default_store_keeps_latest_50_messages,
        test_update_memory_records_skipped_chat_messages_without_reply,
        test_update_memory_records_self_messages_as_assistant,
        test_replace_recent_memory_uses_database_snapshot_instead_of_appending,
        test_llm_summary_disables_console_logging,
        test_summarizes_overflow_before_trimming,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
