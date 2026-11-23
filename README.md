# autoreply

Windows 桌面自动回复助手。轮询本地聊天数据库，通过 LLM 生成回复，模拟操作聊天窗口发送消息。

## 系统要求

**Windows-only**。本项目依赖桌面聊天应用、Win32 API、OCR、窗口截图和点击输入自动化。

## 项目结构

```text
bot.py                         # 主轮询入口
reply_worker.py                # LLM 回复生成进程
db.py                          # 本地聊天数据库读取与解密后查询
sender.py / ljqCtrl.py          # 聊天窗口自动化
ocr_utils.py                   # 截图 OCR
reflect_wxchatbot_reply.py      # prompt 构造与回复解析
chat_memory.py / token_usage.py # 会话记忆与 token 统计
tests/unit/                    # 可离线运行的独立单元测试脚本
tests/manual/                  # 需要真实窗口/OCR/自动化环境的手工测试脚本
docs/                          # 设计文档和项目说明
exchange/ state/ logs/ db_export/ # 运行期数据，已忽略
```

## 快速开始

1. 安装 [uv](https://docs.astral.sh/uv/)
2. 配置 `.env`（参考下方环境变量）
3. 同步依赖：

```powershell
uv sync
```

4. 启动两个独立控制台窗口：

```powershell
# 窗口1：bot
uv run python bot.py

# 窗口2：reply worker
uv run python reply_worker.py
```

## 常用命令

```powershell
uv run python tests/unit/test_reply_worker.py
uv run python tests/manual/test_ocr_dump.py
uv run python tests/manual/test_sender_e2e.py
```

`tests/manual/` 下的脚本需要真实聊天窗口、OCR 和本机自动化环境。

## 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `WX_DB_DIR` | 聊天数据目录 | `C:\Users\xxx\Documents\xwechat_files\wxid_xxx` |
| `WX_MY_WXID` | 你的会话 ID | `wxid_xxx_9763` |
| `WX_MSG_DB_KEY` | 消息数据库密钥（hex） | `2e47...` |
| `WX_CONTACT_DB_KEY` | 联系人数据库密钥（hex） | `d8d9...` |
| `LLM_BASE_URL` | LLM API 地址 | `https://api.deepseek.com` |
| `LLM_API_KEY` | LLM API Key | `sk-xxx` |
| `LLM_MODEL` | 模型名 | `deepseek-v4-flash` |

## 架构

```text
bot.py
  -> exchange/pending.json
  -> reply_worker.py
  -> exchange/reply.json
  -> bot.py
  -> sender.py
```

## 安全

不要提交 `.env`、数据库密钥、解密后的数据库、聊天导出、真实日志或 `state/` 里的记忆文件。

## 免责声明

本项目仅供学习与研究使用。通过自动化方式操作即时通讯软件、读取其本地数据，可能违反该软件的用户协议，存在账号被限制或封禁的风险。使用本项目所产生的一切后果由使用者自行承担，作者不对任何滥用、损失或账号后果负责。本项目与任何即时通讯软件官方无关。

## 许可证

[MIT](LICENSE)
