from sender import find_text, strip_leading_at_mention


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


if __name__ == "__main__":
    tests = [
        test_find_text_fuzzy_matches_ocr_damaged_chinese_chat_name,
        test_strip_leading_at_mention_removes_group_at_prefix,
        test_strip_leading_at_mention_keeps_non_matching_content,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
