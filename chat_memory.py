import copy
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path


DEFAULT_MEMORY_DIR = Path(__file__).parent / "state" / "chat_memory"


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
    def __init__(self, memory_dir=DEFAULT_MEMORY_DIR, max_recent=50, summarize_fn=None):
        self.memory_dir = Path(memory_dir)
        self.max_recent = max_recent
        self.summarize_fn = summarize_fn

    def path_for(self, chat: dict) -> Path:
        return self.memory_dir / f"{memory_key(chat)}.json"

    def default_memory(self, chat: dict) -> dict:
        return {
            "chat": chat.get("chat", ""),
            "is_group": bool(chat.get("is_group", False)),
            "summary": "",
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
        data.setdefault("recent_messages", [])
        data.setdefault("updated_at", _now_iso())
        return data

    def save(self, chat: dict, memory: dict, summarize_fn=None):
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        data = copy.deepcopy(memory)
        data["chat"] = chat.get("chat", data.get("chat", ""))
        data["is_group"] = bool(chat.get("is_group", data.get("is_group", False)))
        recent = list(data.get("recent_messages", []))
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
    content = str(message.get("content", "")).strip()
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

    if reply and str(reply.get("content", "")).strip():
        entry = {
            "role": "assistant",
            "sender": "bot",
            "content": str(reply.get("content", "")).strip(),
            "time": _now_iso(),
        }
        fingerprint = _message_fingerprint(entry)
        if fingerprint not in seen:
            recent.append(entry)

    memory["recent_messages"] = recent
    store.save(chat, memory)

def replace_recent_memory(chat_ref, messages, is_group=False, chat_name=None, store: ChatMemoryStore | None = None):
    """Use a database snapshot as the current recent memory for one chat."""
    store = store or ChatMemoryStore()
    chat = _chat_from_ref(chat_ref, messages, is_group=is_group, chat_name=chat_name)
    memory = store.load(chat)
    memory["summary"] = ""
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
    from reply_worker import call_llm, load_llm_config

    chat_type = "群聊" if chat.get("is_group") else "私聊"
    prompt = f"""请把以下微信会话历史压缩为长期记忆摘要，用中文，保留人物关系、偏好、重要事实、未解决事项和最近情绪。
不要输出 JSON，不要编造信息，控制在 200 字以内。

会话: {chat.get('chat', '')} ({chat_type})
已有摘要:
{existing_summary or '无'}

待压缩消息:
{_format_messages_for_summary(messages)}

更新后的长期摘要:"""
    return call_llm(prompt, load_llm_config(), log_func=None).strip()


def enrich_pending_with_memory(pending: dict, store: ChatMemoryStore | None = None) -> dict:
    store = store or ChatMemoryStore()
    enriched = copy.deepcopy(pending)
    for chat in enriched.get("chats", []):
        chat["memory"] = store.load(chat)
    return enriched


def update_memory_after_replies(pending: dict, replies: list[dict], store: ChatMemoryStore | None = None):
    store = store or ChatMemoryStore()
    replies_by_key = {memory_key(reply): reply for reply in replies if not reply.get("skip", False)}

    for chat in pending.get("chats", []):
        key = memory_key(chat)
        reply = replies_by_key.get(key)
        if reply is None:
            reply = next(
                (
                    item
                    for item in replies
                    if not item.get("skip", False)
                    and item.get("chat") == chat.get("chat")
                    and bool(item.get("is_group", chat.get("is_group", False))) == bool(chat.get("is_group", False))
                ),
                None,
            )

        update_memory(chat, chat.get("messages", []), reply=reply, store=store)
