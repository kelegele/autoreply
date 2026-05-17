import copy
import json
import os
from datetime import datetime
from pathlib import Path

DEFAULT_TOKEN_USAGE_FILE = Path(__file__).parent / "state" / "token_usage.json"
TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _empty_stats():
    return {
        "updated_at": _now_iso(),
        "total": {
            "requests": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "reasoning_tokens": 0,
        },
        "by_chat": {},
        "by_source": {},
        "events": [],
    }


def _load(path: Path):
    if not path.exists():
        return _empty_stats()
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return _empty_stats()

    default = _empty_stats()
    for key, value in default.items():
        data.setdefault(key, value)
    for key, value in default["total"].items():
        data["total"].setdefault(key, value)
    return data


def _usage_numbers(usage: dict):
    details = usage.get("completion_tokens_details") or {}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "reasoning_tokens": int(details.get("reasoning_tokens") or usage.get("reasoning_tokens") or 0),
    }


def _chat_key(chat: dict):
    chat_hash = str(chat.get("chat_hash") or "").strip()
    if chat_hash:
        return chat_hash
    return f"{chat.get('chat', '')}|{bool(chat.get('is_group', False))}"


def _chat_weight(chat: dict):
    text = json.dumps(
        {
            "chat": chat.get("chat", ""),
            "messages": chat.get("messages", []),
        },
        ensure_ascii=False,
    )
    return max(1, len(text))


def _allocate_numbers(total_numbers: dict, weights: list[int]):
    total_weight = sum(weights) or len(weights) or 1
    allocations = []
    for index, weight in enumerate(weights):
        item = {}
        for field in TOKEN_FIELDS:
            value = total_numbers[field]
            if index == len(weights) - 1:
                item[field] = value - sum(previous[field] for previous in allocations)
            else:
                item[field] = int(round(value * weight / total_weight))
        allocations.append(item)
    return allocations


def _add_numbers(target: dict, numbers: dict):
    target["requests"] = int(target.get("requests") or 0) + 1
    for field in ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens"):
        target[field] = int(target.get(field) or 0) + int(numbers.get(field) or 0)


def _chat_record(chat: dict, allocation: str):
    return {
        "chat": chat.get("chat", ""),
        "chat_hash": chat.get("chat_hash", ""),
        "is_group": bool(chat.get("is_group", False)),
        "allocation": allocation,
        "requests": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
    }


def record_token_usage(
    path=DEFAULT_TOKEN_USAGE_FILE,
    usage=None,
    pending=None,
    source="reply",
    model="",
    max_events=500,
):
    if not usage:
        return None

    path = Path(path)
    data = _load(path)
    numbers = _usage_numbers(usage)
    chats = list((pending or {}).get("chats", []))
    allocation_mode = "exact" if len(chats) <= 1 else "estimated"
    event_chats = []

    _add_numbers(data["total"], numbers)

    if chats:
        weights = [_chat_weight(chat) for chat in chats]
        allocations = _allocate_numbers(numbers, weights)
        for chat, allocated in zip(chats, allocations):
            key = _chat_key(chat)
            record = data["by_chat"].setdefault(key, _chat_record(chat, allocation_mode))
            record["chat"] = chat.get("chat", record.get("chat", ""))
            record["chat_hash"] = chat.get("chat_hash", record.get("chat_hash", ""))
            record["is_group"] = bool(chat.get("is_group", record.get("is_group", False)))
            record["allocation"] = "estimated" if record.get("allocation") == "estimated" else allocation_mode
            _add_numbers(record, allocated)
            event_chats.append(
                {
                    "chat": chat.get("chat", ""),
                    "chat_hash": chat.get("chat_hash", ""),
                    "is_group": bool(chat.get("is_group", False)),
                    "allocation": allocation_mode,
                    "allocated_prompt_tokens": allocated["prompt_tokens"],
                    "allocated_completion_tokens": allocated["completion_tokens"],
                    "allocated_total_tokens": allocated["total_tokens"],
                }
            )
    else:
        by_source = data["by_source"].setdefault(
            source,
            {
                "requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "reasoning_tokens": 0,
            },
        )
        _add_numbers(by_source, numbers)

    data["events"].append(
        {
            "timestamp": _now_iso(),
            "source": source,
            "model": model,
            "usage": copy.deepcopy(usage),
            "chats": event_chats,
        }
    )
    data["events"] = data["events"][-max_events:]
    data["updated_at"] = _now_iso()

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    os.replace(str(tmp), str(path))
    return data
