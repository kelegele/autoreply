def test_build_prompt_includes_chat_memory():
    import reflect_wxchatbot_reply as reflect

    ga_data = {
        "persona": "你是测试人格",
        "chats": [
            {
                "chat": "示例用户",
                "is_group": False,
                "memory": {
                    "summary": "这是老朋友，喜欢简短玩笑。",
                    "recent_messages": [
                        {"role": "user", "sender": "示例用户", "content": "昨天说的猫粮还记得吗"},
                        {"role": "assistant", "sender": "bot", "content": "记得，别催啦"},
                    ],
                },
                "messages": [{"sender": "示例用户", "content": "那今天呢？"}],
            }
        ],
    }

    prompt = reflect.build_prompt(ga_data)

    assert "## 会话记忆" in prompt
    assert "这是老朋友，喜欢简短玩笑。" in prompt
    assert "[示例用户]: 昨天说的猫粮还记得吗" in prompt
    assert "[bot]: 记得，别催啦" in prompt
    assert "[示例用户]: 那今天呢？" in prompt



def test_build_prompt_shows_timestamps_and_gap():
    import reflect_wxchatbot_reply as reflect

    ga_data = {
        "persona": "你是测试人格",
        "chats": [
            {
                "chat": "测试群",
                "is_group": True,
                "messages": [
                    {"sender": "Alice", "content": "早上好", "is_at": False,
                     "timestamp": "2025-05-17 08:00:00"},
                    {"sender": "Bob", "content": "有人在吗", "is_at": True,
                     "timestamp": "2025-05-17 10:05:00"},
                ],
            }
        ],
    }

    prompt = reflect.build_prompt(ga_data)

    # Check HH:MM timestamps appear
    assert "08:00" in prompt, f"Expected 08:00 timestamp, got: {prompt}"
    assert "10:05" in prompt, f"Expected 10:05 timestamp, got: {prompt}"

    # Check gap annotation (2 hours between messages)
    assert "2 小时" in prompt, f"Expected gap annotation, got: {prompt}"

    # Check the rule about not outputting time formats
    assert "不要包含时间、日期、时间戳" in prompt


if __name__ == "__main__":
    tests = [test_build_prompt_includes_chat_memory, test_build_prompt_shows_timestamps_and_gap]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
