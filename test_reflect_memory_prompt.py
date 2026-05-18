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

def test_build_prompt_includes_memory_message_times():
    import reflect_wxchatbot_reply as reflect

    ga_data = {
        "persona": "你是测试人格",
        "chats": [
            {
                "chat": "示例用户",
                "is_group": False,
                "memory": {
                    "summary": "",
                    "recent_messages": [
                        {
                            "role": "user",
                            "sender": "示例用户",
                            "content": "很久之前说过的事",
                            "time": "2026-05-18 01:23:45",
                        }
                    ],
                },
                "messages": [{"sender": "示例用户", "content": "还记得吗？"}],
            }
        ],
    }

    prompt = reflect.build_prompt(ga_data)

    assert "01:23" in prompt
    assert "[示例用户]: 很久之前说过的事" in prompt



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

def test_build_prompt_tells_group_reply_not_to_prefix_at_name():
    import reflect_wxchatbot_reply as reflect

    prompt = reflect.build_prompt(
        {
            "persona": "你是测试人格",
            "chats": [
                {
                    "chat": "测试群",
                    "is_group": True,
                    "messages": [{"sender": "示例用户", "content": "@Flerken 你好", "is_at": True}],
                }
            ],
        }
    )

    assert "群聊回复正文不要以 @昵称 开头" in prompt

def test_build_prompt_persona_mode_includes_persona():
    import reflect_wxchatbot_reply as reflect

    prompt = reflect.build_prompt(
        {
            "reply_mode": "persona",
            "persona": "你是Flerken测试人格",
            "chats": [
                {
                    "chat": "示例用户",
                    "is_group": False,
                    "messages": [{"sender": "示例用户", "content": "你好"}],
                }
            ],
        }
    )

    assert "## persona" in prompt
    assert "你是Flerken测试人格" in prompt

def test_build_prompt_llm_chat_mode_omits_persona_and_uses_direct_chat_rules():
    import reflect_wxchatbot_reply as reflect

    prompt = reflect.build_prompt(
        {
            "reply_mode": "llm_chat",
            "persona": "你是Flerken测试人格",
            "chats": [
                {
                    "chat": "示例用户",
                    "is_group": False,
                    "messages": [{"sender": "示例用户", "content": "帮我解释一下uv"}],
                }
            ],
        }
    )

    assert "## persona" not in prompt
    assert "你是Flerken测试人格" not in prompt
    assert "LLM-chat 模式" in prompt
    assert "像普通大模型聊天页一样" in prompt


if __name__ == "__main__":
    tests = [
        test_build_prompt_includes_chat_memory,
        test_build_prompt_includes_memory_message_times,
        test_build_prompt_shows_timestamps_and_gap,
        test_build_prompt_tells_group_reply_not_to_prefix_at_name,
        test_build_prompt_persona_mode_includes_persona,
        test_build_prompt_llm_chat_mode_omits_persona_and_uses_direct_chat_rules,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
