import json
import os
import tempfile
from pathlib import Path


def test_chat_completions_url_accepts_base_variants():
    from reply_worker import chat_completions_url

    assert chat_completions_url("https://api.deepseek.com") == "https://api.deepseek.com/v1/chat/completions"
    assert chat_completions_url("https://api.deepseek.com/v1") == "https://api.deepseek.com/v1/chat/completions"
    assert chat_completions_url("https://api.deepseek.com/v1/chat/completions") == "https://api.deepseek.com/v1/chat/completions"


def test_load_llm_config_reads_environment():
    from reply_worker import load_llm_config

    env = {
        "LLM_BASE_URL": "https://api.deepseek.com/v1",
        "LLM_API_KEY": "test-key",
        "LLM_MODEL": "deepseek-v4-flash",
        "LLM_TIMEOUT": "7",
        "LLM_TEMPERATURE": "0.3",
    }

    config = load_llm_config(env)

    assert config.base_url == "https://api.deepseek.com/v1"
    assert config.api_key == "test-key"
    assert config.model == "deepseek-v4-flash"
    assert config.timeout == 7
    assert config.temperature == 0.3


def test_call_llm_posts_openai_compatible_payload():
    from reply_worker import LLMConfig, call_llm

    captured = {}

    def fake_post(url, headers, payload, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {"choices": [{"message": {"content": "[{\"chat\":\"示例用户\",\"content\":\"好\",\"skip\":false}]"}}]}

    config = LLMConfig(
        base_url="https://api.deepseek.com/v1",
        api_key="test-key",
        model="deepseek-v4-flash",
        timeout=9,
        temperature=0.2,
    )

    result = call_llm("hello", config, post_json=fake_post)

    assert result == '[{"chat":"示例用户","content":"好","skip":false}]'
    assert captured["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"]["model"] == "deepseek-v4-flash"
    assert captured["payload"]["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["payload"]["temperature"] == 0.2
    assert captured["timeout"] == 9

def test_call_llm_with_usage_returns_content_and_usage():
    from reply_worker import LLMConfig, call_llm_with_usage

    def fake_post(url, headers, payload, timeout):
        return {
            "choices": [{"message": {"content": "[]"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        }

    config = LLMConfig(
        base_url="https://api.deepseek.com/v1",
        api_key="test-key",
        model="deepseek-v4-flash",
    )

    result = call_llm_with_usage("hello", config, post_json=fake_post, log_func=None)

    assert result.content == "[]"
    assert result.usage == {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}


def test_call_llm_logs_prompt_payload_and_raw_response_without_api_key():
    from reply_worker import LLMConfig, call_llm

    logs = []

    def fake_post(url, headers, payload, timeout):
        return {"choices": [{"message": {"content": "[]"}}]}

    config = LLMConfig(
        base_url="https://api.deepseek.com",
        api_key="secret-key",
        model="deepseek-v4-flash",
        timeout=9,
    )

    call_llm("hello", config, post_json=fake_post, log_func=logs.append)

    joined = "\n".join(logs)
    assert "LLM request URL: https://api.deepseek.com/v1/chat/completions" in joined
    assert "LLM prompt:\nhello" in joined
    assert '"model": "deepseek-v4-flash"' in joined
    assert "LLM raw response:" in joined
    assert "secret-key" not in joined


def test_run_once_passes_reflect_prompt_to_llm_and_on_done():
    from reply_worker import LLMConfig, run_once

    calls = []

    class FakeReflect:
        INTERVAL = 3

        def check(self):
            calls.append("check")
            return "reply to this"

        def on_done(self, result):
            calls.append(("on_done", result))

    def fake_call_llm(prompt, config):
        calls.append(("llm", prompt, config.model))
        return '[{"chat":"示例用户","content":"好","skip":false}]'

    config = LLMConfig(
        base_url="https://api.deepseek.com/v1",
        api_key="test-key",
        model="deepseek-v4-flash",
    )

    assert run_once(FakeReflect(), config, call_llm_func=fake_call_llm) is True
    assert calls == [
        "check",
        ("llm", "reply to this", "deepseek-v4-flash"),
        ("on_done", '[{"chat":"示例用户","content":"好","skip":false}]'),
    ]

def test_run_once_records_token_usage_for_pending_chats():
    import json
    import tempfile
    from pathlib import Path

    from reply_worker import LLMConfig, LLMResult, run_once

    with tempfile.TemporaryDirectory() as tmp:
        usage_path = Path(tmp) / "token_usage.json"

        class FakeReflect:
            _pending_data = {
                "chats": [
                    {
                        "chat": "示例用户",
                        "chat_hash": "abc123",
                        "is_group": False,
                        "messages": [{"sender": "示例用户", "content": "你好"}],
                    }
                ]
            }

            def check(self):
                return "reply to this"

            def on_done(self, result):
                pass

        def fake_call_llm(prompt, config):
            return LLMResult(
                content='[{"chat":"示例用户","content":"好","skip":false}]',
                usage={"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
                raw={},
            )

        config = LLMConfig(
            base_url="https://api.deepseek.com/v1",
            api_key="test-key",
            model="deepseek-v4-flash",
        )

        assert run_once(FakeReflect(), config, call_llm_func=fake_call_llm, token_usage_path=usage_path) is True
        data = json.loads(usage_path.read_text(encoding="utf-8"))

    assert data["total"]["total_tokens"] == 12
    assert data["by_chat"]["abc123"]["total_tokens"] == 12


def test_run_once_does_nothing_when_no_task():
    from reply_worker import LLMConfig, run_once

    class FakeReflect:
        def check(self):
            return None

    config = LLMConfig(base_url="https://api.deepseek.com/v1", api_key="test-key", model="deepseek-v4-flash")

    assert run_once(FakeReflect(), config) is False


if __name__ == "__main__":
    tests = [
        test_chat_completions_url_accepts_base_variants,
        test_load_llm_config_reads_environment,
        test_call_llm_posts_openai_compatible_payload,
        test_call_llm_with_usage_returns_content_and_usage,
        test_call_llm_logs_prompt_payload_and_raw_response_without_api_key,
        test_run_once_passes_reflect_prompt_to_llm_and_on_done,
        test_run_once_records_token_usage_for_pending_chats,
        test_run_once_does_nothing_when_no_task,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
