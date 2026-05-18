import _path  # noqa: F401

def test_format_messages_preserves_message_timestamp():
    from bot import format_messages_for_ga

    raw = [
        {
            "sender": "示例用户",
            "sender_wxid": "wxid_1",
            "content": "想你了",
            "is_at": False,
            "chat_name": "示例用户",
            "chat_hash": "abc123",
            "chat_type": "private",
            "timestamp": "2026-05-17 22:09:47",
            "is_group": False,
            "is_self": False,
            "chat_already_replied": False,
        }
    ]

    data = format_messages_for_ga(raw, {"persona": "p"})

    assert data["chats"][0]["messages"][0]["time"] == "2026-05-17 22:09:47"


def test_prompt_includes_time_context_and_forbids_time_prefixes():
    import reflect_wxchatbot_reply as reflect

    data = {
        "persona": "p",
        "chats": [
            {
                "chat": "示例用户",
                "is_group": False,
                "memory": {
                    "recent_messages": [
                        {"role": "user", "sender": "示例用户", "content": "昨天呢", "time": "2026-05-16 09:00:00"},
                        {"role": "assistant", "sender": "bot", "content": "哼", "time": "2026-05-16 09:01:00"},
                    ]
                },
                "messages": [
                    {"sender": "示例用户", "content": "现在回我", "time": "2026-05-17 22:09:47"}
                ],
            }
        ],
    }

    prompt = reflect.build_prompt(data)

    assert "2026-05-16 09:00:00 [示例用户]: 昨天呢" in prompt
    assert "2026-05-17 22:09:47 [示例用户]: 现在回我" in prompt
    assert "感知消息间隔" in prompt
    assert "不要在回复正文中带时间格式" in prompt


if __name__ == "__main__":
    tests = [
        test_format_messages_preserves_message_timestamp,
        test_prompt_includes_time_context_and_forbids_time_prefixes,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
