import _path  # noqa: F401

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

def test_load_llm_config_reads_deepseek_options():
    from reply_worker import load_llm_config

    env = {
        "LLM_PROVIDER": "deepseek",
        "LLM_BASE_URL": "https://api.deepseek.com/v1",
        "LLM_API_KEY": "test-key",
        "LLM_MODEL": "deepseek-v4-flash",
        "LLM_MAX_TOKENS": "1200",
        "LLM_THINKING": "enabled",
        "LLM_REASONING_EFFORT": "high",
        "LLM_RESPONSE_FORMAT": "json_object",
    }

    config = load_llm_config(env)

    assert config.provider == "deepseek"
    assert config.max_tokens == 1200
    assert config.thinking == "enabled"
    assert config.reasoning_effort == "high"
    assert config.response_format == "json_object"

def test_load_llm_config_infers_provider_from_base_url():
    from reply_worker import load_llm_config

    deepseek = load_llm_config(
        {
            "LLM_BASE_URL": "https://api.deepseek.com",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "deepseek-v4-flash",
        }
    )
    compatible = load_llm_config(
        {
            "LLM_BASE_URL": "https://example.com/openai",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "some-model",
        }
    )

    assert deepseek.provider == "deepseek"
    assert compatible.provider == "openai_compatible"

def test_load_llm_config_normalizes_provider_aliases():
    from reply_worker import load_llm_config

    config = load_llm_config(
        {
            "LLM_PROVIDER": "openai-compatible",
            "LLM_BASE_URL": "https://example.com/openai",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "some-model",
            "LLM_THINKING": "enabled",
        }
    )

    assert config.provider == "openai_compatible"
    assert config.thinking == "enabled"


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

def test_call_llm_payload_includes_deepseek_options_only_for_deepseek():
    from reply_worker import LLMConfig, call_llm

    captured = {}

    def fake_post(url, headers, payload, timeout):
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "[]"}}]}

    config = LLMConfig(
        base_url="https://api.deepseek.com/v1",
        api_key="test-key",
        model="deepseek-v4-flash",
        provider="deepseek",
        max_tokens=1200,
        thinking="enabled",
        reasoning_effort="high",
        response_format="json_object",
    )

    call_llm("hello", config, post_json=fake_post, log_func=None)

    assert captured["payload"]["max_tokens"] == 1200
    assert captured["payload"]["thinking"] == {"type": "enabled"}
    assert captured["payload"]["reasoning_effort"] == "high"
    assert captured["payload"]["response_format"] == {"type": "json_object"}

def test_call_llm_payload_omits_deepseek_only_options_for_compatible_provider():
    from reply_worker import LLMConfig, call_llm

    captured = {}
    logs = []

    def fake_post(url, headers, payload, timeout):
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "[]"}}]}

    config = LLMConfig(
        base_url="https://example.com/v1",
        api_key="secret-key",
        model="compatible-model",
        provider="openai_compatible",
        max_tokens=1200,
        thinking="enabled",
        reasoning_effort="high",
        response_format="json_object",
    )

    call_llm("hello", config, post_json=fake_post, log_func=logs.append)

    assert captured["payload"]["max_tokens"] == 1200
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert "thinking" not in captured["payload"]
    assert "reasoning_effort" not in captured["payload"]
    assert "Ignoring DeepSeek-only option LLM_THINKING" in "\n".join(logs)
    assert "secret-key" not in "\n".join(logs)

def test_call_llm_accepts_structured_messages():
    from reply_worker import LLMConfig, call_llm

    captured = {}

    def fake_post(url, headers, payload, timeout):
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "[]"}}]}

    messages = [
        {"role": "system", "content": "规则"},
        {"role": "user", "content": "你好"},
    ]
    config = LLMConfig(base_url="https://api.deepseek.com/v1", api_key="test-key", model="deepseek-v4-flash")

    call_llm(messages, config, post_json=fake_post, log_func=None)

    assert captured["payload"]["messages"] == messages

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

