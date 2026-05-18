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
        db_dir = "db"
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


def test_plain_group_message_without_at_does_not_call_llm_before_interjection_threshold():
    import bot

    captured = {}

    class DbConfig:
        db_dir = "db"
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

        def warning(self, message):
            pass

        def error(self, message):
            raise AssertionError(message)

    class PollState:
        last_seq_per_chat = {}
        seen_server_ids = set()

        def save(self):
            pass

    class FakeStore:
        def load(self, chat):
            return {
                "recent_messages": [
                    {"role": "assistant", "time": "2026-05-18 10:00:00", "content": "上一条回复"},
                    {"role": "user", "time": "2026-05-18 10:01:00", "content": "消息"},
                ]
            }

    original_query = bot.query_new_messages
    original_store = None
    original_update = None
    try:
        import chat_memory

        original_store = chat_memory.ChatMemoryStore
        original_update = chat_memory.update_memory
        chat_memory.ChatMemoryStore = FakeStore
        chat_memory.update_memory = lambda *args, **kwargs: None
        bot.query_new_messages = lambda *args, **kwargs: [
            {
                "chat_name": "测试群",
                "chat_hash": "group123456789",
                "chat_type": "group",
                "is_group": True,
                "sender": "示例用户",
                "sender_wxid": "wxid_f",
                "content": "没人@但群里很活跃",
                "timestamp": "2026-05-18 10:10:00",
                "is_at": False,
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
        if original_store is not None:
            chat_memory.ChatMemoryStore = original_store
        if original_update is not None:
            chat_memory.update_memory = original_update

    assert "pending" not in captured

def test_random_interjection_forces_group_pending_without_at_after_threshold():
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

        def warning(self, message):
            pass

        def error(self, message):
            raise AssertionError(message)

    class PollState:
        last_seq_per_chat = {}
        seen_server_ids = set()

        def save(self):
            pass

    class FakeStore:
        def load(self, chat):
            return {
                "recent_messages": [
                    {"role": "assistant", "time": "2026-05-18 10:00:00", "content": "上一条回复"},
                    *[
                        {"role": "user", "time": f"2026-05-18 10:{idx + 1:02d}:00", "content": f"消息{idx}"}
                        for idx in range(9)
                    ],
                ]
            }

    original_query = bot.query_new_messages
    original_store = None
    original_update = None
    try:
        import chat_memory

        original_store = chat_memory.ChatMemoryStore
        original_update = chat_memory.update_memory
        chat_memory.ChatMemoryStore = FakeStore
        chat_memory.update_memory = lambda *args, **kwargs: None
        bot.query_new_messages = lambda *args, **kwargs: [
            {
                "chat_name": "测试群",
                "chat_hash": "group123456789",
                "chat_type": "group",
                "is_group": True,
                "sender": "示例用户",
                "sender_wxid": "wxid_f",
                "content": "没人@但群里很活跃",
                "timestamp": "2026-05-18 10:10:00",
                "is_at": False,
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
        if original_store is not None:
            chat_memory.ChatMemoryStore = original_store
        if original_update is not None:
            chat_memory.update_memory = original_update

    assert captured["pending"]["chats"][0]["chat"] == "测试群"
    assert captured["pending"]["chats"][0]["needs_reply"] is True

def test_startup_sweep_does_not_pending_group_message_at_someone_else():
    import bot

    captured = {}

    class DbConfig:
        db_dir = "db"
        msg_db_path = "msg.db"
        msg_key_bytes = b"key"
        my_wxid = "wxid_me"
        my_display_name = "Flerken"

    class Exchange:
        exchange_dir = None

        def write_pending(self, data):
            captured["pending"] = data

    class Logger:
        def info(self, message):
            pass

        def debug(self, message):
            pass

        def warning(self, message):
            pass

        def error(self, message):
            raise AssertionError(message)

    original_query_recent = bot.query_recent_messages
    original_find = bot.find_wechat_window
    original_refresh = bot.refresh_startup_memory
    original_status = bot.CONSOLE_STATUS
    try:
        bot.query_recent_messages = lambda *args, **kwargs: [
            {
                "chat_name": "测试群",
                "chat_hash": "group123456789",
                "chat_type": "group",
                "is_group": True,
                "sender": "霜序廿七",
                "sender_wxid": "wxid_other",
                "content": "@Kat",
                "timestamp": "2026-05-18 10:10:00",
                "is_at": False,
                "is_self": False,
            }
        ]
        bot.find_wechat_window = lambda: 123
        bot.refresh_startup_memory = lambda *args, **kwargs: 0

        class StopStatus:
            def update(self, message):
                raise KeyboardInterrupt()

            def finish(self):
                pass

        bot.CONSOLE_STATUS = StopStatus()

        instance = bot.WxChatBot.__new__(bot.WxChatBot)
        instance.config = {"persona": "测试人格", "reply_mode": "llm_chat", "mode": "blacklist", "exchange_dir": "exchange"}
        instance.logger = Logger()
        instance.db_config = DbConfig()
        instance.exchange = Exchange()
        instance.poll_interval = 1
        instance.stats = {"polls": 0, "messages_found": 0, "replies_sent": 0, "start_time": None}
        instance.uname2display = {}

        instance.run()
    finally:
        bot.query_recent_messages = original_query_recent
        bot.find_wechat_window = original_find
        bot.refresh_startup_memory = original_refresh
        bot.CONSOLE_STATUS = original_status

    assert "pending" not in captured

if __name__ == "__main__":
    tests = [
        test_format_messages_includes_reply_mode_from_config,
        test_format_messages_defaults_reply_mode_to_persona,
        test_poll_pending_preserves_reply_mode,
        test_plain_group_message_without_at_does_not_call_llm_before_interjection_threshold,
        test_random_interjection_forces_group_pending_without_at_after_threshold,
        test_startup_sweep_does_not_pending_group_message_at_someone_else,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
