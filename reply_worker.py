import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).parent
LOG_DIR = PROJECT_DIR / "logs"


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 120
    temperature: float | None = None


def chat_completions_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/v1/chat/completions"


def load_llm_config(env=None) -> LLMConfig:
    source = os.environ if env is None else env
    base_url = source.get("LLM_BASE_URL", "").strip()
    api_key = source.get("LLM_API_KEY", "").strip()
    model = source.get("LLM_MODEL", "").strip()
    timeout = int(source.get("LLM_TIMEOUT", "120"))
    temperature_raw = source.get("LLM_TEMPERATURE", "").strip()
    temperature = float(temperature_raw) if temperature_raw else None

    missing = [
        name
        for name, value in [
            ("LLM_BASE_URL", base_url),
            ("LLM_API_KEY", api_key),
            ("LLM_MODEL", model),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return LLMConfig(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout=timeout,
        temperature=temperature,
    )


def log_line(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line, flush=True)
    try:
        LOG_DIR.mkdir(exist_ok=True)
        log_file = LOG_DIR / f"reply_worker_{datetime.now():%Y%m%d}.log"
        with open(log_file, "a", encoding="utf-8") as file:
            file.write(line + "\n")
    except Exception:
        pass


def _json_pretty(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def post_json(url, headers, payload, timeout):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTP {exc.code}: {detail}") from exc
    return json.loads(data)


def call_llm(prompt: str, config: LLMConfig, post_json=post_json, log_func=log_line) -> str:
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    if config.temperature is not None:
        payload["temperature"] = config.temperature

    url = chat_completions_url(config.base_url)
    if log_func:
        log_func(f"LLM request URL: {url}")
        log_func(f"LLM model: {config.model}")
        log_func(f"LLM prompt:\n{prompt}")
        log_func(f"LLM request payload:\n{_json_pretty(payload)}")

    data = post_json(
        url,
        {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        payload,
        config.timeout,
    )
    if log_func:
        log_func(f"LLM raw response:\n{_json_pretty(data)}")
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected LLM response: {data}") from exc


def _load_fallback_phrases(key, default=None):
    """Load fallback phrases from config.yaml"""
    try:
        import yaml
        with open(PROJECT_DIR / "config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cfg.get(key, default or [])
    except Exception:
        return default or []


def _pick_fallback(chat_name, is_group, sender, phrase_list):
    """Create a fallback reply JSON for a single chat"""
    import random
    return {
        "chat": chat_name,
        "content": random.choice(phrase_list) if phrase_list else "我现在不方便回复",
        "is_group": is_group,
        "sender": sender,
        "skip": False,
    }


def run_once(reflect_module, config: LLMConfig, call_llm_func=call_llm) -> bool:
    task = reflect_module.check()
    if task is None:
        return False
    if task == "/exit":
        raise SystemExit(0)

    log_line(f"Reflect triggered, prompt {len(task)} chars")

    try:
        result = call_llm_func(task, config)
        log_line(f"LLM completed, result {len(result)} chars")
    except Exception as exc:
        err_msg = str(exc)
        log_line(f"ERROR {type(exc).__name__}: {err_msg}")
        # LLM unavailable (auth error, billing, network)
        if any(kw in err_msg.lower() for kw in ["401", "402", "403", "billing", "payment", "quota", "insufficient", "connection", "timeout", "refused"]):
            phrases = _load_fallback_phrases("fallback_unavailable")
            if phrases and hasattr(reflect_module, "_pending_chats"):
                import random
                replies = [_pick_fallback(c["chat"], c.get("is_group", False), c.get("sender", ""), phrases) for c in reflect_module._pending_chats]
                log_line(f"LLM unavailable, using fallback_unavailable for {len(replies)} chats")
                if hasattr(reflect_module, "on_done"):
                    reflect_module.on_done(json.dumps(replies, ensure_ascii=False))
                return True
        raise

    # Check if LLM result looks like a content policy refusal
    refusal_markers = ["i cannot", "i can't", "作为ai", "as an ai", "i'm unable", "抱歉", "无法", "不当", "inappropriate"]
    result_lower = result.lower()
    if any(marker in result_lower for marker in refusal_markers):
        phrases = _load_fallback_phrases("fallback_sensitive")
        if phrases and hasattr(reflect_module, "_pending_chats"):
            replies = [_pick_fallback(c["chat"], c.get("is_group", False), c.get("sender", ""), phrases) for c in reflect_module._pending_chats]
            log_line(f"LLM refused content, using fallback_sensitive for {len(replies)} chats")
            # Write fallback replies directly
            if hasattr(reflect_module, "on_done"):
                reflect_module.on_done(json.dumps(replies, ensure_ascii=False))
            return True

    if hasattr(reflect_module, "on_done"):
        reflect_module.on_done(result)
    return True


def run_loop(reflect_module, config: LLMConfig):
    interval = int(getattr(reflect_module, "INTERVAL", 5))
    once = bool(getattr(reflect_module, "ONCE", False))
    log_line(f"reply_worker started model={config.model} interval={interval}s")

    while True:
        try:
            ran = run_once(reflect_module, config)
        except SystemExit:
            log_line("reflect requested exit")
            return
        except Exception as exc:
            log_line(f"ERROR {type(exc).__name__}: {exc}")
            ran = False

        if once and ran:
            log_line("ONCE=True, exiting")
            return
        time.sleep(interval)


def main():
    load_dotenv(PROJECT_DIR / ".env", override=False)
    config = load_llm_config()

    import reflect_wxchatbot_reply as reflect_module

    if hasattr(reflect_module, "init"):
        reflect_module.init({})
    run_loop(reflect_module, config)


if __name__ == "__main__":
    main()
