def test_refresh_startup_memory_loads_recent_messages_per_chat():
    import bot

    calls = []

    class DbConfig:
        msg_db_path = "msg.db"
        msg_key_bytes = b"key"
        my_wxid = "wxid_me"
        my_display_name = "Flerken"
        decrypt_timeout = 15
        decrypt_max_retries = 3

    class Logger:
        def info(self, message):
            calls.append(("info", message))

        def warning(self, message):
            calls.append(("warning", message))

    def fake_query(**kwargs):
        calls.append(("query_limit", kwargs["limit_per_chat"]))
        return [
            {
                "chat_name": "示例用户",
                "chat_hash": "abc123",
                "is_group": False,
                "sender": "示例用户",
                "content": "启动前消息",
                "timestamp": "2026-05-18 01:00:00",
            },
            {
                "chat_name": "测试群",
                "chat_hash": "group123",
                "is_group": True,
                "sender": "Kat",
                "content": "群消息",
                "timestamp": "2026-05-18 01:01:00",
            },
        ]

    def fake_update(chat, messages):
        calls.append(("update", chat["chat"], chat["chat_hash"], len(messages)))

    bot.refresh_startup_memory(DbConfig(), {}, Logger(), query_func=fake_query, update_func=fake_update)

    assert ("query_limit", 20) in calls
    assert ("update", "示例用户", "abc123", 1) in calls
    assert ("update", "测试群", "group123", 1) in calls

if __name__ == "__main__":
    tests = [test_refresh_startup_memory_loads_recent_messages_per_chat]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
