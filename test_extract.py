"""测试 _extract_replies 能否正确解析 reflect_logs 中的实际输出"""
import json, re, sys

# 从 reflect_logs 读取真实输出
with open('temp/reflect_logs/reflect_wxchatbot_reply_2026-05-17.log', 'r', encoding='utf-8') as f:
    log_content = f.read()

# 按 [05-17 06:XX] 分割成单独的 result
import re
chunks = re.split(r'\n(?=\[\d{2}-\d{2} \d{2}:\d{2}\])', log_content)

# 复制 _extract_replies 逻辑
def _extract_replies(text):
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
    return None

print(f"共 {len([c for c in chunks if c.strip()])} 个结果块\n")

for i, chunk in enumerate(chunks):
    chunk = chunk.strip()
    if not chunk:
        continue
    print(f"=== 块 {i+1} ===")
    # 截取前200字
    preview = chunk[:300].replace('\n', '\\n')
    print(f"预览: {preview}...")
    
    replies = _extract_replies(chunk)
    if replies:
        print(f"✅ 提取成功: {json.dumps(replies, ensure_ascii=False)}")
    else:
        print(f"❌ 提取失败")
    print()
