import copy
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path

from text_sanitize import NON_TEXT_PLACEHOLDER, sanitize_message_content


DEFAULT_MEMORY_DIR = Path(__file__).parent / "state" / "chat_memory"
DEFAULT_USER_MEMORY_FILE = Path(__file__).parent / "state" / "user_memory.json"


def _safe_key(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value or "").strip("._")
    return cleaned[:120] or "unknown"


def memory_key(chat: dict) -> str:
    chat_hash = str(chat.get("chat_hash") or "").strip()
    if chat_hash:
        return _safe_key(chat_hash)

    raw = f"{chat.get('chat', '')}|{bool(chat.get('is_group', False))}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"chat_{digest}"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ChatMemoryStore:
    def __init__(self, memory_dir=DEFAULT_MEMORY_DIR, max_recent=100, summarize_fn=None, user_memory_path=DEFAULT_USER_MEMORY_FILE):
        self.memory_dir = Path(memory_dir)
        self.max_recent = max_recent
        self.summarize_fn = summarize_fn
        self.user_memory_path = Path(user_memory_path)

    def path_for(self, chat: dict) -> Path:
        return self.memory_dir / f"{memory_key(chat)}.json"

    def default_memory(self, chat: dict) -> dict:
        return {
            "chat": chat.get("chat", ""),
            "is_group": bool(chat.get("is_group", False)),
            "summary": "",
            "daily": {},
            "recent_messages": [],
            "updated_at": _now_iso(),
        }

    def load(self, chat: dict) -> dict:
        path = self.path_for(chat)
        if not path.exists():
            return self.default_memory(chat)
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return self.default_memory(chat)

        data.setdefault("chat", chat.get("chat", ""))
        data.setdefault("is_group", bool(chat.get("is_group", False)))
        data.setdefault("summary", "")
        data.setdefault("daily", {})
        data.setdefault("recent_messages", [])
        data.setdefault("updated_at", _now_iso())
        data["recent_messages"] = _sanitize_memory_entries(data.get("recent_messages", []))
        data["daily"] = _sanitize_daily_memory(data.get("daily", {}))
        return data

    def save(self, chat: dict, memory: dict, summarize_fn=None):
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        data = copy.deepcopy(memory)
        data["chat"] = chat.get("chat", data.get("chat", ""))
        data["is_group"] = bool(chat.get("is_group", data.get("is_group", False)))
        recent = _sanitize_memory_entries(data.get("recent_messages", []))
        if len(recent) > self.max_recent:
            overflow = recent[: -self.max_recent]
            recent = recent[-self.max_recent :]
            summary_fn = summarize_fn if summarize_fn is not None else self.summarize_fn
            if summary_fn is None:
                summary_fn = summarize_memory_with_llm
            try:
                new_summary = summary_fn(str(data.get("summary", "")), overflow, chat)
                if new_summary is not None:
                    data["summary"] = str(new_summary).strip()
            except Exception as exc:
                data["summary"] = _fallback_summary(str(data.get("summary", "")), overflow, exc)
        data["recent_messages"] = recent
        data["updated_at"] = _now_iso()

        path = self.path_for(chat)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(str(tmp), str(path))

def _message_fingerprint(message: dict) -> str:
    if message.get("message_id"):
        return f"id:{message.get('message_id')}"
    return "|".join(
        [
            str(message.get("time", "")),
            str(message.get("sender", "")),
            str(message.get("content", "")),
        ]
    )

def _message_time(message: dict) -> str:
    return str(message.get("timestamp") or message.get("time") or _now_iso())

def _message_date(message: dict) -> str:
    time_text = _message_time(message)
    if len(time_text) >= 10 and re.match(r"^\d{4}-\d{2}-\d{2}", time_text):
        return time_text[:10]
    return datetime.now().strftime("%Y-%m-%d")

def _chat_from_ref(chat_ref, messages=None, is_group=False, chat_name=None):
    if isinstance(chat_ref, dict):
        return {
            "chat": chat_ref.get("chat", chat_ref.get("chat_name", "")),
            "chat_hash": chat_ref.get("chat_hash", ""),
            "is_group": bool(chat_ref.get("is_group", False)),
        }

    first = (messages or [{}])[0] if messages else {}
    return {
        "chat": chat_name or first.get("chat_name") or str(chat_ref),
        "chat_hash": str(chat_ref or first.get("chat_hash", "")),
        "is_group": bool(is_group or first.get("is_group", False)),
    }

