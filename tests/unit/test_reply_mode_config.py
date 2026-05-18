import _path  # noqa: F401

def test_format_messages_includes_reply_mode_from_config():
    from bot import format_messages_for_ga

    raw_messages = [
        {
            "sender": "示例用户",
            "sender_wxid": "wxid_f",
            "content": "你好",
            "chat_name": "示例用户",
            "chat_hash": "abc123",
            "chat_type": "private",
            "is_group": False,
            "is_self": False,
        }
    ]

    data = format_messages_for_ga(raw_messages, {"persona": "测试人格", "reply_mode": "llm_chat"})

    assert data["reply_mode"] == "llm_chat"


def test_format_messages_defaults_reply_mode_to_persona():
    from bot import format_messages_for_ga

    raw_messages = [
        {
            "sender": "示例用户",
            "content": "你好",
            "chat_name": "示例用户",
            "chat_hash": "abc123",
            "is_group": False,
            "is_self": False,
        }
    ]

    data = format_messages_for_ga(raw_messages, {"persona": "测试人格"})

    assert data["reply_mode"] == "persona"

def test_poll_pending_preserves_reply_mode():
    import bot

    captured = {}

    class DbConfig:
        msg_db_path = "msg.db"
        msg_key_bytes = b"key"
        my_wxid = "wxid_me"
        my_display_name = "Flerken"

    class Exchange:
        def write_pending(self, data):
            captured["pending"] = data

    class Logger:
        def info(self, message):
            pass

        def debug(self, message):
            pass

        def error(self, message):
            raise AssertionError(message)

    class PollState:
        last_seq_per_chat = {}
        seen_server_ids = set()

        def save(self):
            pass

    original_query = bot.query_new_messages
    original_update = None
    try:
        import chat_memory

        original_update = chat_memory.update_memory
        chat_memory.update_memory = lambda *args, **kwargs: None
        bot.query_new_messages = lambda *args, **kwargs: [
            {
                "chat_name": "示例用户",
                "chat_hash": "abc123",
                "chat_type": "private",
                "is_group": False,
                "sender": "示例用户",
                "sender_wxid": "wxid_f",
                "content": "帮我查一下",
                "timestamp": "2026-05-18 10:00:00",
                "is_self": False,
                "chat_already_replied": False,
            }
        ]

        instance = bot.WxChatBot.__new__(bot.WxChatBot)
        instance.config = {"persona": "测试人格", "reply_mode": "llm_chat"}
        instance.logger = Logger()
        instance.db_config = DbConfig()
        instance.poll_state = PollState()
        instance.exchange = Exchange()
        instance.stats = {"polls": 0, "messages_found": 0, "replies_sent": 0, "start_time": None}
        instance.uname2display = {}

        instance._poll_once()
    finally:
        bot.query_new_messages = original_query
        if original_update is not None:
            chat_memory.update_memory = original_update

    assert captured["pending"]["reply_mode"] == "llm_chat"


if __name__ == "__main__":
    tests = [
        test_format_messages_includes_reply_mode_from_config,
        test_format_messages_defaults_reply_mode_to_persona,
        test_poll_pending_preserves_reply_mode,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
