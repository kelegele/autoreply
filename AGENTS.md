# Repository Guidelines

## 项目结构与模块组织

本仓库是一个 Windows 微信自动回复机器人，源码以根目录 Python 脚本为主。`bot.py` 是主轮询入口，负责读取配置、拉取消息、写入 `exchange/` 交互文件并触发发送；`reply_worker.py` 是本地反射回复进程，负责调用 LLM 并写回回复；`db.py` 负责解密后微信数据库读取；`sender.py`、`ljqCtrl.py` 负责微信窗口与点击输入自动化；`ocr_utils.py` 提供截图和 OCR；`reflect_wxchatbot_reply.py` 处理 prompt 构造与回复解析。

运行期目录不要当作源码修改：`exchange/` 存放待回复和回复文件，`state/` 存放轮询状态和 `chat_memory/` 会话记忆，`logs/` 存放日志，`db_export/` 存放导出的聊天数据库 CSV。项目文档放在 `docs/`。

## 外部依赖

项目依赖由 `pyproject.toml` 和 `uv.lock` 管理。已声明的第三方库包括 `python-dotenv`、`PyYAML`、`pycryptodome`、`pywin32`、`numpy`、`Pillow`、`opencv-python`、`rapidocr-onnxruntime`、`pyperclip`。项目还依赖 Windows、桌面版微信、可访问的微信数据目录、OpenAI-compatible LLM 接口，以及本机 OCR/窗口自动化能力。

## Python 环境规则

所有 Python 相关操作必须通过 `uv` 执行，禁止直接使用系统默认的 `python`、`pip`、`conda` 或手工管理的 `venv`。运行脚本使用 `uv run python <script.py>`，新增依赖使用 `uv add <package>`，同步环境使用 `uv sync`。只有在明确说明 `uv` 不适用并获得维护者同意后，才能使用替代方案。

## 构建、测试与开发命令

以下命令都必须通过 `uv` 执行。

- 启动时必须打开两个独立可见控制台窗口：一个运行 `bot.py`，一个运行 `reply_worker.py`。不要把这两个长期进程静默放到后台；窗口里要直接打印日志，便于人工观察。
- 启动 `bot.py` 窗口时使用：`$botCmd = "& { `$Host.UI.RawUI.WindowTitle = 'wechatbot-bot'; Set-Location 'F:\dev\wechatbot'; uv run python bot.py }"; Start-Process powershell -ArgumentList @('-NoExit','-Command',$botCmd)`。
- 启动 `reply_worker.py` 窗口时使用：`$replyCmd = "& { `$Host.UI.RawUI.WindowTitle = 'wechatbot-reply-worker'; Set-Location 'F:\dev\wechatbot'; uv run python reply_worker.py }"; Start-Process powershell -ArgumentList @('-NoExit','-Command',$replyCmd)`。
- `uv run python sender.py`：单独调试微信发送自动化。
- `uv run python test_ocr_dump.py`：检查截图 OCR 输出。
- `uv run python test_sender_e2e.py`：运行真实微信端到端发送测试。
- `uv run python test_reply_worker.py`：运行本地反射回复 worker 的单元测试。
- `uv add <package>`：新增依赖并生成项目元数据。
- `uv sync`：按 `uv.lock` 同步本地环境。

## LLM 配置

`reply_worker.py` 使用 OpenAI-compatible `/chat/completions` HTTP API。通过 `.env` 或系统环境变量配置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`，可选配置 `LLM_TIMEOUT` 和 `LLM_TEMPERATURE`。DeepSeek 示例：`LLM_BASE_URL=https://api.deepseek.com`，`LLM_MODEL=deepseek-v4-flash`。不要提交真实 `LLM_API_KEY`。

## 会话记忆

每个微信聊天框使用独立本地记忆，存放在 `state/chat_memory/`。记忆由长期 `summary` 和最近消息列表组成；`reply_worker.py` 每次调用 LLM 前会注入对应聊天的记忆，回复完成后更新该聊天的记忆文件。最近消息最多保留 50 条，超过后触发 LLM 摘要旧消息；`bot.py` 启动时会刷新每个会话最近 20 条聊天记录。该目录可能包含私人聊天内容，必须视为敏感运行期数据。

## 代码风格与命名

使用 Python 3、4 空格缩进和 UTF-8 文本。函数与变量使用 `snake_case`，常量使用 `UPPER_SNAKE_CASE`。保持脚本式结构清晰，避免无计划地移动根目录模块。涉及微信 ID、窗口句柄、坐标和路径的变量要使用可读名称。

## 测试规范

测试目前是独立 `test_*.py` 脚本，不是完整 pytest 套件。新增测试优先命名为 `test_<feature>.py`。纯解析、数据库逻辑与真实微信自动化测试应分开；真实测试需在文件顶部说明前置条件，例如微信窗口状态、OCR 可用性和测试数据路径。

## 提交与 PR 规范

当前 checkout 没有 Git 历史可参考。提交信息使用简短祈使句，例如 `Fix chat type detection` 或 `Add sender retry logging`。PR 需说明目的、配置变更、执行过的命令及结果；涉及 UI 自动化时附截图或关键日志，并注明是否跳过真实微信测试。

## 安全与配置

不要提交 `.env`、数据库密钥、解密后的数据库、个人聊天导出或真实日志。文档中只写变量名示例，例如 `WX_DB_DIR`、`WX_MY_WXID`、`WX_MSG_DB_KEY`。`logs/`、`state/`、`exchange/`、`db_export/` 都应视为敏感运行期数据。