def test_call_llm_raises_on_truncated_length_finish():
    from reply_worker import LLMConfig, call_llm_with_usage

    def fake_post(url, headers, payload, timeout):
        return {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"content": '{"replies":'},
                }
            ]
        }

    config = LLMConfig(
        base_url="https://api.deepseek.com/v1",
        api_key="test-key",
        model="deepseek-v4-flash",
    )

    try:
        call_llm_with_usage("hello", config, post_json=fake_post, log_func=None)
    except RuntimeError as exc:
        assert "finish_reason=length" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for truncated LLM response")


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

    def fake_call_llm(prompt, config, user_id=None):
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

        def fake_call_llm(prompt, config, user_id=None):
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


def test_run_once_does_not_replace_capability_limit_with_sensitive_fallback():
    from reply_worker import LLMConfig, run_once

    calls = []
    llm_content = json.dumps(
        {
            "replies": [
                {
                    "chat": "示例群聊",
                    "content": "抱歉，我无法实时查询天气，请使用天气预报应用查看准确信息。",
                    "is_group": True,
                    "sender": "示例用户",
                    "skip": False,
                }
            ]
        },
        ensure_ascii=False,
    )

    class FakeReflect:
        _pending_chats = [{"chat": "示例群聊", "is_group": True, "sender": "示例用户"}]

        def check(self):
            return "reply to this"

        def on_done(self, result):
            calls.append(result)

    def fake_call_llm(prompt, config, user_id=None):
        return llm_content

    config = LLMConfig(
        base_url="https://api.deepseek.com/v1",
        api_key="test-key",
        model="deepseek-v4-flash",
    )

    assert run_once(FakeReflect(), config, call_llm_func=fake_call_llm) is True
    assert calls == [llm_content]

def test_run_once_does_nothing_when_no_task():
    from reply_worker import LLMConfig, run_once

    class FakeReflect:
        def check(self):
            return None

    config = LLMConfig(base_url="https://api.deepseek.com/v1", api_key="test-key", model="deepseek-v4-flash")

    assert run_once(FakeReflect(), config) is False




def test_call_llm_payload_includes_hashed_user_id():
    from reply_worker import LLMConfig, call_llm_with_usage

    captured = {}

    def fake_post(url, headers, payload, timeout):
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "{}"}}]}

    config = LLMConfig(
        base_url="https://api.deepseek.com/v1",
        api_key="test-key",
        model="deepseek-v4-flash",
    )

    call_llm_with_usage("hello", config, post_json=fake_post, log_func=None, user_id="wxbot_abc123test")

    assert "user" in captured["payload"]
    user_val = captured["payload"]["user"]
    assert user_val.startswith("wxbot_")
    assert "wxid_f" not in user_val
    assert "示例用户" not in user_val

def test_call_llm_payload_never_exposes_raw_wxid_or_nickname():
    from reply_worker import LLMConfig, call_llm

    captured = {}

    def fake_post(url, headers, payload, timeout):
        captured["payload"] = payload
        captured["headers"] = headers
        return {"choices": [{"message": {"content": "{}"}}]}

    config = LLMConfig(
        base_url="https://api.deepseek.com/v1",
        api_key="test-key",
        model="deepseek-v4-flash",
    )

    call_llm("hello", config, post_json=fake_post)

    payload_str = str(captured["payload"])
    headers_str = str(captured["headers"])
    assert "secret-key" not in payload_str
    assert "test-key" not in payload_str



