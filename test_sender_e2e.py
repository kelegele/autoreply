"""
wxchatbot sender 端到端测试 v2 - 直接点击聊天列表
不再搜索，直接从左侧聊天列表找目标联系人点击
"""
import ctypes
ctypes.windll.user32.SetProcessDPIAware()

import sys, time

import ljqCtrl
import win32gui, win32con, win32process, win32api
import pyperclip
from ocr_utils import ocr_image
from PIL import ImageGrab

WX_HWND = 1510264
TARGET = '文件传输助手'

def _force_fg():
    """激活微信到前台"""
    SW_RESTORE = 9
    win32gui.ShowWindow(WX_HWND, SW_RESTORE)
    win32gui.SetWindowPos(WX_HWND, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
    time.sleep(0.05)
    fg = win32gui.GetForegroundWindow()
    if fg != WX_HWND:
        fg_tid, _ = win32process.GetWindowThreadProcessId(fg)
        my_tid = win32api.GetCurrentThreadId()
        if fg_tid != my_tid:
            ctypes.windll.user32.AttachThreadInput(my_tid, fg_tid, True)
            win32gui.SetForegroundWindow(WX_HWND)
            ctypes.windll.user32.AttachThreadInput(my_tid, fg_tid, False)
    win32gui.SetWindowPos(WX_HWND, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
    time.sleep(0.1)

def click_at(screenshot_x, screenshot_y):
    """截图坐标 → 屏幕坐标 → ljqCtrl.Click"""
    wx_rect = win32gui.GetWindowRect(WX_HWND)
    screen_x = wx_rect[0] + screenshot_x
    screen_y = wx_rect[1] + screenshot_y
    print(f"    click: 截图({screenshot_x:.0f},{screenshot_y:.0f}) → 屏幕({screen_x:.0f},{screen_y:.0f})")
    ljqCtrl.Click(screen_x, screen_y)

def ocr_and_find(img, keyword, x_min=0, x_max=400):
    """OCR截图，找目标文本，返回匹配列表"""
    tmp_path = r'F:\dev\GenericAgent\temp\wxchatbot\_tmp_screenshot.png'
    img.save(tmp_path)
    result = ocr_image(tmp_path)
    details = result.get('details', [])
    
    matches = []
    for d in details:
        t = d.get('text', '').strip()
        if t and len(t) > 1:
            bbox = d['bbox']
            cx = (bbox[0][0] + bbox[2][0]) / 2
            cy = (bbox[0][1] + bbox[2][1]) / 2
            print(f"    ({cx:.0f},{cy:.0f}) '{t}'")
            if t == keyword and x_min <= cx <= x_max:
                matches.append({'text': t, 'cx': cx, 'cy': cy})
    return matches

# ══════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════

wx_rect = win32gui.GetWindowRect(WX_HWND)
print(f"微信 hwnd={WX_HWND} WindowRect={wx_rect}")

# Step 0: 激活窗口
print("\n[0] 激活微信窗口")
_force_fg()
# 验证是否真的到前台了
fg = win32gui.GetForegroundWindow()
fg_title = win32gui.GetWindowText(fg)
print(f"  前台: hwnd={fg} title='{fg_title}' 是微信: {fg == WX_HWND}")
time.sleep(0.3)

# Step 1: 截图，找聊天列表里的目标
print("\n[1] 截图 + OCR找聊天列表目标")
_force_fg()
time.sleep(0.2)
wx_rect = win32gui.GetWindowRect(WX_HWND)
img = ImageGrab.grab(bbox=wx_rect)
print(f"  截图尺寸: {img.size}")

matches = ocr_and_find(img, TARGET, x_min=50, x_max=350)
if not matches:
    print(f"  ❌ 聊天列表未找到 '{TARGET}'")
    sys.exit(1)

# 选y最小的（最上面的匹配）
target = min(matches, key=lambda m: m['cy'])
print(f"  ✅ 找到: '{target['text']}' at ({target['cx']:.0f},{target['cy']:.0f})")

# Step 2: 点击目标
print("\n[2] 点击目标")
_force_fg()
time.sleep(0.1)
click_at(target['cx'], target['cy'])
time.sleep(0.8)

# Step 3: 截图验证是否进入了聊天
print("\n[3] 验证 + 找输入框")
_force_fg()
time.sleep(0.2)
wx_rect = win32gui.GetWindowRect(WX_HWND)
img2 = ImageGrab.grab(bbox=wx_rect)

# 找输入框 — 用ClientToScreen计算大致位置
cx, cy = win32gui.ClientToScreen(WX_HWND, (0, 0))
_, _, cw, ch = win32gui.GetClientRect(WX_HWND)
input_x = cx + cw * 0.5
input_y = cy + ch * 0.95
print(f"  输入框估算: ({input_x:.0f},{input_y:.0f})")

# 先点输入框激活
_force_fg()
ljqCtrl.Click(input_x, input_y)
time.sleep(0.3)

# Step 4: 粘贴+发送
print("\n[4] 粘贴+发送")
_force_fg()
test_msg = f"wxchatbot e2e test {time.strftime('%H:%M:%S')}"
pyperclip.copy(test_msg)
time.sleep(0.1)
ljqCtrl.Press('ctrl+v', staytime=0)
time.sleep(0.5)

_force_fg()
time.sleep(0.1)
ljqCtrl.Press('enter', staytime=0)
time.sleep(0.8)

print(f"\n✅ 发送完成: '{test_msg}'")
print("请检查微信文件传输助手是否收到！")
