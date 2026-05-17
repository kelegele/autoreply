"""
ga_reply.py — GA侧回复闭环工具
用法:
  python ga_reply.py --check          # 检查pending，输出JSON到stdout
  python ga_reply.py --reply JSON     # 写入reply.json
  python ga_reply.py --watch          # 持续监控模式，检测到pending输出内容
"""
import sys, json, time
from pathlib import Path

EXCHANGE_DIR = Path(__file__).parent / "exchange"
PENDING_PATH = EXCHANGE_DIR / "pending.json"
REPLY_PATH = EXCHANGE_DIR / "reply.json"


def check_pending():
    """读取pending.json，输出到stdout，不删除文件（由GA处理完reply后清）"""
    if not PENDING_PATH.exists():
        print(json.dumps({"status": "empty"}, ensure_ascii=False))
        return
    try:
        data = json.loads(PENDING_PATH.read_text(encoding='utf-8'))
        print(json.dumps({"status": "pending", "data": data}, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False))


def consume_pending():
    """读取并删除pending（消费模式，表示GA已取走）"""
    if not PENDING_PATH.exists():
        print(json.dumps({"status": "empty"}, ensure_ascii=False))
        return
    try:
        data = json.loads(PENDING_PATH.read_text(encoding='utf-8'))
        PENDING_PATH.unlink()  # 消费掉
        print(json.dumps({"status": "pending", "data": data}, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False))


def write_reply(reply_json):
    """写入reply.json"""
    try:
        if isinstance(reply_json, str):
            replies = json.loads(reply_json)
        else:
            replies = reply_json
        
        # 验证格式
        if not isinstance(replies, list):
            replies = [replies]
        
        for r in replies:
            assert "chat" in r and "content" in r, f"Invalid reply format: {r}"
        
        # 原子写入
        tmp = REPLY_PATH.with_suffix('.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(replies, f, ensure_ascii=False, indent=2)
        tmp.rename(REPLY_PATH)
        
        print(json.dumps({"status": "ok", "count": len(replies)}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False))


def watch_mode(interval=3):
    """持续监控模式：检测到pending就输出，等reply被消费后继续"""
    print(f"[watch] 监控中，间隔{interval}s...", file=sys.stderr)
    while True:
        if PENDING_PATH.exists():
            try:
                data = json.loads(PENDING_PATH.read_text(encoding='utf-8'))
                # 输出到stdout（被GA读取）
                print(json.dumps({"status": "pending", "data": data}, ensure_ascii=False), flush=True)
                # 等待GA处理：检测pending被删除或reply出现
                while PENDING_PATH.exists():
                    time.sleep(1)
                # 再等reply被bot消费
                while REPLY_PATH.exists():
                    time.sleep(1)
                print(json.dumps({"status": "cycle_done"}, ensure_ascii=False), flush=True)
            except Exception as e:
                print(json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False), flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "--check":
        check_pending()
    elif cmd == "--consume":
        consume_pending()
    elif cmd == "--reply":
        if len(sys.argv) < 3:
            print('{"status": "error", "error": "missing reply JSON"}')
            sys.exit(1)
        write_reply(sys.argv[2])
    elif cmd == "--watch":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        watch_mode(interval)
    else:
        print(f'Unknown command: {cmd}')
        print(__doc__)
