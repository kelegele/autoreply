import _path  # noqa: F401

import io
import logging


def test_console_status_updates_same_line():
    from bot import ConsoleStatusLine

    stream = io.StringIO()
    status = ConsoleStatusLine(stream)

    status.update("[22:11:52]  第559次轮询")
    status.update("[22:11:53]  第559次轮询.")

    output = stream.getvalue()
    assert "\r[22:11:52]  第559次轮询" in output
    assert "\r[22:11:53]  第559次轮询." in output
    assert "\n" not in output


def test_status_aware_handler_finishes_status_line_before_log():
    import bot

    stream = io.StringIO()
    old_status = bot.CONSOLE_STATUS
    bot.CONSOLE_STATUS = bot.ConsoleStatusLine(stream)
    try:
        handler = bot.StatusAwareStreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "new message", (), None)

        bot.CONSOLE_STATUS.update("loading")
        handler.emit(record)

        output = stream.getvalue()
    finally:
        bot.CONSOLE_STATUS = old_status

    assert "\rloading\nnew message\n" in output


def test_display_padding_accounts_for_chinese_width():
    from bot import display_width, pad_display

    assert display_width("群聊") == 4
    assert pad_display("群聊", 6) == "群聊  "

def test_chat_log_line_uses_aligned_columns():
    from bot import format_chat_log_line

    line = format_chat_log_line("群聊", "示例群聊", "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d", "2条待回复")

    assert line.startswith("  [群聊]")
    assert "[85c1..23f0]" in line
    assert " | 2条待回复" in line

def test_chat_log_line_does_not_render_empty_hash_brackets():
    from bot import format_chat_log_line

    line = format_chat_log_line("群聊", "示例群聊", "", "准备发送")

    assert "[]" not in line
    assert " | 准备发送" in line

def test_message_log_line_uses_separator_column():
    from bot import format_message_log_line

    line = format_message_log_line("示例用户", "这是一条需要预览的消息", sender_wxid="wxid_f", is_at=True)

    assert line.startswith("    - ")
    assert "示例用户(wxid_f) @我" in line
    assert " | 这是一条需要预览的消息" in line

if __name__ == "__main__":
    tests = [
        test_console_status_updates_same_line,
        test_status_aware_handler_finishes_status_line_before_log,
        test_display_padding_accounts_for_chinese_width,
        test_chat_log_line_uses_aligned_columns,
        test_chat_log_line_does_not_render_empty_hash_brackets,
        test_message_log_line_uses_separator_column,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
