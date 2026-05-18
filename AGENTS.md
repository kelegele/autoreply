# Repository Guidelines

## 项目结构与模块组织

本仓库是一个 Windows 微信自动回复机器人，源码以根目录 Python 脚本为主。`bot.py` 是主轮询入口，负责读取配置、拉取消息、写入 `exchange/` 交互文件并触发发送；`reply_worker.py` 是本地反射回复进程，负责调用 LLM 并写回回复；`db.py` 负责解密后微信数据库读取；`sender.py`、`ljqCtrl.py` 负责微信窗口与点击输入自动化；`ocr_utils.py` 提供截图和 OCR；`reflect_wxchatbot_reply.py` 处理 prompt 构造与回复解析。

运行期目录不要当作源码修改：`exchange/` 存放待回复和回复文件，`state/` 存放轮询状态、`chat_memory/` 会话记忆、`user_memory.json` 跨会话用户每日记忆和 `token_usage.json` token 统计，`logs/` 存放日志，`db_export/` 存放导出的聊天数据库 CSV。项目文档放在 `docs/`。

## 外部依赖

项目依赖由 `pyproject.toml` 和 `uv.lock` 管理。已声明的第三方库包括 `python-dotenv`、`PyYAML`、`pycryptodome`、`pywin32`、`numpy`、`Pillow`、`opencv-python`、`rapidocr-onnxruntime`、`pyperclip`。项目还依赖 Windows、桌面版微信、可访问的微信数据目录、OpenAI-compatible LLM 接口，以及本机 OCR/窗口自动化能力。

## Python 环境规则

所有 Python 相关操作必须通过 `uv` 执行，禁止直接使用系统默认的 `python`、`pip`、`conda` 或手工管理的 `venv`。运行脚本使用 `uv run python <script.py>`，新增依赖使用 `uv add <package>`，同步环境使用 `uv sync`。只有在明确说明 `uv` 不适用并获得维护者同意后，才能使用替代方案。

## 构建、测试与开发命令

以下命令都必须通过 `uv` 执行。

- 启动时必须打开两个独立可见控制台窗口：一个运行 `bot.py`，一个运行 `reply_worker.py`。不要把这两个长期进程静默放到后台；窗口里要直接打印日志，便于人工观察。
- 维护者叫重启时，先用 `Get-CimInstance Win32_Process` 匹配命令行中含 `wechatbot-bot` 或 `wechatbot-reply-worker` 的旧进程，全部 `Stop-Process` 后再启动新窗口。不要依赖 `MainWindowTitle`，它对 PowerShell 子进程可能为空。
- 启动 `bot.py` 窗口时使用：`$botCmd = "& { `$Host.UI.RawUI.WindowTitle = 'wechatbot-bot'; $Host.UI.RawUI.WindowSize = New-Object Management.Automation.Host.Size(60,30); Set-Location 'F:\dev\wechatbot'; uv run python bot.py }"; Start-Process powershell -ArgumentList @('-NoExit','-Command',$botCmd)`。
- 启动 `reply_worker.py` 窗口时使用：`$replyCmd = "& { `$Host.UI.RawUI.WindowTitle = 'wechatbot-reply-worker'; $Host.UI.RawUI.WindowSize = New-Object Management.Automation.Host.Size(60,30); Set-Location 'F:\dev\wechatbot'; uv run python reply_worker.py }"; Start-Process powershell -ArgumentList @('-NoExit','-Command',$replyCmd)`。
- `uv run python sender.py`：单独调试微信发送自动化。
- `uv run python tests/manual/test_ocr_dump.py`：检查截图 OCR 输出。
- `uv run python tests/manual/test_sender_e2e.py`：运行真实微信端到端发送测试。
- `uv run python tests/unit/test_reply_worker.py`：运行本地反射回复 worker 的单元测试。
- `uv add <package>`：新增依赖并生成项目元数据。
- `uv sync`：按 `uv.lock` 同步本地环境。

## LLM 配置

`reply_worker.py` 使用 OpenAI-compatible `/chat/completions` HTTP API。通过 `.env` 或系统环境变量配置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`，可选配置 `LLM_TIMEOUT` 和 `LLM_TEMPERATURE`。DeepSeek 示例：`LLM_BASE_URL=https://api.deepseek.com`，`LLM_MODEL=deepseek-v4-flash`。不要提交真实 `LLM_API_KEY`。

