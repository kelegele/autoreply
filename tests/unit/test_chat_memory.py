import _path  # noqa: F401

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

def test_default_store_keeps_latest_100_messages():
    from chat_memory import ChatMemoryStore

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp), summarize_fn=lambda summary, messages, chat: summary + " summarized")
        chat = {"chat": "示例用户", "chat_hash": "abc123", "is_group": False}
        memory = store.load(chat)
        memory["recent_messages"] = [
            {"role": "user", "sender": "示例用户", "content": f"消息{i}", "time": "t"}
            for i in range(105)
        ]

        store.save(chat, memory)
        reloaded = store.load(chat)

    assert len(reloaded["recent_messages"]) == 100
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

    assert reloaded["summary"] == "保留长期摘要"
    assert [m["content"] for m in reloaded["recent_messages"]] == ["DB 最新消息"]

def test_update_memory_indexes_daily_messages_by_user_and_chat():
    from chat_memory import ChatMemoryStore, update_memory

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp))
        chat = {"chat": "测试群", "chat_hash": "group123", "is_group": True}

        update_memory(
            chat,
            [
                {
                    "local_id": 1,
                    "sender": "示例用户",
                    "sender_wxid": "wxid_f",
                    "content": "今天我想让大模型记住聊天",
                    "timestamp": "2026-05-18 10:00:00",
                },
                {
                    "local_id": 2,
                    "sender": "纯粹",
                    "sender_wxid": "wxid_c",
                    "content": "论文查重还没过",
                    "timestamp": "2026-05-18 10:01:00",
                },
            ],
            store=store,
        )
        memory = store.load(chat)

    day = memory["daily"]["2026-05-18"]
    assert day["chat"] == "测试群"
    assert day["by_user"]["wxid_f"]["name"] == "示例用户"
    assert day["by_user"]["wxid_f"]["message_count"] == 1
    assert day["by_user"]["wxid_f"]["messages"][0]["content"] == "今天我想让大模型记住聊天"
    assert day["by_user"]["wxid_c"]["messages"][0]["content"] == "论文查重还没过"

def test_update_memory_indexes_global_user_daily_memory_across_chats():
    import json
    from chat_memory import ChatMemoryStore, update_memory

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp), user_memory_path=Path(tmp) / "user_memory.json")
        update_memory(
            {"chat": "群A", "chat_hash": "group_a", "is_group": True},
            [
                {
                    "local_id": 1,
                    "sender": "示例用户",
                    "sender_wxid": "wxid_f",
                    "content": "我在群A说了记忆",
                    "timestamp": "2026-05-18 10:00:00",
                }
            ],
            store=store,
        )
        update_memory(
            {"chat": "示例用户", "chat_hash": "private_f", "is_group": False},
            [
                {
                    "local_id": 2,
                    "sender": "示例用户",
                    "sender_wxid": "wxid_f",
                    "content": "我在私聊问了模型",
                    "timestamp": "2026-05-18 11:00:00",
                }
            ],
            store=store,
        )
        data = json.loads((Path(tmp) / "user_memory.json").read_text(encoding="utf-8"))

    user = data["daily"]["2026-05-18"]["by_user"]["wxid_f"]
    assert user["name"] == "示例用户"
    assert user["chats"]["group_a"]["messages"][0]["content"] == "我在群A说了记忆"
    assert user["chats"]["private_f"]["messages"][0]["content"] == "我在私聊问了模型"

def test_enrich_pending_adds_current_senders_global_daily_memory():
    from chat_memory import ChatMemoryStore, enrich_pending_with_memory, update_memory

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp), user_memory_path=Path(tmp) / "user_memory.json")
        update_memory(
            {"chat": "群A", "chat_hash": "group_a", "is_group": True},
            [
                {
                    "local_id": 1,
                    "sender": "示例用户",
                    "sender_wxid": "wxid_f",
                    "content": "我在群A说了记忆",
                    "timestamp": "2026-05-18 10:00:00",
                }
            ],
            store=store,
        )
        pending = {
            "chats": [
                {
                    "chat": "示例用户",
                    "chat_hash": "private_f",
                    "is_group": False,
                    "messages": [{"sender": "示例用户", "sender_wxid": "wxid_f", "content": "我今天说了什么？"}],
                }
            ]
        }
        enriched = enrich_pending_with_memory(pending, store)

    user_memory = enriched["chats"][0]["user_daily_memory"]["2026-05-18"]["by_user"]["wxid_f"]
    assert user_memory["chats"]["group_a"]["messages"][0]["content"] == "我在群A说了记忆"

def test_replace_recent_memory_preserves_long_term_and_updates_daily_index():
    from chat_memory import ChatMemoryStore, replace_recent_memory

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp))
        chat = {"chat": "示例用户", "chat_hash": "abc123", "is_group": False}
        memory = store.load(chat)
        memory["summary"] = "长期：示例用户关注记忆能力。"
        store.save(chat, memory)

        replace_recent_memory(
            chat,
            [
                {
                    "local_id": 10,
                    "sender": "示例用户",
                    "sender_wxid": "wxid_f",
                    "content": "今天问了记忆怎么改造",
                    "timestamp": "2026-05-18 12:00:00",
                }
            ],
            store=store,
        )
        reloaded = store.load(chat)

    assert reloaded["summary"] == "长期：示例用户关注记忆能力。"
    assert reloaded["daily"]["2026-05-18"]["by_user"]["wxid_f"]["messages"][0]["content"] == "今天问了记忆怎么改造"

