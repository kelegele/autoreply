"""调试：看确认弹窗OCR识别了什么文字"""
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

# 截图OCR看当前页面所有文字
img, details, rect = screenshot_ocr(hwnd)
w, h = img.size
print(f"截图 {w}x{h}")
print(f"\n所有OCR识别文字：")
for d in details:
    if not isinstance(d, dict):
        print(f"  [非dict] {d}")
        continue
    t = d.get('text', '').strip()
    if t:
        bbox = d['bbox']
        cx = (bbox[0][0] + bbox[2][0]) / 2
        cy = (bbox[0][1] + bbox[2][1]) / 2
        print(f"  '{t}' at ({cx:.0f},{cy:.0f})")
