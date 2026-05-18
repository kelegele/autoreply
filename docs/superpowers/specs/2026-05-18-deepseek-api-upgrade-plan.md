# DeepSeek API Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the reply worker from a minimal OpenAI-compatible call to a configurable DeepSeek-aware integration.

**Architecture:** Keep `reply_worker.py` as the only HTTP client and keep `reflect_wxchatbot_reply.py` responsible for prompt construction and reply parsing. Apply the upgrades in three tiers so each tier can be tested, committed, and rolled back independently. Do not restart `bot.py` or `reply_worker.py` after implementation without maintainer confirmation.

**Tech Stack:** Python 3 via `uv`, DeepSeek OpenAI-compatible `/chat/completions`, local JSON exchange files, existing `test_*.py` script tests.

---

## Scope And Rules

- All Python commands must use `uv run python ...`.
- Preserve both `reply_mode: persona` and `reply_mode: llm_chat`.
- Preserve OpenAI-compatible portability: DeepSeek-only request fields must be enabled only when the configured provider is DeepSeek.
- Keep secrets out of logs. Never print `LLM_API_KEY`.
- Continue recording token usage in `state/token_usage.json`.
- Runtime data under `state/`, `exchange/`, `logs/`, and `db_export/` remains sensitive.
- Implement with TDD: write failing tests first, verify failure, implement, verify pass, then commit.

## Provider Gating

The client must distinguish generic OpenAI-compatible behavior from DeepSeek-specific behavior.

Recommended config:

```env
LLM_PROVIDER=deepseek
```

Provider detection rules:

- If `LLM_PROVIDER` is set, trust it after normalization.
- If unset and `LLM_BASE_URL` host contains `deepseek.com`, infer `deepseek`.
- Otherwise use `openai_compatible`.

DeepSeek-only fields:

```text
thinking
reasoning_effort
prefix completion
DeepSeek-specific finish_reason handling
DeepSeek cache usage fields
```

Generic OpenAI-compatible fields:

```text
model
messages
stream
temperature
max_tokens
response_format
tools/tool_choice, when implemented
```

Hard rule: if provider is not `deepseek`, do not send DeepSeek-only fields even when the matching environment variables are present. Log a sanitized warning such as `Ignoring DeepSeek-only option LLM_THINKING for provider=openai_compatible`.

## Tier 1: Stable Structured Replies

**Impact:** Higher reply reliability, fewer JSON parsing failures, clearer prompt boundaries, controllable output length and reasoning cost.

**Files:**
- Modify: `reply_worker.py`
- Modify: `reflect_wxchatbot_reply.py`
- Test: `tests/test_reply_worker.py`
- Test: `tests/test_reflect_memory_prompt.py`
- Optional docs: `AGENTS.md`, `README.md`

### Task 1: Add LLM Request Options

**Step 1: Write failing tests**

Add tests that `load_llm_config()` reads:

```python
LLM_PROVIDER=deepseek
LLM_MAX_TOKENS=1200
LLM_THINKING=enabled
LLM_REASONING_EFFORT=high
LLM_RESPONSE_FORMAT=json_object
```

Expected config fields: `provider`, `max_tokens`, `thinking`, `reasoning_effort`, `response_format`.

Also add tests that:

- `LLM_PROVIDER=deepseek` enables DeepSeek-only options.
- `LLM_PROVIDER=openai_compatible` keeps those options in config but marks them ineligible for payload use.
- Unset `LLM_PROVIDER` with `LLM_BASE_URL=https://api.deepseek.com` infers `deepseek`.
- Unset `LLM_PROVIDER` with another OpenAI-compatible URL infers `openai_compatible`.

**Step 2: Verify RED**

Run: `uv run python tests/test_reply_worker.py`

Expected: FAIL because `LLMConfig` lacks these fields.

**Step 3: Implement**

Extend `LLMConfig` and `load_llm_config()`. Recommended defaults:

- `LLM_MAX_TOKENS`: unset by default.
- `LLM_THINKING`: unset by default, so provider default still works.
- `LLM_REASONING_EFFORT`: unset by default.
- `LLM_RESPONSE_FORMAT`: unset by default, enabled per call where safe.

**Step 4: Verify GREEN**

Run: `uv run python tests/test_reply_worker.py`

Expected: PASS.

### Task 2: Build DeepSeek-Aware Payload

**Step 1: Write failing tests**

Test that `call_llm_with_usage()` includes configured DeepSeek-only fields only when `config.provider == "deepseek"`:

```json
{
  "max_tokens": 1200,
  "thinking": {"type": "enabled"},
  "reasoning_effort": "high",
  "response_format": {"type": "json_object"}
}
```

Also test that:

- Unset fields are omitted.
- `provider=openai_compatible` still sends `max_tokens` and `response_format`, but omits `thinking` and `reasoning_effort`.
- Logs never include API keys.

**Step 2: Verify RED**

