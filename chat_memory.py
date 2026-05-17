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
    def __init__(self, memory_dir=DEFAULT_MEMORY_DIR, max_recent=30):
        self.memory_dir = Path(memory_dir)
        self.max_recent = max_recent

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

    def save(self, chat: dict, memory: dict):
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        data = copy.deepcopy(memory)
        data["chat"] = chat.get("chat", data.get("chat", ""))
        data["is_group"] = bool(chat.get("is_group", data.get("is_group", False)))
        data["recent_messages"] = data.get("recent_messages", [])[-self.max_recent :]
        data["updated_at"] = _now_iso()

        path = self.path_for(chat)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(str(tmp), str(path))


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

        memory = store.load(chat)
        recent = list(memory.get("recent_messages", []))
        timestamp = _now_iso()
        for message in chat.get("messages", []):
            content = str(message.get("content", "")).strip()
            if not content:
                continue
            recent.append(
                {
                    "role": "user",
                    "sender": message.get("sender", ""),
                    "content": content,
                    "time": timestamp,
                }
            )

        if reply and str(reply.get("content", "")).strip():
            recent.append(
                {
                    "role": "assistant",
                    "sender": "bot",
                    "content": str(reply.get("content", "")).strip(),
                    "time": timestamp,
                }
            )

        memory["recent_messages"] = recent
        store.save(chat, memory)
