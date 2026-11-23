# Agent Cognitive Tools Design

## Goal

Define the first tool-call layer for the bot as a small set of high-level cognitive tools, inspired by Codex-style agent harnesses: the model proposes tool calls, the host validates and executes them, then returns results to the model for the final reply.

This design is intentionally separate from the DeepSeek API upgrade plan. It describes the tool abstraction and safety boundary, not a provider-specific implementation.

## Core Principle

The LLM must never directly operate the machine. It can only request a tool call. The host process owns all execution:

1. LLM receives chat context and available tool schemas.
2. LLM returns a tool call request.
3. `reply_worker.py` validates tool name, schema, permissions, and round limits.
4. The local tool runs and returns a bounded result.
5. The result is injected back as untrusted tool output.
6. LLM produces the final JSON reply.
7. `bot.py` remains the only sender.

## First Tool Set

Use four high-level cognitive tools:

```text
perception.observe
memory.recall
world.discover
resource.read
```

These are preferred over narrow tools such as `time.now`, `web.search`, or `web.fetch` because they describe the agent's capability domain instead of one implementation detail.

## Tool Semantics

### `perception.observe`

Reads current environment state. It is read-only and should never perform actions.

Initial scope:

```json
{"scope": "time", "query": "current local time and date"}
```

Future scopes may include:

```text
device
network
im
runtime
location
sensor
```

Examples:

- Current time, timezone, weekday, late-night flag.
- Whether the chat window is visible.
- Runtime health such as pending queue age.

### `memory.recall`

Retrieves local conversation memory. It covers chat-level memory, user daily memory, recent context, and long-term summaries.

Example:

```json
{
  "query": "示例用户今天说了什么",
  "filters": {
    "date": "today",
    "user": "示例用户",
    "scope": "all_chats"
  }
}
```

It must not expose raw memory files or arbitrary local paths. Results should be concise, structured, and limited by count and token budget.

### `world.discover`

Finds candidate external information sources. The first implementation can be web search, but the abstraction allows future sources such as news, maps, GitHub, docs, wikis, or local knowledge bases.

Example:

```json
{
  "query": "成都到波密318路况 雨季",
  "sources": ["web"],
  "freshness": "recent",
  "max_results": 5
}
```

Return only metadata and short summaries: title, URL, date when available, source, and snippet. Do not return full pages here.

### `resource.read`

Reads a known resource by URI. The first implementation should support `http` and `https` URLs only.

Example:

```json
{
  "uri": "https://example.com/article",
  "purpose": "summarize_for_reply"
}
```

Future URI types may include local docs, PDFs, images, or screenshots, but only after separate permission review.

## Permission Model

Initial tools are read-only:

```text
perception.observe: read_environment
memory.recall: read_memory
world.discover: read_web_index
resource.read: read_web_resource
```

Do not expose these capabilities in the first tool layer:

```text
shell
file_read
file_write
edit
send_message
delete_state
read_env
http_request with arbitrary method/body
```

Message sending remains outside tool calls. The final reply JSON is still the only path to sending messages.

## Safety Rules

- Tool names must be allowlisted.
- Arguments must be schema-validated.
- URLs must be `http` or `https`.
- Tool results must be size-limited.
- Tool results must be marked as untrusted external or untrusted retrieved context.
- Tool results cannot override persona, system rules, output format, or security policy.
- Limit tool loops, recommended `max_rounds: 2`.
- Log tool call name, sanitized arguments, duration, and result size.
- Never log secrets or raw API keys.

## Suggested Config

```yaml
tools:
  enabled: true
  mode: conservative
  max_rounds: 2
  allow:
    - perception.observe
    - memory.recall
    - world.discover
    - resource.read
```

Mode behavior:

- `conservative`: tools are used only for explicit asks, current facts, links, or memory lookup questions.
- `auto`: model may choose tools more freely, still within allowlist and round limits.

Recommended defaults:

- `persona`: conservative.
- `llm_chat`: conservative first, later consider auto after logs show stable behavior.
- Group chats: conservative regardless of mode.

## Implementation Shape

Proposed files:

```text
tools/__init__.py
tools/registry.py
tools/perception.py
tools/memory.py
tools/world.py
tools/resource.py
```

`reply_worker.py` owns the tool loop:

1. Send normal messages plus tool schemas to LLM.
2. If response contains `tool_calls`, validate and execute.
3. Append tool results as tool messages.
4. Repeat until no tool calls or `max_rounds` reached.
5. Require final JSON reply object.

`reflect_wxchatbot_reply.py` owns tool-aware prompt rules:

- Explain tools as optional capabilities.
- Instruct model not to call tools for normal casual replies.
- Instruct model to use `memory.recall` for "today / earlier / remember" questions.
- Instruct model to use `world.discover` and `resource.read` for current facts and links.

## First Milestone

Implement only:

```text
perception.observe(scope="time")
memory.recall(...)
world.discover(..., sources=["web"])
resource.read(uri=http/https)
```

Do not implement write-memory, shell, file tools, browser control, or chat action tools in the first milestone.

## Verification

Minimum tests:

- Tool registry rejects unknown tools.
- Tool registry rejects invalid arguments.
- `perception.observe(scope="time")` returns local time metadata.
- `memory.recall` can retrieve per-user daily memory without reading arbitrary files.
- `world.discover` returns bounded search results.
- `resource.read` rejects non-HTTP(S) URIs.
- Tool output is wrapped as untrusted context.
- Tool loop stops after `max_rounds`.
- Final reply still goes through existing JSON parser and `reply.json`.

Run with:

```powershell
uv run python tests/test_tools_registry.py
uv run python tests/test_reply_worker.py
uv run python tests/test_reflect_memory_prompt.py
uv run python -m py_compile reply_worker.py reflect_wxchatbot_reply.py
git diff --check
```
