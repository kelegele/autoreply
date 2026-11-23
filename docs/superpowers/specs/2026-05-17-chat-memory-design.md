# Chat Memory Design

## Goal

Give each desktop IM conversation its own local memory so replies are not stateless. The LLM remains a stateless HTTP API; this project supplies per-chat context on every request.

## Approach

Use summary plus recent messages. Each chat stores a compact long-term `summary` and a bounded `recent_messages` list. On every pending reply task, the worker loads memory by `chat_hash` when available, falls back to `chat` name when needed, injects the memory into the prompt, and updates the memory after replies are produced.

## Storage

Memory files live under `state/chat_memory/`. File names are sanitized stable keys:

- Prefer `chat_hash` from `pending.json`.
- Fall back to a hash of `chat` and `is_group`.

Each JSON file contains:

```json
{
  "chat": "chat display name",
  "is_group": false,
  "summary": "",
  "recent_messages": [
    {"role": "user", "sender": "name", "content": "message", "time": "..."},
    {"role": "assistant", "sender": "bot", "content": "reply", "time": "..."}
  ],
  "updated_at": "..."
}
```

## Prompt Injection

Before calling the LLM, `reply_worker.py` enriches each chat in the pending payload with a `memory` object. `reflect_wxchatbot_reply.py` renders the memory into the prompt:

- Long-term summary if present.
- Recent messages, newest last.
- Current pending messages.

## Update Rules

After LLM output is parsed, the worker appends current incoming messages as `role=user` and successful replies as `role=assistant`. Keep the most recent 30 entries. Defer LLM-based summary compression until the basic memory loop is stable.

## Testing Plan

Add standalone tests for memory key generation, load/save behavior, recent-message trimming, prompt enrichment, and update after replies.
