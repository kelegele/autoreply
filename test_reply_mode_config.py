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


if __name__ == "__main__":
    tests = [
        test_format_messages_includes_reply_mode_from_config,
        test_format_messages_defaults_reply_mode_to_persona,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
