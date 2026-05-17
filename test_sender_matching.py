from sender import find_text


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


if __name__ == "__main__":
    tests = [
        test_find_text_fuzzy_matches_ocr_damaged_chinese_chat_name,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
