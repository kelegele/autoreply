import _path  # noqa: F401

def test_build_prompt_includes_chat_memory():
    import reflect_wxchatbot_reply as reflect

    ga_data = {
        "persona": "你是测试人格",
        "reply_mode": "persona",
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

def test_build_prompt_includes_structured_daily_user_memory():
    import reflect_wxchatbot_reply as reflect

    ga_data = {
        "persona": "你是测试人格",
        "reply_mode": "persona",
        "chats": [
            {
                "chat": "测试群",
                "is_group": True,
                "memory": {
                    "summary": "长期：示例用户关注机器人记忆。",
                    "daily": {
                        "2026-05-18": {
                            "chat": "测试群",
                            "by_user": {
                                "wxid_f": {
                                    "name": "示例用户",
                                    "messages": [
                                        {
                                            "time": "2026-05-18 10:00:00",
                                            "content": "今天我问了大模型记忆怎么改造",
                                        }
                                    ],
                                    "message_count": 1,
                                }
                            },
                        }
                    },
                    "recent_messages": [],
                },
                "messages": [{"sender": "示例用户", "content": "我今天说了什么？"}],
            }
        ],
    }

    prompt = reflect.build_prompt(ga_data)

    assert "长期记忆摘要" in prompt
    assert "今日结构化记忆" in prompt
    assert "示例用户" in prompt
    assert "今天我问了大模型记忆怎么改造" in prompt

def test_build_prompt_includes_cross_chat_user_daily_memory():
    import reflect_wxchatbot_reply as reflect

    ga_data = {
        "persona": "你是测试人格",
        "chats": [
            {
                "chat": "示例用户",
                "is_group": False,
                "user_daily_memory": {
                    "2026-05-18": {
                        "by_user": {
                            "wxid_f": {
                                "name": "示例用户",
                                "chats": {
                                    "group_a": {
                                        "chat": "群A",
                                        "messages": [
                                            {
                                                "time": "2026-05-18 10:00:00",
                                                "content": "我在群A说了记忆",
                                            }
                                        ],
                                    }
                                },
                            }
                        }
                    }
                },
                "messages": [{"sender": "示例用户", "sender_wxid": "wxid_f", "content": "我今天说了什么？"}],
            }
        ],
    }

    prompt = reflect.build_prompt(ga_data)

    assert "当前用户今日跨会话记忆" in prompt
    assert "群A" in prompt
    assert "我在群A说了记忆" in prompt

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
        "reply_mode": "persona",
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

def test_build_prompt_tells_persona_mode_to_reply_per_mention():
    import reflect_wxchatbot_reply as reflect

    prompt = reflect.build_prompt(
        {
            "reply_mode": "persona",
            "persona": "你是测试人格",
            "chats": [
                {
                    "chat": "测试群",
                    "is_group": True,
                    "messages": [
                        {"sender": "示例用户", "content": "@Flerken 广州天气", "is_at": True},
                        {"sender": "蕉太", "content": "@Flerken 泉州天气", "is_at": True},
                    ],
                }
            ],
        }
    )

    assert "逐条输出 reply" in prompt
    assert "chat 可以相同" in prompt
    assert "sender 必须分别对应原提问者" in prompt

def test_build_prompt_tells_llm_chat_mode_to_reply_per_mention():
    import reflect_wxchatbot_reply as reflect

    prompt = reflect.build_prompt(
        {
            "reply_mode": "llm_chat",
            "chats": [
                {
                    "chat": "测试群",
                    "is_group": True,
                    "messages": [
                        {"sender": "示例用户", "content": "@Flerken 广州天气", "is_at": True},
                        {"sender": "蕉太", "content": "@Flerken 泉州天气", "is_at": True},
                    ],
                }
            ],
        }
    )

    assert "逐条输出 reply" in prompt
    assert "chat 可以相同" in prompt
    assert "sender 必须分别对应原提问者" in prompt

def test_build_prompt_marks_random_interjection_as_proactive_task():
    import reflect_wxchatbot_reply as reflect

    prompt = reflect.build_prompt(
        {
            "reply_mode": "llm_chat",
            "chats": [
                {
                    "chat": "测试群",
                    "is_group": True,
                    "reply_reason": "随机插话",
                    "messages": [{"sender": "霜序廿七", "content": "@Kat", "is_at": False}],
                }
            ],
        }
    )

    assert "主动随机插话任务" in prompt
    assert "当前消息没有 @你 或 @了别人，也必须完成这次插话" in prompt
    assert "sender 设为空字符串" in prompt

def test_build_prompt_does_not_expose_skip_decision_to_model():
    import reflect_wxchatbot_reply as reflect

    prompt = reflect.build_prompt(
        {
            "reply_mode": "llm_chat",
            "chats": [
                {
                    "chat": "测试群",
                    "is_group": True,
                    "reply_reason": "随机插话",
                    "messages": [{"sender": "霜序廿七", "content": "@Kat", "is_at": False}],
                }
            ],
        }
    )

    assert "skip" not in prompt.lower()
    assert "不回复" not in prompt

def test_build_prompt_sanitizes_garbled_current_message_for_model():
    import reflect_wxchatbot_reply as reflect

    garbled = "(�/�`7\u0000=\t\u0000D\u0011wxid_demo1:\n@Flerken 写一个 Python 函数\u0005\u0000m\u0004�\u001d�b�N"

    prompt = reflect.build_prompt(
        {
            "reply_mode": "llm_chat",
            "chats": [
                {
                    "chat": "测试群",
                    "is_group": True,
                    "messages": [{"sender": "示例用户", "content": garbled, "is_at": True}],
                }
            ],
        }
    )

    assert "@Flerken 写一个 Python 函数" in prompt
    assert "\x00" not in prompt
    assert "�" not in prompt

def test_output_format_requests_json_object_replies():
    import reflect_wxchatbot_reply as reflect

    prompt = reflect.build_prompt(
        {
            "persona": "你是测试人格",
            "chats": [
                {
                    "chat": "示例用户",
                    "is_group": False,
                    "messages": [{"sender": "示例用户", "content": "你好"}],
                }
            ],
        }
    )

    assert '"replies"' in prompt
    assert '{"replies": [' in prompt

def test_extract_replies_accepts_json_object_replies():
    import reflect_wxchatbot_reply as reflect

    replies = reflect._extract_replies(
        '{"replies":[{"chat":"示例用户","content":"好","is_group":false,"sender":"示例用户","skip":false}]}'
    )

    assert replies == [{"chat": "示例用户", "content": "好", "is_group": False, "sender": "示例用户", "skip": False}]

def test_extract_replies_accepts_fenced_json_object_replies():
    import reflect_wxchatbot_reply as reflect

    replies = reflect._extract_replies(
        '```json\n{"replies":[{"chat":"示例用户","content":"好","skip":false}]}\n```'
    )

    assert replies == [{"chat": "示例用户", "content": "好", "skip": False}]

def test_extract_replies_keeps_legacy_array_compatibility():
    import reflect_wxchatbot_reply as reflect

    replies = reflect._extract_replies('[{"chat":"示例用户","content":"好","skip":false}]')

    assert replies == [{"chat": "示例用户", "content": "好", "skip": False}]

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

def test_build_messages_persona_mode_splits_system_and_user():
    import reflect_wxchatbot_reply as reflect

    messages = reflect.build_messages(
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

    assert [m["role"] for m in messages] == ["system", "user"]
    assert "## persona" in messages[0]["content"]
    assert "你是Flerken测试人格" in messages[0]["content"]
    assert "## 收到的消息" in messages[1]["content"]
    assert "[示例用户]: 你好" in messages[1]["content"]

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

def test_build_prompt_llm_chat_mode_preserves_model_capability():
    import reflect_wxchatbot_reply as reflect

    prompt = reflect.build_prompt(
        {
            "reply_mode": "llm_chat",
            "persona": "不应该出现",
            "chats": [
                {
                    "chat": "示例用户",
                    "is_group": False,
                    "messages": [{"sender": "示例用户", "content": "写一个 Python 函数并解释思路"}],
                }
            ],
        }
    )

    assert "不要为了像微信短回复而牺牲正确性和完整性" in prompt
    assert "可以使用分步骤、代码块、列表" in prompt
    assert "content 字段里放最终要发出的完整回答" in prompt

def test_build_prompt_llm_chat_mode_uses_general_honesty_boundary():
    import reflect_wxchatbot_reply as reflect

    prompt = reflect.build_prompt(
        {
            "reply_mode": "llm_chat",
            "chats": [
                {
                    "chat": "示例用户",
                    "is_group": False,
                    "messages": [{"sender": "示例用户", "content": "回答一个需要核实的问题"}],
                }
            ],
        }
    )

    assert "对缺少上下文、无法验证或需要外部实时信息的问题" in prompt
    assert "明确说明不确定性" in prompt
    assert "不要假装已经查询或确认" in prompt
    assert "天气" not in prompt

def test_build_messages_llm_chat_mode_omits_persona_but_keeps_memory():
    import reflect_wxchatbot_reply as reflect

    messages = reflect.build_messages(
        {
            "reply_mode": "llm_chat",
            "persona": "你是Flerken测试人格",
            "chats": [
                {
                    "chat": "示例用户",
                    "is_group": False,
                    "memory": {"summary": "长期：示例用户关注机器人记忆。", "recent_messages": []},
                    "messages": [{"sender": "示例用户", "content": "帮我解释一下uv"}],
                }
            ],
        }
    )

    assert [m["role"] for m in messages] == ["system", "user"]
    assert "## persona" not in messages[0]["content"]
    assert "你是Flerken测试人格" not in messages[0]["content"]
    assert "LLM-chat 模式" in messages[0]["content"]
    assert "长期：示例用户关注机器人记忆。" in messages[1]["content"]

def test_build_prompt_llm_chat_mode_still_includes_memory():
    import reflect_wxchatbot_reply as reflect

    prompt = reflect.build_prompt(
        {
            "reply_mode": "llm_chat",
            "persona": "这段不应该出现",
            "chats": [
                {
                    "chat": "示例用户",
                    "is_group": False,
                    "memory": {
                        "summary": "长期：示例用户今天一直在测试记忆。",
                        "daily": {
                            "2026-05-18": {
                                "by_user": {
                                    "wxid_f": {
                                        "name": "示例用户",
                                        "message_count": 1,
                                        "messages": [
                                            {
                                                "time": "2026-05-18 10:00:00",
                                                "content": "问过记忆是否对纯聊模式生效",
                                            }
                                        ],
                                    }
                                }
                            }
                        },
                    },
                    "user_daily_memory": {
                        "2026-05-18": {
                            "by_user": {
                                "wxid_f": {
                                    "name": "示例用户",
                                    "chats": {
                                        "group_a": {
                                            "chat": "群A",
                                            "messages": [
                                                {
                                                    "time": "2026-05-18 09:00:00",
                                                    "content": "在群A讨论过上下文记忆",
                                                }
                                            ],
                                        }
                                    },
                                }
                            }
                        }
                    },
                    "messages": [{"sender": "示例用户", "sender_wxid": "wxid_f", "content": "这些改造纯聊也有效吗？"}],
                }
            ],
        }
    )

    assert "LLM-chat 模式" in prompt
    assert "## 会话记忆" in prompt
    assert "长期：示例用户今天一直在测试记忆。" in prompt
    assert "问过记忆是否对纯聊模式生效" in prompt
    assert "当前用户今日跨会话记忆" in prompt
    assert "在群A讨论过上下文记忆" in prompt


if __name__ == "__main__":
    tests = [
        test_build_prompt_includes_chat_memory,
        test_build_prompt_includes_structured_daily_user_memory,
        test_build_prompt_includes_cross_chat_user_daily_memory,
        test_build_prompt_includes_memory_message_times,
        test_build_prompt_shows_timestamps_and_gap,
        test_build_prompt_tells_group_reply_not_to_prefix_at_name,
        test_build_prompt_tells_persona_mode_to_reply_per_mention,
        test_build_prompt_tells_llm_chat_mode_to_reply_per_mention,
        test_build_prompt_marks_random_interjection_as_proactive_task,
        test_build_prompt_does_not_expose_skip_decision_to_model,
        test_build_prompt_sanitizes_garbled_current_message_for_model,
        test_output_format_requests_json_object_replies,
        test_extract_replies_accepts_json_object_replies,
        test_extract_replies_accepts_fenced_json_object_replies,
        test_extract_replies_keeps_legacy_array_compatibility,
        test_build_prompt_persona_mode_includes_persona,
        test_build_messages_persona_mode_splits_system_and_user,
        test_build_prompt_llm_chat_mode_omits_persona_and_uses_direct_chat_rules,
        test_build_prompt_llm_chat_mode_preserves_model_capability,
        test_build_prompt_llm_chat_mode_uses_general_honesty_boundary,
        test_build_messages_llm_chat_mode_omits_persona_but_keeps_memory,
        test_build_prompt_llm_chat_mode_still_includes_memory,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