def _message_to_memory_entry(message: dict) -> dict | None:
    content = sanitize_message_content(message.get("content", ""))
    if not content:
        return None
    is_self = bool(message.get("is_self", False))
    entry = {
        "role": "assistant" if is_self else "user",
        "sender": "bot" if is_self else message.get("sender", ""),
        "content": content,
        "time": _message_time(message),
    }
    if message.get("sender_wxid"):
        entry["sender_wxid"] = message.get("sender_wxid")
    if message.get("local_id") is not None:
        entry["message_id"] = str(message.get("local_id"))
    return entry

def _user_key(entry: dict) -> str:
    return str(entry.get("sender_wxid") or entry.get("sender") or entry.get("role") or "unknown")

def _append_daily_message(memory: dict, chat: dict, entry: dict, user_memory_path=None, max_messages_per_user=300):
    entry = copy.deepcopy(entry)
    entry["content"] = sanitize_message_content(entry.get("content", ""))
    if not entry["content"]:
        return
    day_key = _message_date(entry)
    daily = memory.setdefault("daily", {})
    day = daily.setdefault(
        day_key,
        {
            "chat": chat.get("chat", memory.get("chat", "")),
            "chat_hash": chat.get("chat_hash", ""),
            "is_group": bool(chat.get("is_group", memory.get("is_group", False))),
            "chat_summary": "",
            "by_user": {},
            "updated_at": _now_iso(),
        },
    )
    day["chat"] = chat.get("chat", day.get("chat", ""))
    day["chat_hash"] = chat.get("chat_hash", day.get("chat_hash", ""))
    day["is_group"] = bool(chat.get("is_group", day.get("is_group", False)))

    key = _user_key(entry)
    user = day.setdefault("by_user", {}).setdefault(
        key,
        {
            "name": entry.get("sender", ""),
            "wxid": entry.get("sender_wxid", ""),
            "message_count": 0,
            "messages": [],
            "summary": "",
            "updated_at": _now_iso(),
        },
    )
    if entry.get("sender"):
        user["name"] = entry.get("sender")
    if entry.get("sender_wxid"):
        user["wxid"] = entry.get("sender_wxid")

    daily_item = {
        "time": entry.get("time", ""),
        "role": entry.get("role", ""),
        "sender": entry.get("sender", ""),
        "content": entry.get("content", ""),
    }
    if entry.get("message_id"):
        daily_item["message_id"] = entry.get("message_id")
    fingerprint = _message_fingerprint(entry)
    existing = {_message_fingerprint(item) for item in user.get("messages", [])}
    if fingerprint not in existing:
        user["messages"].append(daily_item)
        user["message_count"] = int(user.get("message_count") or 0) + 1
        user["messages"] = user["messages"][-max_messages_per_user:]
    user["updated_at"] = _now_iso()
    day["updated_at"] = _now_iso()
    _append_global_user_daily_message(user_memory_path, chat, entry, max_messages_per_user=max_messages_per_user)

def _sanitize_memory_entries(entries):
    cleaned = []
    for item in entries or []:
        if not isinstance(item, dict):
            continue
        entry = copy.deepcopy(item)
        entry["content"] = sanitize_message_content(entry.get("content", ""))
        if entry["content"]:
            cleaned.append(entry)
    return cleaned

def _sanitize_daily_memory(daily):
    if not isinstance(daily, dict):
        return {}
    cleaned_daily = copy.deepcopy(daily)
    for day in (cleaned_daily or {}).values():
        if not isinstance(day, dict):
            continue
        for user in (day.get("by_user") or {}).values():
            if isinstance(user, dict):
                user["messages"] = _sanitize_memory_entries(user.get("messages", []))
                user["message_count"] = len(user["messages"])
    return cleaned_daily

def _load_json(path: Path, default: dict) -> dict:
    if not path or not path.exists():
        return copy.deepcopy(default)
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else copy.deepcopy(default)
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(default)

