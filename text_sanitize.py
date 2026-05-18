import re
import unicodedata

NON_TEXT_PLACEHOLDER = "[非文本消息，原始内容已过滤]"


def _control_ratio(text: str) -> float:
    if not text:
        return 0.0
    controls = sum(
        1
        for char in text
        if unicodedata.category(char) in {"Cc", "Cf"} and char not in "\n\r\t"
    )
    replacements = text.count("\ufffd")
    return (controls + replacements) / max(len(text), 1)


def looks_binary_like_text(value) -> bool:
    text = str(value or "")
    return bool(text) and (_control_ratio(text) > 0.08 or "\x00" in text or "\ufffd" in text)


def sanitize_message_content(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    original_binary_like = looks_binary_like_text(text)
    if original_binary_like:
        wxid_match = re.search(r"wxid_[A-Za-z0-9_]+\s*:\s*\n?(.*)", text, re.DOTALL)
        if wxid_match:
            candidate = wxid_match.group(1).strip()
            chars = []
            for char in candidate:
                if char == "\ufffd":
                    break
                if unicodedata.category(char) in {"Cc", "Cf"} and char not in "\n\r\t":
                    break
                chars.append(char)
            if chars:
                text = "".join(chars).strip()

    text = text.replace("\ufffd", " ")
    text = "".join(
        char if (char in "\n\r\t" or unicodedata.category(char) not in {"Cc", "Cf"}) else " "
        for char in text
    )
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*", "\n", text).strip()

    wxid_match = re.search(r"wxid_[A-Za-z0-9_]+\s*:\s*\n?(.*)", text, re.DOTALL)
    if wxid_match and wxid_match.group(1).strip():
        text = wxid_match.group(1).strip()

    if original_binary_like:
        readable_chars = re.findall(r"[\u4e00-\u9fffA-Za-z0-9@#_.,:;!?，。！？、（）()【】\[\]{}<>《》/\\+\-*=|`'\" \n]", text)
        text = "".join(readable_chars)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*", "\n", text).strip(" -_/\\|`'\"")

    return text or NON_TEXT_PLACEHOLDER
