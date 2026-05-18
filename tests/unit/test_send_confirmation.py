import _path  # noqa: F401


def test_send_with_db_confirmation_retries_until_message_appears_in_db():
    import bot

    send_calls = []
    confirm_calls = []

    class Logger:
        def info(self, message):
            pass

        def warning(self, message):
            pass

    class DbConfig:
        msg_db_path = "msg.db"
        msg_key_bytes = b"key"
        my_wxid = "wxid_me"
        my_display_name = "Flerken"

    def send_func(chat, content, at_name=None):
        send_calls.append((chat, content, at_name))
        return True

    def confirm_func(*args, **kwargs):
        confirm_calls.append((args, kwargs))
        return len(send_calls) >= 2

    ok = bot.send_with_db_confirmation(
        reply={"chat": "测试群", "chat_hash": "group123", "is_group": True, "sender": "", "content": "hello"},
        db_config=DbConfig(),
        uname2display={},
        logger=Logger(),
        send_func=send_func,
        confirm_func=confirm_func,
        max_send_attempts=5,
        confirm_checks=1,
        confirm_total_seconds=0,
    )

    assert ok is True
    assert len(send_calls) == 2
    assert len(confirm_calls) == 2


def test_send_with_db_confirmation_fails_after_five_unconfirmed_sends():
    import bot

    send_calls = []

    class Logger:
        def info(self, message):
            pass

        def warning(self, message):
            pass

    class DbConfig:
        msg_db_path = "msg.db"
        msg_key_bytes = b"key"
        my_wxid = "wxid_me"
        my_display_name = "Flerken"

    def send_func(chat, content, at_name=None):
        send_calls.append((chat, content, at_name))
        return True

    ok = bot.send_with_db_confirmation(
        reply={"chat": "测试群", "chat_hash": "group123", "is_group": True, "sender": "", "content": "hello"},
        db_config=DbConfig(),
        uname2display={},
        logger=Logger(),
        send_func=send_func,
        confirm_func=lambda *args, **kwargs: False,
        max_send_attempts=5,
        confirm_checks=1,
        confirm_total_seconds=0,
    )

    assert ok is False
    assert len(send_calls) == 5


if __name__ == "__main__":
    tests = [
        test_send_with_db_confirmation_retries_until_message_appears_in_db,
        test_send_with_db_confirmation_fails_after_five_unconfirmed_sends,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
