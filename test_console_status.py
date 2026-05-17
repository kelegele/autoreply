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


if __name__ == "__main__":
    tests = [
        test_console_status_updates_same_line,
        test_status_aware_handler_finishes_status_line_before_log,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
