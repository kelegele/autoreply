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


if __name__ == "__main__":
    tests = [test_build_prompt_includes_chat_memory]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
