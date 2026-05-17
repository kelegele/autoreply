# wxchatbot 进阶计划：Heartbeat + GA自动回复

> 创建时间: 2026-05-17
> 更新时间: 2026-05-17 v3（方案一改为秒级心跳reflect模块）
> 状态: 待实施

---

## 方案一：Heartbeat 机制

### 背景

GA 本身是**被动响应式**的（用户发消息→GA 回复），没有常驻进程。需要一个外部调度器定期"唤醒" GA，让它读取 `HEARTBEAT.md` 里的指令去干活。

**核心洞察**：heartbeat 本质上就是 GA 的 **reflect 模式**（watchdog+scheduled task），无需造新轮子，直接复用 reflect 基础设施。

参考: OpenClaw heartbeat (https://docs.openclaw.ai/zh-CN/gateway/heartbeat)

### 两种模式对比

| | OpenClaw Heartbeat | GA Reflect 模式 |
|---|---|---|
| 触发方式 | 定时(cron/interval) | 定时(scheduler) + 文件监控(watchdog) |
| 检测机制 | 轻量脚本检查条件 | `check()` 函数返回 prompt 或 None |
| 触发时 | 返回 prompt 字符串 | `check()` 返回 prompt 字符串 |
| 注入到 | 共享 Agent 会话 | 共享 Agent 会话（`agent.put_task()`） |
| 共享记忆 | ✅ | ✅ |
| 共享工具 | ✅ | ✅ |

**结论：heartbeat = 一个 reflect 模块。**

### 两层调度架构

```
心跳层（check）         每1-5秒        读文件+比时间戳    零成本（不调LLM）
    ↓
    99%: return None → 不唤醒 LLM
    ↓
    1%: task 到期 → return prompt → 唤醒 LLM
    ↓
任务层（LLM）          按task interval  执行具体任务      有token消耗
```

agentmain.py 源码关键行：
```python
# L242: sleep 间隔可自定义，最小1秒
time.sleep(getattr(mod, 'INTERVAL', 5))
# L243-247: check() 返回 None 则跳过，不消耗 LLM
task = mod.check()
if task is None: continue   # 静默跳过
```

### 架构设计

```
┌──────────────────────────────────────────────────────────────┐
│  agentmain.py --reflect reflect/heartbeat.py                  │
│                                                              │
│  ┌─────────────┐  每5秒   ┌──────────────┐                   │
│  │ check()     │ ────────→│ 读 state.json│                   │
│  │ (心跳层)    │          │ 读 HEARTBEAT  │                   │
│  │ 零LLM成本   │          │ 算到期tasks   │                   │
│  └──────┬──────┘          └──────────────┘                   │
│         │                                                    │
│    无到期→return None (静默)                                  │
│         │                                                    │
│    有到期→return prompt                                      │
│         ▼                                                    │
│  ┌─────────────┐  LLM执行  ┌──────────────┐                  │
│  │ agent       │ ────────→ │ 执行到期task  │                  │
│  │ (任务层)    │           │ 更新state.json│                  │
│  │ 有token消耗 │           │ 调用工具干活   │                  │
│  └─────────────┘           └──────────────┘                  │
└──────────────────────────────────────────────────────────────┘
```

### 实现文件

**`reflect/heartbeat.py`** — 核心模块

```python
# reflect/heartbeat.py
INTERVAL = 5        # 每5秒一次心跳
ONCE = False

HEARTBEAT_FILE = 'temp/heartbeat_project/HEARTBEAT.md'
STATE_FILE = 'temp/heartbeat_project/heartbeat_state.json'

def init(a):
    pass

def check():
    """每次心跳：解析 HEARTBEAT.md 里的 tasks，只触发到期的"""
    # 1. 读 HEARTBEAT.md（解析 tasks: 块中的 name/interval/prompt）
    # 2. 读 state.json（获取每个 task 的 last_run 时间戳）
    # 3. 计算哪些 task 到期了（now - last_run >= interval）
    # 4. 全部没到期 → return None（静默跳过，零成本）
    # 5. 有到期 → 拼接 prompt + 更新 state.json → return prompt
    pass

def on_done(result):
    """LLM 执行完后的回调（可选：记录日志等）"""
    pass
```

**`temp/heartbeat_project/HEARTBEAT.md`** — 用户编辑的任务清单

```markdown
# Heartbeat 任务清单

## 定时任务
tasks:
- name: wechat-pending-check
  interval: 30s
  prompt: "检查 wxchatbot/exchange/pending.json，如有未回复消息，生成回复并写入 reply.json"

- name: system-health
  interval: 5m
  prompt: "检查进程状态：微信窗口是否存活，bot.py 是否在运行，异常则记录"

- name: daily-brief
  interval: 6h
  prompt: "查看今天的日志和待办，给用户生成一份简要状态汇报"
```

**`temp/heartbeat_project/heartbeat_state.json`** — 持久化时间戳

```json
{
  "last_run": "2026-05-17T10:00:00",
  "task_states": {
    "wechat-pending-check": { "last_run": "2026-05-17T09:59:30" },
    "system-health": { "last_run": "2026-05-17T09:55:00" },
    "daily-brief": { "last_run": "2026-05-17T06:00:00" }
  }
}
```

### 实现计划（4 步）

| # | 步骤 | 说明 | 状态 |
|---|------|------|------|
| 1 | 创建 `reflect/heartbeat.py` | check() + init() + HEARTBEAT.md 解析 + state 管理 | ⏳ |
| 2 | 创建 `temp/heartbeat_project/` | HEARTBEAT.md + heartbeat_state.json 初始文件 | ⏳ |
| 3 | 端到端测试 | `python agentmain.py --reflect reflect/heartbeat.py` 验证秒级心跳 | ⏳ |
| 4 | 添加 wxchatbot 任务 | 在 HEARTBEAT.md 中添加微信 pending 检查等实际任务 | ⏳ |

### 关键设计决策

- **秒级心跳**：`INTERVAL = 5`，check() 只做文件读取+时间比较，< 1ms，零 LLM 成本
- **静默模式**：99% 的 check() 返回 None，不唤醒 LLM，不浪费 token
- **复用 reflect 基础设施**：不造新轮子，直接 `--reflect` 启动，共享 Agent 循环和记忆
- **用户友好**：用户只需编辑 HEARTBEAT.md 添加/修改任务，不需要动代码
- **启动命令**：`python agentmain.py --reflect reflect/heartbeat.py`

---

## 方案二：GA 自动回复转接（独立进程模式）

### 背景

当前 wxchatbot 的流程断在中间：
```
bot.py poll → pending.json → [手动写 reply.json] → bot.py 发送
                       ↑ 这里断开了
```

目标：让 pending.json 自动触发 GA 生成回复。

### 为什么必须用独立进程

❌ **不能注入主 GA 对话框**：agentmain.py 的 reflect 模式把 prompt 注入到**同一个 agent 实例**（`agent.put_task(task)`），LLM 的 history 会混杂用户的日常对话 + 微信消息，导致：
- 上下文污染：写代码时突然被注入"今晚吃啥"
- 优先级混淆：LLM 无法区分用户指令和微信消息
- 并发冲突：reflect 和用户输入共用 task_queue，互相排队

✅ **独立进程**：代码完全一样（`agentmain.py`），只是启动参数不同，拥有独立的对话历史。

### 独立 GA 进程 vs 主 GA

| 对比 | 主 GA（你用的） | wxchatbot GA（独立进程） |
|------|----------------|------------------------|
| 启动 | `python agentmain.py` | `python agentmain.py --task wxchatbot` |
| 输入 | 对话框打字 | 读 `input.txt` 文件 |
| 输出 | 显示在对话框 | 写 `output.txt` 文件 |
| 上下文/history | 你和 GA 的所有对话 | 只有微信消息和回复，完全干净 |
| LLM API | 共享同一个 key | 共享同一个 key |
| 并发 | 你说话时它在排队 | 独立进程，互不干扰 |

**核心：进程按"角色"分，不按"会话"分。100个微信群也只需要1个 wxchatbot GA 进程。**

### 架构设计

```
┌───────────┐  poll   ┌──────────────┐         ┌─────────────┐
│  微信 DB  │ ──────→ │   bot.py     │ ──────→ │ pending.json│
└───────────┘         │  (主循环)     │         └──────┬──────┘
                      └──────────────┘                │
                                                      ▼
┌───────────┐  send   ┌──────────────┐         ┌──────────────┐
│  微信窗口  │ ←────── │  bot.py      │ ←────── │ reply.json   │
│  (sender) │         │  _check_reply│         └──────┬───────┘
└───────────┘         └──────────────┘                │
                                                      ▼
                                            ┌─────────────────────┐
                                            │  wxchatbot GA 进程   │
                                            │  (独立agentmain.py)  │
                                            │                     │
                                            │  input.txt  ← watch │
                                            │  output.txt → reply │
                                            │                     │
                                            │  同时处理所有会话：   │
                                            │  📱张三→"火锅？"     │
                                            │  📱工作群→"已发"     │
                                            │  📱...98个其他会话   │
                                            └─────────────────────┘
```

### 实现计划（5 步）— 改为 reflect 模式方案

> **2026-05-17 实施**: 方案从 --task 改为 --reflect 模式，更简洁

| # | 步骤 | 说明 | 状态 |
|---|------|------|------|
| 1 | 创建 `reflect_wxchatbot_reply.py` | check() + on_done() + JSON提取 | ✅ 已完成 |
| 2 | 验证数据流闭环 | pending.json 格式适配 + reply.json 格式对齐 | ✅ 已验证 |
| 3 | 端到端测试 | 启动 bot.py + reflect 联调 | ⏳ 待测试 |
| 4 | persona 调优 | 根据实际回复效果调整 prompt | ⏳ |
| 5 | 部署上线 | 常驻运行 | ⏳ |

**启动命令**:
```bash
# 终端1: bot.py（轮询微信DB + 发送回复）
cd temp/wxchatbot && python bot.py

# 终端2: GA reflect（检测pending→生成回复→写reply.json）
cd F:\dev\GenericAgent && python agentmain.py --reflect temp/wxchatbot/reflect_wxchatbot_reply.py
```

| # | 步骤 | 说明 |
|---|------|------|
| 1 | 改造 `ga_reply.py` | `--watch` 模式检测到 pending 后，组装 prompt 写入 `exchange/input.txt` |
| 2 | 启动独立 GA 进程 | `python agentmain.py --task wxchatbot`，配置输入输出路径指向 exchange 目录 |
| 3 | 回复闭环 | GA 处理完写入 `exchange/output.txt` → `ga_reply.py` 解析后写入 `reply.json` |
| 4 | 上下文管理 | 实现 sliding window，history 过长时裁剪旧消息，保留最近 N 轮 |
| 5 | 端到端测试 | 发条微信→自动回复→确认收到 |

### prompt 模板（input.txt）

```
[WXCHATBOT] 你收到了以下微信新消息，请按 persona 生成自然、口语化的回复。
要求：
1. 回复要自然，像真人聊天
2. 每条消息单独回复
3. 输出格式：写入 temp/wxchatbot/exchange/reply.json，内容为 [{"chat":"会话名","content":"回复内容"}]
4. 写入后删除 temp/wxchatbot/exchange/pending.json

persona: 你是一个友好的聊天助手

消息内容：
{...pending.json 的内容...}
```

### 扩展性

| 会话规模 | 进程数 | 说明 |
|----------|--------|------|
| 1-100个会话 | 1个 wxchatbot GA | 单进程内 LLM 自动区分各会话 |
| 100+会话，延迟高 | 2-4个 wxchatbot GA | 按会话类型分组（私聊/群聊/工作群） |

---

## 两个方案的关联

```
Heartbeat (方案一)  ──秒级心跳──→  check()每5秒轮询，到期task触发LLM
                                    ↓
          HEARTBEAT.md 里的 wechat-pending-check task (30s间隔)
                                    ↓
wxchatbot 自动回复 (方案二)  ──独立进程──→  消息到达 → GA 生成回复 → 发出
```

- **方案一（heartbeat）**可以作为方案二的**补充**：在 HEARTBEAT.md 中添加 `wechat-pending-check` task（30s间隔），即使独立 GA 进程挂了，heartbeat 也能兜底发现 pending 消息
- **方案二（独立进程）**是实时回复的主力，延迟更低（消息到达即触发）
- 两者互补，不冲突

### 建议实施顺序

1. **先做方案一**（heartbeat）— 通用基础设施，秒级心跳 + HEARTBEAT.md 任务管理，立即可用
2. **再做方案二**（自动回复独立进程）— 在 heartbeat 之上叠加专用微信回复进程