Run: `uv run python tests/test_reply_worker.py`

Expected: FAIL because payload still only has `model`, `messages`, `stream`, `temperature`.

**Step 3: Implement**

Add a helper such as `build_chat_payload(messages, config, response_format=None)`. Keep `temperature` optional. If `thinking` is configured and provider is DeepSeek, follow DeepSeek field shape exactly. If provider is not DeepSeek, ignore DeepSeek-only fields and optionally log a sanitized warning.

**Step 4: Verify GREEN**

Run: `uv run python tests/test_reply_worker.py`

Expected: PASS.

### Task 3: Split Prompt Into System And User Messages

**Step 1: Write failing tests**

In `tests/test_reflect_memory_prompt.py`, assert `build_prompt()` or a new function returns structured messages:

```python
[
    {"role": "system", "content": "...rules..."},
    {"role": "user", "content": "...memory and current messages..."},
]
```

Persona mode must include `## persona` in system content. LLM-chat mode must omit persona but keep memory in user content.

**Step 2: Verify RED**

Run: `uv run python tests/test_reflect_memory_prompt.py`

Expected: FAIL because `build_prompt()` returns one string.

**Step 3: Implement**

Add `build_messages(ga_data)` in `reflect_wxchatbot_reply.py`. Keep `build_prompt()` as a compatibility wrapper that joins messages for tests or older callers if needed. Update `check()` to return messages, or return an object that `reply_worker.run_once()` accepts.

**Step 4: Update Worker Compatibility**

Allow `call_llm_with_usage(prompt_or_messages, config)` to accept either `str` or `list[dict]`. Log both safely.

**Step 5: Verify GREEN**

Run:

```powershell
uv run python tests/test_reflect_memory_prompt.py
uv run python tests/test_reply_worker.py
```

Expected: PASS.

### Task 4: JSON Object Output

**Step 1: Write failing tests**

Change expected reply shape to:

```json
{"replies":[{"chat":"示例用户","content":"好","is_group":false,"sender":"示例用户","skip":false}]}
```

Test `_extract_replies()` still accepts legacy array and fenced JSON for backward compatibility.

**Step 2: Verify RED**

Run: `uv run python tests/test_reflect_memory_prompt.py`

Expected: FAIL because the format block still asks for a raw array.

**Step 3: Implement**

Update `_output_format_block()` to require a JSON object with `replies`. Update `_extract_replies()` to parse:

- `{"replies": [...]}`
- legacy `[ ... ]`
- fenced JSON object or array

Set `response_format=json_object` for reply generation calls.

**Step 4: Verify GREEN**

Run:

```powershell
uv run python tests/test_reflect_memory_prompt.py
uv run python tests/test_reply_worker.py
```

Expected: PASS.

### Task 5: Length Finish Handling

**Step 1: Write failing tests**

Fake a response with:

```json
{"choices":[{"finish_reason":"length","message":{"content":"{\"replies\":"}}]}
```

Expected: `call_llm_with_usage()` or `run_once()` raises a clear retryable error.

**Step 2: Verify RED**

Run: `uv run python tests/test_reply_worker.py`

Expected: FAIL because finish reason is ignored.

**Step 3: Implement**

Store `finish_reason` in `LLMResult` or inspect it in `call_llm_with_usage()`. For `length`, raise `RuntimeError("LLM response truncated: finish_reason=length")`. Do not silently write broken `reply.json`.

**Step 4: Verify GREEN**

Run: `uv run python tests/test_reply_worker.py`

Expected: PASS.

**Tier 1 Commit:** `git commit -m "Improve DeepSeek reply payload handling"`

## Tier 2: Safer Operations And Observability

**Impact:** Better failure diagnosis, safer provider behavior, lower accidental privacy exposure, and cleaner cost analysis.

**Files:**
- Modify: `reply_worker.py`
- Modify: `token_usage.py`
- Modify: `config.yaml`
- Test: `tests/test_reply_worker.py`
- Test: `tests/test_token_usage.py`

### Task 6: Add Hashed User ID

**Step 1: Write failing tests**

Given pending chat data with `chat_hash` or `sender_wxid`, assert payload includes a non-reversible `user` or `user_id` value. It must not include raw wxid, nickname, or chat name.

**Step 2: Verify RED**

Run: `uv run python tests/test_reply_worker.py`

Expected: FAIL because no user identifier is sent.

**Step 3: Implement**

Add helper `stable_user_id(pending_data)` using SHA-256 and a prefix like `wxbot_`. Feed it only to reply calls. Skip for memory summarization unless there is a clear chat reference.

**Step 4: Verify GREEN**

Run: `uv run python tests/test_reply_worker.py`

Expected: PASS.

### Task 7: Classify Finish Reasons

**Step 1: Write failing tests**

Cover `content_filter`, `insufficient_system_resource`, and normal `stop`.

**Step 2: Verify RED**

