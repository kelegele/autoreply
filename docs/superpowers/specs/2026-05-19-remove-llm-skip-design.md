# Remove LLM Skip Design

## Goal

把“是否忽略消息”的业务判断固定在 `bot.py` 路由层，避免把已经判定需要回复的任务再交给大模型输出 `skip=true`。

## Design

- `bot.py` 继续使用 `needs_reply` 决定哪些会话进入 `pending.json`。
- `reflect_wxchatbot_reply.py` 的输出格式不再展示 `skip` 字段，也不再说明“不回复”由模型决定。
- 进入 LLM 的会话默认都是需要回复的任务；随机插话是强制主动回复任务。
- 解析和发送层暂时保留对旧 `skip=true` 输出的兼容过滤，避免旧 pending 或异常模型输出造成发送错误。

## Tests

- prompt 中不应出现 `skip`。
- 随机插话 prompt 应明确必须完成插话，不允许因 @ 别人而放弃。
- 旧 JSON 中带 `skip` 的解析兼容性保留。
