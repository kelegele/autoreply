"""一次性测试：初始化bot，跑一轮真实poll，看能否读到消息"""
import _path  # noqa: F401
import json
from pathlib import Path

from bot import load_config, FileExchange, WxChatBot

ROOT = Path(__file__).resolve().parent.parent

# 1. 加载配置
cfg = load_config()
db_cfg = cfg.get('db', {})
print(f"[1] Config loaded")
print(f"    wxid: {db_cfg.get('my_wxid', 'N/A')}")
print(f"    db_dir: {db_cfg.get('db_dir', 'N/A')}")
print(f"    mode: {cfg.get('mode')}")

# 2. 初始化bot（不启动主循环，只做一轮poll）
print(f"\n[2] Initializing bot...")
bot = WxChatBot()
print(f"    contacts loaded: {len(bot.uname2display)}")

# 3. 跑一轮poll
print(f"\n[3] Running one poll cycle...")
bot._poll_once()

# 4. 检查pending
exchange_dir = ROOT / "exchange"
pending_path = exchange_dir / "pending.json"
if pending_path.exists():
    data = json.loads(pending_path.read_text(encoding='utf-8'))
    print(f"    ✅ pending.json created!")
    print(f"    timestamp: {data.get('timestamp')}")
    for chat in data.get('messages', []):
        print(f"    📨 Chat: {chat['chat']} ({len(chat['messages'])} msgs)")
        for m in chat['messages'][:3]:
            print(f"       [{m['sender']}]: {m['content'][:60]}")
else:
    print(f"    ℹ️ No new messages (pending.json not created)")

# 5. 检查poll_state
state_path = ROOT / "state" / "poll_state.json"
if state_path.exists():
    state = json.loads(state_path.read_text(encoding='utf-8'))
    print(f"\n[4] poll_state: last_server_id={state.get('last_server_id')}")
else:
    print(f"\n[4] No poll_state yet")

print("\n✅ Test complete!")