Run: `uv run python tests/test_reply_worker.py`

Expected: FAIL because all finish reasons are treated the same.

**Step 3: Implement**

For `content_filter`, route to `fallback_sensitive`. For `insufficient_system_resource`, route to `fallback_unavailable`. Keep `stop` and `tool_calls` non-error for future compatibility.

**Step 4: Verify GREEN**

Run: `uv run python tests/test_reply_worker.py`

Expected: PASS.

### Task 8: Token Usage Metadata

**Step 1: Write failing tests**

Assert `token_usage.json` records cache hit/miss token fields when present:

- `prompt_cache_hit_tokens`
- `prompt_cache_miss_tokens`
- `reasoning_tokens`

**Step 2: Verify RED**

Run: `uv run python tests/test_token_usage.py`

Expected: FAIL if fields are dropped.

**Step 3: Implement**

Preserve provider-specific usage details in each event. Aggregate only stable numeric totals at top level.

**Step 4: Verify GREEN**

Run: `uv run python tests/test_token_usage.py`

Expected: PASS.

### Task 9: Config Documentation

**Step 1: Update docs**

Document these environment variables:

```env
LLM_MAX_TOKENS=1200
LLM_THINKING=enabled
LLM_REASONING_EFFORT=high
LLM_RESPONSE_FORMAT=json_object
```

Also document that `thinking` may increase latency and token cost.

**Step 2: Verify**

Run: `git diff --check`

Expected: no whitespace errors.

**Tier 2 Commit:** `git commit -m "Add DeepSeek runtime safeguards"`

## Tier 3: Advanced Capabilities

**Impact:** Adds richer “browser-like” LLM behavior, but increases complexity, latency, and prompt-injection risk. Implement only after Tier 1 and Tier 2 are stable.

**Files:**
- Modify: `reply_worker.py`
- Modify: `reflect_wxchatbot_reply.py`
- Modify or create: `web_search.py`
- Test: `tests/test_reply_worker.py`
- Test: `tests/test_reflect_memory_prompt.py`
- Test: `tests/test_web_search.py`

### Task 10: Evaluate Prefix Completion

**Decision Gate:** Only implement if JSON mode still fails in real usage.

**Plan:**

- Add `LLM_ENABLE_PREFIX_COMPLETION=false` default.
- If enabled, require base URL ending in `/beta`.
- Last message must be assistant with `prefix=true`.
- Do not combine with normal reply mode until tested against DeepSeek directly.

**Risk:** Beta endpoint behavior may differ from normal chat completions. It is not needed if JSON mode is stable.

### Task 11: Optional Streaming

**Decision Gate:** Do not implement for WeChat replies unless there is a measured latency problem.

**Plan:**

- Keep `stream=false` by default.
- If enabled, buffer the complete stream before calling `on_done()`.
- Token usage may arrive differently, so update accounting tests.

**Risk:** Streaming does not help WeChat sending because we must parse full JSON before writing `reply.json`.

### Task 12: Tool Calls And Web Search

**Step 1: Design Search Boundary**

Create a search tool that accepts a query and returns source title, URL, date, and summary. Never pass raw webpage instructions back as trusted system text.

**Step 2: Write failing tests**

Test that a search-needed query produces a tool request, a sanitized result block, and a final reply with citations if needed.

**Step 3: Implement**

Use explicit tool routing:

- Detect search intent in `llm_chat` mode first.
- For persona mode, search only when the user asks for current facts.
- Inject search results into the next LLM call as untrusted context.

**Step 4: Verify**

Run:

```powershell
uv run python tests/test_web_search.py
uv run python tests/test_reply_worker.py
```

Expected: PASS.

**Risk:** Tool calls create a prompt-injection surface. Source text must be marked untrusted, summarized, and never allowed to override system rules.

**Tier 3 Commit:** `git commit -m "Plan advanced DeepSeek capabilities"` for planning only, or a feature-specific commit if implemented.

## Final Verification Checklist

Run these before claiming implementation complete:

```powershell
uv run python tests/test_reply_worker.py
uv run python tests/test_reflect_memory_prompt.py
uv run python tests/test_token_usage.py
uv run python tests/test_chat_memory.py
uv run python -m py_compile bot.py chat_memory.py reflect_wxchatbot_reply.py reply_worker.py token_usage.py sender.py
git diff --check
```

Expected: all tests pass; compile exits 0; `git diff --check` has no errors.

## Rollout

1. Merge Tier 1 first and run locally without restarting automatically.
2. Ask maintainer before restarting `wechatbot-bot` and `wechatbot-reply-worker`.
3. Observe `reply_worker` logs for payload shape, raw response, `finish_reason`, and token usage.
4. If JSON mode causes provider errors, turn off `LLM_RESPONSE_FORMAT` and keep the parser backward compatible.
5. Roll out Tier 2 after one stable run.
6. Revisit Tier 3 only after real failures justify it.
