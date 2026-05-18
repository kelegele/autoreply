import _path  # noqa: F401

from PIL import Image

from sender import find_text, is_chat_row_selected, strip_leading_at_mention


def _detail(text, x1=100, y1=100, x2=200, y2=130):
    return {
        "text": text,
        "bbox": [
            [x1, y1],
            [x2, y1],
            [x2, y2],
            [x1, y2],
        ],
    }


def test_find_text_fuzzy_matches_ocr_damaged_chinese_chat_name():
    details = [_detail("广州一齐局", x1=100, y1=140, x2=420, y2=180)]

    matches = find_text(details, "示例群聊", exact=False, x_max=500, y_min=120)

    assert len(matches) == 1
    assert matches[0]["text"] == "广州一齐局"

def test_strip_leading_at_mention_removes_group_at_prefix():
    msg = "@示例用户 @示例用户\u2005从成都走318到波密"

    assert strip_leading_at_mention(msg, "示例用户") == "从成都走318到波密"

def test_strip_leading_at_mention_keeps_non_matching_content():
    msg = "@别人 从成都走318到波密"

    assert strip_leading_at_mention(msg, "示例用户") == msg


def test_selected_chat_detection_samples_row_background_not_text_center():
    img = Image.new("RGB", (500, 260), (245, 245, 245))
    for x in range(20, 220):
        for y in range(130, 190):
            img.putpixel((x, y), (40, 200, 80))

    match = _detail("广州一齐局", x1=100, y1=145, x2=180, y2=170)
    match["cx"] = 140
    match["cy"] = 157
    for x in range(100, 181):
        for y in range(145, 171):
            img.putpixel((x, y), (20, 20, 20))

    assert is_chat_row_selected(img, match, list_width=220)


if __name__ == "__main__":
    tests = [
        test_find_text_fuzzy_matches_ocr_damaged_chinese_chat_name,
        test_strip_leading_at_mention_removes_group_at_prefix,
        test_strip_leading_at_mention_keeps_non_matching_content,
        test_selected_chat_detection_samples_row_background_not_text_center,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