回复模式由 `reply_mode` 控制：`persona` 使用 Flerken 人设；`llm_chat` 尽量像浏览器里的大模型聊天页直接回复，不套人设。可用环境变量 `WX_REPLY_MODE=llm_chat` 临时覆盖。

## 会话记忆

每个微信聊天框使用独立本地记忆，存放在 `state/chat_memory/`。记忆包含长期 `summary`、按日期/用户拆分的 `daily` 结构化记忆，以及最近消息列表；`state/user_memory.json` 额外按日期、用户、聊天框聚合跨会话发言，便于回答“某用户今天说了什么”。`reply_worker.py` 每次调用 LLM 前会注入这些记忆。最近消息最多保留 100 条，超过后触发 LLM 生成较详细的结构化长期记忆；`bot.py` 启动时从 DB 覆盖刷新每个会话最近 20 条聊天记录，但不得清空长期摘要和每日用户记忆。该目录可能包含私人聊天内容，必须视为敏感运行期数据。

## 代码风格与命名

使用 Python 3、4 空格缩进和 UTF-8 文本。函数与变量使用 `snake_case`，常量使用 `UPPER_SNAKE_CASE`。保持脚本式结构清晰，避免无计划地移动根目录模块。涉及微信 ID、窗口句柄、坐标和路径的变量要使用可读名称。

## 测试规范

测试目前是 `tests/` 目录下的独立 `test_*.py` 脚本，不是完整 pytest 套件。可离线测试放在 `tests/unit/`，真实微信/OCR/窗口自动化测试放在 `tests/manual/`。新增测试优先命名为 `test_<feature>.py`。真实测试需在文件顶部说明前置条件，例如微信窗口状态、OCR 可用性和测试数据路径。

## 提交与 PR 规范

当前 checkout 没有 Git 历史可参考。提交信息使用简短祈使句，例如 `Fix chat type detection` 或 `Add sender retry logging`。PR 需说明目的、配置变更、执行过的命令及结果；涉及 UI 自动化时附截图或关键日志，并注明是否跳过真实微信测试。

## 经验教训（Agent 编辑注意事项）

- **补丁回退**：`apply_patch` 在 Windows CRLF 下经常匹配失败。如果补丁不生效，改用 Python 脚本直接读/写文件：`Set-Content` 写临时 `.py` → `uv run python` 执行 → `Remove-Item` 清理。
- **PowerShell 花括号问题**：PowerShell 会在内联 Python `-c` 脚本里把 `{data}` 解析为变量展开，导致 `ParserError`。避免用 `uv run python -c` 写含花括号的代码；用 here-string `@"..."@` 写入临时 `.py` 文件再执行。
- **f-string 插值陷阱**：f-string 只对模板字面量做 `{{` → `{` 转义，不会对已插值的函数返回值再转义。`_output_format_block()` 如果用在 f-string 里，模板必须写单花括号 `{` `}`，不能依赖 `{{`。
- **进程管理**：PowerShell `Get-Process` 的 `MainWindowTitle` 对子进程经常为空，杀 wechatbot 进程必须用 `Get-CimInstance Win32_Process` 匹配命令行参数（含 `wechatbot-bot` 或 `wechatbot-reply-worker`）。
- **记忆更新时序**：bot 回复必须先发送成功再更新记忆，否则发送失败的消息也被当作已回复。实现：`on_done()` 写 `pending_meta.json`，`bot.py` 发送完成后读它调 `update_memory_after_replies`。
- **JSON 输出模板**：`response_format=json_object` 时，模型会严格按模板格式输出。模板里的示例 JSON 必须是可直接解析的单花括号格式。

## 安全与配置

不要提交 `.env`、数据库密钥、解密后的数据库、个人聊天导出或真实日志。文档中只写变量名示例，例如 `WX_DB_DIR`、`WX_MY_WXID`、`WX_MSG_DB_KEY`。`logs/`、`state/`、`exchange/`、`db_export/` 都应视为敏感运行期数据。
