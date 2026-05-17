# wechatbot

Windows 微信自动回复机器人。轮询本地微信数据库，通过 LLM 生成回复，模拟操作微信窗口发送消息。

## 系统要求

**Windows-only** — 本项目仅支持 Windows，原因：
- 依赖微信桌面版 + Win32 API 操作窗口（截图、OCR、模拟点击）
- 数据库路径和加密方式为 Windows 桌面版微信特有
- 使用 pywin32、ljqCtrl、ctypes.windll 等 Windows 专用接口

## 快速开始

1. 安装 [uv](https://docs.astral.sh/uv/)
2. 配置 .env（参考下方环境变量）
3. 安装依赖：uv sync
4. 启动两个控制台窗口：

```powershell
# 窗口1：bot
uv run python bot.py

# 窗口2：reply worker
uv run python reply_worker.py
```

## 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| WX_DB_DIR | 微信数据目录 | `C:\Users\xxx\Documents\xwechat_files\wxid_xxx` |
| WX_MY_WXID | 你的 wxid | `wxid_xxx_9763` |
| WX_MSG_DB_KEY | 消息数据库密钥（hex） | `2e47...` |
| WX_CONTACT_DB_KEY | 联系人数据库密钥（hex） | `d8d9...` |
| LLM_BASE_URL | LLM API 地址 | `https://api.deepseek.com` |
| LLM_API_KEY | LLM API Key | `sk-xxx` |
| LLM_MODEL | 模型名 | `deepseek-v4-flash` |

## 架构

```
bot.py (轮询DB) -> pending.json -> reply_worker.py (LLM生成回复) -> reply.json -> bot.py (发送)
```

- ot.py：轮询微信数据库，过滤消息，管理文件交换，调用 sender 发送回复
- eply_worker.py：读取 pending.json，调用 LLM API 生成回复，写入 reply.json
- sender.py：OCR 识别微信窗口，模拟点击发送消息
- chat_memory.py：每个聊天框独立记忆（摘要 + 最近消息）
- eflect_wxchatbot_reply.py：消息格式化、prompt 构造、回复解析

## 许可证

Private