def test_llm_summary_disables_console_logging():
    import reply_worker
    from chat_memory import summarize_memory_with_llm

    captured = {}
    original_call_llm = reply_worker.call_llm_with_usage
    original_load_llm_config = reply_worker.load_llm_config

    def fake_call_llm(prompt, config, log_func="not-none"):
        captured["log_func"] = log_func
        return reply_worker.LLMResult(
            content="摘要",
            usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            raw={},
        )

    try:
        reply_worker.call_llm_with_usage = fake_call_llm
        reply_worker.load_llm_config = lambda: object()

        result = summarize_memory_with_llm(
            "",
            [{"sender": "示例用户", "content": "你好", "time": "2026-05-18 02:00:00"}],
            {"chat": "示例用户", "is_group": False},
        )
    finally:
        reply_worker.call_llm_with_usage = original_call_llm
        reply_worker.load_llm_config = original_load_llm_config

    assert result == "摘要"
    assert captured["log_func"] is None

def test_llm_summary_records_system_token_usage():
    import json
    import tempfile
    from pathlib import Path

    import reply_worker
    import token_usage
    from chat_memory import summarize_memory_with_llm

    original_call_llm = reply_worker.call_llm_with_usage
    original_load_llm_config = reply_worker.load_llm_config
    original_usage_file = token_usage.DEFAULT_TOKEN_USAGE_FILE

    with tempfile.TemporaryDirectory() as tmp:
        token_usage.DEFAULT_TOKEN_USAGE_FILE = Path(tmp) / "token_usage.json"

        def fake_call_llm(prompt, config, log_func=None):
            return reply_worker.LLMResult(
                content="摘要",
                usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
                raw={},
            )

        try:
            reply_worker.call_llm_with_usage = fake_call_llm
            reply_worker.load_llm_config = lambda: type("Config", (), {"model": "deepseek-v4-flash"})()

            summarize_memory_with_llm(
                "",
                [{"sender": "示例用户", "content": "你好", "time": "2026-05-18 02:00:00"}],
                {"chat": "示例用户", "is_group": False},
            )
            data = json.loads(token_usage.DEFAULT_TOKEN_USAGE_FILE.read_text(encoding="utf-8"))
        finally:
            reply_worker.call_llm_with_usage = original_call_llm
            reply_worker.load_llm_config = original_load_llm_config
            token_usage.DEFAULT_TOKEN_USAGE_FILE = original_usage_file

    assert data["total"]["total_tokens"] == 5
    assert data["by_source"]["system.memory_summarize"]["total_tokens"] == 5

def test_summarizes_overflow_before_trimming():
    from chat_memory import ChatMemoryStore

    calls = []

    def fake_summarize(summary, messages, chat):
        calls.append((summary, [m["content"] for m in messages], chat["chat"]))
        return "旧摘要 + 前2条"

    with tempfile.TemporaryDirectory() as tmp:
        store = ChatMemoryStore(Path(tmp), max_recent=100, summarize_fn=fake_summarize)
        chat = {"chat": "示例用户", "chat_hash": "abc123", "is_group": False}
        memory = store.load(chat)
        memory["summary"] = "旧摘要"
        memory["recent_messages"] = [
            {"role": "user", "sender": "示例用户", "content": f"消息{i}", "time": "t"}
            for i in range(105)
        ]

        store.save(chat, memory)
        reloaded = store.load(chat)

    assert calls == [("旧摘要", ["消息0", "消息1", "消息2", "消息3", "消息4"], "示例用户")]
    assert reloaded["summary"] == "旧摘要 + 前2条"
    assert len(reloaded["recent_messages"]) == 100
    assert reloaded["recent_messages"][0]["content"] == "消息5"


if __name__ == "__main__":
    tests = [
        test_memory_key_prefers_chat_hash,
        test_memory_key_falls_back_to_stable_digest,
        test_store_loads_default_memory_when_missing,
        test_store_saves_and_reloads_memory,
        test_enrich_pending_adds_memory_to_each_chat,
        test_update_memory_appends_incoming_and_reply_then_trims,
        test_default_store_keeps_latest_100_messages,
        test_update_memory_records_skipped_chat_messages_without_reply,
        test_update_memory_records_self_messages_as_assistant,
        test_replace_recent_memory_uses_database_snapshot_instead_of_appending,
        test_update_memory_indexes_daily_messages_by_user_and_chat,
        test_update_memory_indexes_global_user_daily_memory_across_chats,
        test_enrich_pending_adds_current_senders_global_daily_memory,
        test_replace_recent_memory_preserves_long_term_and_updates_daily_index,
        test_llm_summary_disables_console_logging,
        test_llm_summary_records_system_token_usage,
        test_summarizes_overflow_before_trimming,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
