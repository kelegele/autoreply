"""
reflect_wxchatbot_reply.py — wxchatbot 本地反射回复模块
启动: python reply_worker.py

流程:
  bot.py poll DB → pending.json → check()检测到 → 返回 prompt 给 reply_worker → LLM 生成回复 → on_done()写reply.json → bot.py发送

check():  每3秒检测 pending.json，有则读取+删除+返回格式化prompt
on_done(): 解析 LLM 输出，提取回复内容，写入 reply.json
"""
import json, re, os
from pathlib import Path
from datetime import datetime

# ============ 配置 ============
INTERVAL = 3    # 每3秒检查一次
ONCE = False    # 持续运行

PROJECT_DIR = Path(__file__).parent
EXCHANGE_DIR = PROJECT_DIR / "exchange"
PENDING_FILE = EXCHANGE_DIR / "pending.json"
REPLY_FILE = EXCHANGE_DIR / "reply.json"
CONFIG_FILE = PROJECT_DIR / "config.yaml"
LOG_DIR = PROJECT_DIR / "logs"

# ============ 模块级缓存 ============
# 由 check() 保存，on_done() 使用，防止LLM输出错误的chat名导致串频
_pending_chats = []
_pending_data = None

# ============ 工具函数 ============

def _load_config():
    """加载config.yaml中的persona"""
    try:
        import yaml
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        return cfg.get('persona', '你是一个友好的聊天助手')
    except Exception:
        return '你是一个友好的聊天助手'


def _log(msg):
    """简单日志"""
    try:
        LOG_DIR.mkdir(exist_ok=True)
        log_file = LOG_DIR / f"reply_reflect_{datetime.now():%Y%m%d}.log"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now():%H:%M:%S}] {msg}\n")
    except Exception:
        pass


# ============ reflect 接口 ============

def init(args=None):
    """初始化"""
    EXCHANGE_DIR.mkdir(exist_ok=True)
    # 清理残留的 pending（避免启动时处理旧消息）
    _log("wxchatbot_reply reflect module initialized")


def _format_memory(memory):
    if not memory:
        return ""
    lines = []
    summary = str(memory.get('summary', '')).strip()
    if summary:
        lines.append(f"长期摘要: {summary}")
    recent = memory.get('recent_messages', []) or []
    if recent:
        lines.append("最近上下文:")
        for item in recent[-12:]:
            sender = item.get('sender') or item.get('role') or '?'
            content = str(item.get('content', '')).strip()
            if content:
                lines.append(f"- [{sender}]: {content}")
    return "\n".join(lines)


def build_prompt(ga_data):
    """根据 pending 数据构造 LLM prompt。"""
    persona = ga_data.get('persona', _load_config())
    chats = ga_data['chats']
    msg_text = ""

    for chat_info in chats:
        chat_name = chat_info['chat']
        is_group = chat_info.get('is_group', False)
        chat_type = "群聊" if is_group else "私聊"
        msgs = chat_info.get('messages', [])
        msg_text += f"\n### {chat_type}: {chat_name}\n"

        memory_text = _format_memory(chat_info.get('memory'))
        if memory_text:
            msg_text += "\n## 会话记忆\n"
            msg_text += memory_text + "\n"

        msg_text += "\n## 当前新消息\n"
        for m in msgs:
            sender = m.get('sender', '?')
            content = m.get('content', '')
            at_mark = " [@我]" if m.get('is_at') else ""
            msg_text += f"- [{sender}]{at_mark}: {content}\n"

    return f"""[WXCHATBOT 自动回复任务]

你收到了以下微信新消息，请根据 persona 和会话记忆生成自然、口语化的回复。

## persona
{persona}

## 收到的消息
{msg_text}
## 要求
1. 每个会话单独回复，回复要自然，像真人聊天
2. 回复控制在50字以内
3. 如果是群聊中被@的消息，优先回复
4. 如果只是普通闲聊/表情包/转发，可以简短回复或不回复
5. **群聊和私聊要区分**：群聊可能有多人发言，回复要有针对性
6. 会话记忆只作为上下文参考，不要直接复述记忆内容

## 输出格式（必须严格遵循）
直接输出JSON，不要有其他内容：
```json
[
  {{"chat": "会话名", "content": "回复内容", "is_group": false, "sender": "对方昵称", "skip": false}},
  {{"chat": "群名", "content": "回复内容", "is_group": true, "sender": "说话的人", "skip": false}},
  {{"chat": "不需要回复的会话", "content": "", "is_group": false, "sender": "", "skip": true}}
]
```
skip=true 表示不回复该会话。只列出需要回复的会话即可。"""