def test_call_llm_raises_on_content_filter_finish():
    from reply_worker import LLMConfig, call_llm_with_usage

    def fake_post(url, headers, payload, timeout):
        return {"choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}]}

    config = LLMConfig(base_url="https://api.deepseek.com/v1", api_key="test-key", model="deepseek-v4-flash")
    try:
        call_llm_with_usage("hello", config, post_json=fake_post, log_func=None)
        raise AssertionError("Expected RuntimeError for content_filter")
    except RuntimeError as exc:
        assert "content_filter" in str(exc)

def test_call_llm_raises_on_insufficient_system_resource():
    from reply_worker import LLMConfig, call_llm_with_usage

    def fake_post(url, headers, payload, timeout):
        return {"choices": [{"message": {"content": ""}, "finish_reason": "insufficient_system_resource"}]}

    config = LLMConfig(base_url="https://api.deepseek.com/v1", api_key="test-key", model="deepseek-v4-flash")
    try:
        call_llm_with_usage("hello", config, post_json=fake_post, log_func=None)
        raise AssertionError("Expected RuntimeError for insufficient_system_resource")
    except RuntimeError as exc:
        assert "insufficient_system_resource" in str(exc)

def test_token_usage_preserves_reasoning_tokens_and_cache_fields():
    from reply_worker import LLMConfig, call_llm_with_usage

    def fake_post(url, headers, payload, timeout):
        return {
            "choices": [{"message": {"content": "[]"}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "completion_tokens_details": {"reasoning_tokens": 3},
                "prompt_tokens_details": {"cached_tokens": 8},
                "prompt_cache_hit_tokens": 6,
                "prompt_cache_miss_tokens": 4,
            },
        }

    config = LLMConfig(base_url="https://api.deepseek.com/v1", api_key="test-key", model="deepseek-v4-flash")
    result = call_llm_with_usage("hello", config, post_json=fake_post, log_func=None)
    assert result.usage["prompt_tokens"] == 10
    assert result.usage["prompt_cache_hit_tokens"] == 6
    assert result.usage["prompt_cache_miss_tokens"] == 4
    assert result.usage["completion_tokens_details"]["reasoning_tokens"] == 3

def test_token_usage_omits_nonexistent_cache_fields():
    from reply_worker import LLMConfig, call_llm_with_usage

    def fake_post(url, headers, payload, timeout):
        return {
            "choices": [{"message": {"content": "[]"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
        }

    config = LLMConfig(base_url="https://api.deepseek.com/v1", api_key="test-key", model="deepseek-v4-flash")
    result = call_llm_with_usage("hello", config, post_json=fake_post, log_func=None)
    # Should not inject absent fields
    assert "prompt_cache_hit_tokens" not in result.usage or result.usage.get("prompt_cache_hit_tokens") is None

if __name__ == "__main__":
    tests = [
        test_chat_completions_url_accepts_base_variants,
        test_load_llm_config_reads_environment,
        test_load_llm_config_reads_deepseek_options,
        test_load_llm_config_infers_provider_from_base_url,
        test_load_llm_config_normalizes_provider_aliases,
        test_call_llm_posts_openai_compatible_payload,
        test_call_llm_payload_includes_deepseek_options_only_for_deepseek,
        test_call_llm_payload_omits_deepseek_only_options_for_compatible_provider,
        test_call_llm_accepts_structured_messages,
        test_call_llm_with_usage_returns_content_and_usage,
        test_call_llm_raises_on_truncated_length_finish,
        test_call_llm_logs_prompt_payload_and_raw_response_without_api_key,
        test_run_once_passes_reflect_prompt_to_llm_and_on_done,
        test_run_once_records_token_usage_for_pending_chats,
        test_run_once_does_not_replace_capability_limit_with_sensitive_fallback,
        test_run_once_does_nothing_when_no_task,
        test_call_llm_raises_on_content_filter_finish,
        test_call_llm_raises_on_insufficient_system_resource,
        test_token_usage_preserves_reasoning_tokens_and_cache_fields,
        test_token_usage_omits_nonexistent_cache_fields,
        test_call_llm_payload_includes_hashed_user_id,
        test_call_llm_payload_never_exposes_raw_wxid_or_nickname,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
