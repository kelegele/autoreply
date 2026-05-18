# Reply Worker Design

## Goal

Replace the GenericAgent `agentmain.py --reflect` dependency with a local reply worker that keeps the same `pending.json` to `reply.json` contract used by `bot.py`.

## Architecture

The project keeps two long-running processes. `bot.py` polls WeChat, writes `exchange/pending.json`, and consumes `exchange/reply.json`. The new `reply_worker.py` is the second process: it loads `reflect_wxchatbot_reply.py`, calls `check()` on an interval, sends returned prompts to an OpenAI-compatible chat completions API, and passes the model output to `on_done()`.

This preserves the existing reflect module boundary:

- `init(args=None)` prepares state and logs startup.
- `check()` returns `None`, `/exit`, or a prompt string.
- `on_done(result)` parses the model output and writes `reply.json`.

## LLM Configuration

The worker reads model configuration from environment variables, including `.env` loaded through `python-dotenv`:

- `LLM_BASE_URL`, for example `https://api.deepseek.com/v1`
- `LLM_API_KEY`
- `LLM_MODEL`, for example `deepseek-v4-flash`
- `LLM_TIMEOUT`, default `120`
- `LLM_TEMPERATURE`, optional

The worker posts to `/chat/completions`, accepting base URLs that already include `/v1` or `/v1/chat/completions`.

## Error Handling

The worker logs to console and `logs/reply_worker_YYYYMMDD.log`. A failed LLM call does not delete future work because `reflect_wxchatbot_reply.check()` consumes only the current pending file after reading it. On failure, the worker logs the error and continues polling.

## Testing Plan

Use standalone `tests/unit/test_reply_worker.py` with injected fake HTTP transport. Cover URL normalization, environment config loading, chat completion payloads, and a single reflect cycle from `check()` to `on_done()`.

## Implementation Plan

1. Add failing tests for config, URL, LLM payload, and one-cycle reflect behavior.
2. Implement `reply_worker.py` using `urllib.request` and dependency injection for tests.
3. Run `uv run python tests/unit/test_reply_worker.py`.
4. Update `AGENTS.md` startup instructions to use `reply_worker.py`.