def check():
    """
    检查 pending.json，有则返回 prompt，无则返回 None（静默跳过）
    
    pending.json 格式（由 bot.py format_messages_for_ga 生成）:
    {
        "persona": "...",
        "chats": [
            {
                "chat": "会话名",
                "messages": [
                    {"sender": "发送者", "content": "内容", "is_at": false}
                ],
                "needs_reply": true
            }
        ]
    }
    """
    if not PENDING_FILE.exists():
        return None
    
    try:
        with open(PENDING_FILE, 'r', encoding='utf-8') as f:
            pending = json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        _log(f"读取 pending.json 失败: {e}")
        # 删掉坏文件，避免卡住
        try: PENDING_FILE.unlink()
        except: pass
        return None
    
    # bot.py 的 write_pending 包了一层: {"timestamp":..., "messages": ga_data}
    # 所以需要从 messages 字段取实际数据
    ga_data = pending.get('messages', pending)
    try:
        from chat_memory import enrich_pending_with_memory
        ga_data = enrich_pending_with_memory(ga_data)
    except Exception as e:
        _log(f"⚠️ 加载会话记忆失败: {e}")
    
    if not ga_data or not ga_data.get('chats'):
        try: PENDING_FILE.unlink()
        except: pass
        return None
    
    # 删除 pending.json（已读取，避免重复触发）
    try: PENDING_FILE.unlink()
    except: pass
    
    chats = ga_data['chats']
    
    # ★ 保存聊天元信息，供 on_done 强制覆盖 LLM 的 chat 名（防串频）
    global _pending_chats, _pending_data
    _pending_chats = [{
        'chat': c['chat'],
        'is_group': c.get('is_group', False),
        'sender': c.get('messages', [{}])[-1].get('sender', '') if c.get('messages') else ''
    } for c in chats]
    _pending_data = ga_data
    
    # 统计消息数
    total_msgs = sum(len(c.get('messages', [])) for c in chats)
    _log(f"📬 检测到 {len(chats)} 个会话, {total_msgs} 条消息")
    
    prompt = build_prompt(ga_data)
    
    _log(f"→ 触发 LLM 生成回复 (prompt {len(prompt)} chars)")
    return prompt


def on_done(result):
    """
    LLM 完成后的回调，解析输出并写入 reply.json
    
    result: LLM 的完整输出文本，包含 JSON 格式的回复
    """
    _log(f"← LLM 回复完成 ({len(result)} chars)")
    
    # 从 LLM 输出中提取 JSON
    replies = _extract_replies(result)
    
    if not replies:
        _log("⚠️ 未能从 LLM 输出中提取有效回复")
        return

    try:
        from chat_memory import update_memory_after_replies
        if _pending_data:
            update_memory_after_replies(_pending_data, replies)
            _log("🧠 会话记忆已更新")
    except Exception as e:
        _log(f"⚠️ 更新会话记忆失败: {e}")
    
    # 过滤掉 skip=true 的
    valid_replies = [r for r in replies if not r.get('skip', False)]
    
    if not valid_replies:
        _log("所有会话标记为 skip，无需回复")
        return
    
    # 写入 reply.json
    try:
        with open(REPLY_FILE, 'w', encoding='utf-8') as f:
            json.dump(valid_replies, f, ensure_ascii=False, indent=2)
        _log(f"✅ reply.json 已写入 ({len(valid_replies)} 条回复)")
        for r in valid_replies:
            _log(f"  📤 [{r.get('chat', '?')}]: {r.get('content', '')[:50]}")
    except Exception as e:
        _log(f"❌ 写入 reply.json 失败: {e}")


def _extract_replies(text):
    """从 LLM 输出文本中提取JSON回复列表"""
    
    # 策略1: 找 ```json ... ``` 块
    json_pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(json_pattern, text, re.DOTALL)
    for match in matches:
        try:
            data = json.loads(match.strip())
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
        except json.JSONDecodeError:
            continue
    
    # 策略2: 找 [...] 块
    bracket_pattern = r'\[\s*\{.*?\}\s*\]'
    matches = re.findall(bracket_pattern, text, re.DOTALL)
    for match in matches:
        try:
            data = json.loads(match)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            continue
    
    # 策略3: 整个文本尝试解析
    try:
        data = json.loads(text.strip())
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    except json.JSONDecodeError:
        pass
    
    return []
