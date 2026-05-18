"""测试右键「不显示」流程：右键→不显示→我知道了"""
import _path  # noqa: F401
import ctypes
ctypes.windll.user32.SetProcessDPIAware()
import time
from sender import find_wechat_window, screenshot_ocr, force_foreground, click_at, find_text
import ljqCtrl

hwnd = find_wechat_window()
if not hwnd:
    print("❌ 未找到微信窗口")
    exit(1)

print(f"微信窗口: hwnd={hwnd}")
force_foreground(hwnd)
time.sleep(0.3)

# 截图OCR找文件传输助手
img, details, rect = screenshot_ocr(hwnd)
w, h = img.size
print(f"截图 {w}x{h}")

# 找聊天列表中的"文件传输助手"（x<30%）
target = None
for d in details:
    if not isinstance(d, dict):
        continue
    t = d.get('text', '').strip()
    if t == '文件传输助手':
        bbox = d['bbox']
        cx = (bbox[0][0] + bbox[2][0]) / 2
        cy = (bbox[0][1] + bbox[2][1]) / 2
        if cx < w * 0.3:
            target = {'text': t, 'cx': cx, 'cy': cy}
            print(f"  找到 '{t}' at ({cx:.0f},{cy:.0f})")

if not target:
    print("❌ 聊天列表中未找到文件传输助手")
    exit(1)

print(f"\n🎯 右键点击: '{target['text']}' at ({target['cx']:.0f},{target['cy']:.0f})")
force_foreground(hwnd)
click_at(hwnd, target['cx'], target['cy'], button='right')
time.sleep(0.5)

# 找右键菜单中的「不显示」
img2, details2, _ = screenshot_ocr(hwnd)
hide_hits = find_text(details2, '不显示', exact=False)
if not hide_hits:
    print("❌ 右键菜单没找到'不显示'")
    ljqCtrl.Press('esc', staytime=0)
    exit(1)

print(f"  找到 '不显示' at ({hide_hits[0]['cx']:.0f},{hide_hits[0]['cy']:.0f})")
force_foreground(hwnd)
click_at(hwnd, hide_hits[0]['cx'], hide_hits[0]['cy'])
time.sleep(0.5)

# 找二次确认弹窗中的「我知道了」
img3, details3, _ = screenshot_ocr(hwnd)
confirm_hits = find_text(details3, '我知道了', exact=False)
if confirm_hits:
    print(f"  找到 '我知道了' at ({confirm_hits[0]['cx']:.0f},{confirm_hits[0]['cy']:.0f})")
    force_foreground(hwnd)
    click_at(hwnd, confirm_hits[0]['cx'], confirm_hits[0]['cy'])
    print("✅ 点击了'我知道了'")
else:
    print("⚠️ 没找到'我知道了'确认按钮")

time.sleep(0.3)
print("\n✅ 测试完毕 - 请确认文件传输助手是否已从列表隐藏（但聊天记录还在）")