def _save_json_atomic(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    os.replace(str(tmp), str(path))

def _append_global_user_daily_message(user_memory_path, chat: dict, entry: dict, max_messages_per_user=300):
    if not user_memory_path or entry.get("role") != "user":
        return
    entry = copy.deepcopy(entry)
    entry["content"] = sanitize_message_content(entry.get("content", ""))
    if not entry["content"]:
        return
    key = _user_key(entry)
    if not key or key == "unknown":
        return

    path = Path(user_memory_path)
    data = _load_json(path, {"updated_at": _now_iso(), "daily": {}})
    day_key = _message_date(entry)
    day = data.setdefault("daily", {}).setdefault(day_key, {"by_user": {}, "updated_at": _now_iso()})
    user = day.setdefault("by_user", {}).setdefault(
        key,
        {
            "name": entry.get("sender", ""),
            "wxid": entry.get("sender_wxid", ""),
            "chats": {},
            "updated_at": _now_iso(),
        },
    )
    if entry.get("sender"):
        user["name"] = entry.get("sender")
    if entry.get("sender_wxid"):
        user["wxid"] = entry.get("sender_wxid")

    chat_key = str(chat.get("chat_hash") or chat.get("chat") or "unknown")
    chat_data = user.setdefault("chats", {}).setdefault(
        chat_key,
        {
            "chat": chat.get("chat", ""),
            "chat_hash": chat.get("chat_hash", ""),
            "is_group": bool(chat.get("is_group", False)),
            "message_count": 0,
            "messages": [],
            "summary": "",
            "updated_at": _now_iso(),
        },
    )
    chat_data["chat"] = chat.get("chat", chat_data.get("chat", ""))
    chat_data["chat_hash"] = chat.get("chat_hash", chat_data.get("chat_hash", ""))
    chat_data["is_group"] = bool(chat.get("is_group", chat_data.get("is_group", False)))

    item = {
        "time": entry.get("time", ""),
        "sender": entry.get("sender", ""),
        "content": entry.get("content", ""),
    }
    if entry.get("message_id"):
        item["message_id"] = entry.get("message_id")
    existing = {_message_fingerprint(message) for message in chat_data.get("messages", [])}
    if _message_fingerprint(entry) not in existing:
        chat_data["messages"].append(item)
        chat_data["message_count"] = int(chat_data.get("message_count") or 0) + 1
        chat_data["messages"] = chat_data["messages"][-max_messages_per_user:]

    chat_data["updated_at"] = _now_iso()
    user["updated_at"] = _now_iso()
    day["updated_at"] = _now_iso()
    data["updated_at"] = _now_iso()
    _save_json_atomic(path, data)

def _select_user_daily_memory(user_memory_path, chats: list[dict]) -> dict:
    data = _load_json(Path(user_memory_path), {"daily": {}})
    wanted = set()
    for chat in chats:
        for message in chat.get("messages", []) or []:
            key = str(message.get("sender_wxid") or message.get("sender") or "").strip()
            if key:
                wanted.add(key)
    if not wanted:
        return {}

    selected = {"daily": {}}
    for day_key, day in (data.get("daily") or {}).items():
        users = {}
        for user_key, user in (day.get("by_user") or {}).items():
            if user_key in wanted:
                users[user_key] = user
        if users:
            selected["daily"][day_key] = {"by_user": users, "updated_at": day.get("updated_at", "")}
    return selected

def update_memory(chat_ref, messages, reply=None, is_group=False, chat_name=None, store: ChatMemoryStore | None = None):
    store = store or ChatMemoryStore()
    chat = _chat_from_ref(chat_ref, messages, is_group=is_group, chat_name=chat_name)
    memory = store.load(chat)
    recent = list(memory.get("recent_messages", []))
    seen = {_message_fingerprint(item) for item in recent}

    for message in messages or []:
        entry = _message_to_memory_entry(message)
        if entry is None:
            continue
        fingerprint = _message_fingerprint(entry)
        if fingerprint in seen:
            continue
        recent.append(entry)
        seen.add(fingerprint)
        _append_daily_message(memory, chat, entry, user_memory_path=store.user_memory_path)

    if reply and str(reply.get("content", "")).strip():
        content = str(reply.get("content", "")).strip()
        if "_send_success" in reply:
            status = "已发送" if reply["_send_success"] else "未成功发送"
            content = f"[{status}] {content}"
        entry = {
            "role": "assistant",
            "sender": "bot",
            "content": content,
            "time": _now_iso(),
            "send_success": reply.get("_send_success"),
        }
        fingerprint = _message_fingerprint(entry)
        if fingerprint not in seen:
            recent.append(entry)
            _append_daily_message(memory, chat, entry, user_memory_path=store.user_memory_path)

    memory["recent_messages"] = recent
    store.save(chat, memory)

def replace_recent_memory(chat_ref, messages, is_group=False, chat_name=None, store: ChatMemoryStore | None = None):
    """Use a database snapshot as the current recent memory for one chat."""
    store = store or ChatMemoryStore()
    chat = _chat_from_ref(chat_ref, messages, is_group=is_group, chat_name=chat_name)
    memory = store.load(chat)
    recent = []
    seen = set()

    for message in messages or []:
        entry = _message_to_memory_entry(message)
        if entry is None:
            continue
        fingerprint = _message_fingerprint(entry)
        if fingerprint in seen:
            continue
        recent.append(entry)
        seen.add(fingerprint)
        _append_daily_message(memory, chat, entry, user_memory_path=store.user_memory_path)

    memory["recent_messages"] = recent[-store.max_recent :]
    store.save(chat, memory, summarize_fn=lambda summary, overflow, chat: summary)

def _format_messages_for_summary(messages: list[dict]) -> str:
    lines = []
    for item in messages:
        sender = item.get("sender") or item.get("role") or "?"
        content = str(item.get("content", "")).strip()
        time_text = item.get("time", "")
        if content:
            prefix = f"{time_text} {sender}".strip()
            lines.append(f"- {prefix}: {content}")
    return "\n".join(lines)

def _fallback_summary(existing_summary: str, messages: list[dict], exc: Exception) -> str:
    snippets = []
    for item in messages[-5:]:
        sender = item.get("sender") or item.get("role") or "?"
        content = str(item.get("content", "")).strip()
        if content:
            snippets.append(f"{sender}: {content[:60]}")
    note = "；".join(snippets)
    reason = f"摘要失败: {type(exc).__name__}"
    parts = [part for part in [existing_summary.strip(), reason, note] if part]
    return "\n".join(parts)

def summarize_memory_with_llm(existing_summary: str, messages: list[dict], chat: dict) -> str:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env", override=False)
    from reply_worker import call_llm_with_usage, load_llm_config

    chat_type = "群聊" if chat.get("is_group") else "私聊"
    prompt = f"""请把以下微信会话历史更新为“结构化长期记忆档案”，用中文，细节要足够可用，不要压缩成空泛短句。
不要输出 JSON，不要编造信息。允许 800-1500 字；如果信息很多，可以更长。

请使用下面的 Markdown 结构，并尽量写具体：

## 长期事实
- 只记录稳定、反复出现或对后续回复有用的信息。

## 人物画像
- 按用户分别写：谁说了什么、关注什么、偏好/雷点/表达习惯是什么。

## 进行中事项
- 记录尚未解决的问题、计划、待跟进话题。过期或一次性闲聊不要长期挂起。

## 回复注意
- 记录以后回复这个聊天框/这些用户时要注意的语气、禁忌、上下文。

## 最近状态
- 记录最近一段聊天正在发生什么，必须带具体人名和具体内容。

会话: {chat.get('chat', '')} ({chat_type})
已有长期记忆:
{existing_summary or '无'}

待压缩消息:
{_format_messages_for_summary(messages)}

更新后的结构化长期记忆档案:"""
    config = load_llm_config()
    result = call_llm_with_usage(prompt, config, log_func=None)
    if result.usage:
        from token_usage import DEFAULT_TOKEN_USAGE_FILE, record_token_usage

        record_token_usage(
            DEFAULT_TOKEN_USAGE_FILE,
            result.usage,
            source="system.memory_summarize",
            model=getattr(config, "model", ""),
        )
    return result.content.strip()


def enrich_pending_with_memory(pending: dict, store: ChatMemoryStore | None = None) -> dict:
    store = store or ChatMemoryStore()
    enriched = copy.deepcopy(pending)
    for chat in enriched.get("chats", []):
        chat["memory"] = store.load(chat)
    user_daily = _select_user_daily_memory(store.user_memory_path, enriched.get("chats", []))
    if user_daily:
        for chat in enriched.get("chats", []):
            chat["user_daily_memory"] = user_daily.get("daily", {})
    return enriched


def update_memory_after_replies(pending: dict, replies: list[dict], store: ChatMemoryStore | None = None):
    store = store or ChatMemoryStore()
    replies_by_key = {}
    for reply in replies:
        if reply.get("skip", False):
            continue
        if reply.get("_send_success") is False:
            continue
        replies_by_key.setdefault(memory_key(reply), []).append(reply)

    for chat in pending.get("chats", []):
        key = memory_key(chat)
        chat_replies = list(replies_by_key.get(key, []))
        if not chat_replies:
            chat_replies = [
                item
                for item in replies
                if not item.get("skip", False)
                and item.get("_send_success") is not False
                and item.get("chat") == chat.get("chat")
                and bool(item.get("is_group", chat.get("is_group", False))) == bool(chat.get("is_group", False))
            ]

        update_memory(chat, chat.get("messages", []), store=store)
        for reply in chat_replies:
            update_memory(chat, [], reply=reply, store=store)
