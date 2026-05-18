import _path  # noqa: F401

from pathlib import Path

import yaml


def test_persona_uses_flerken_with_xiaozhe_style_not_identity():
    cfg = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    persona = cfg["persona"]

    assert "Flerken" in persona
    assert "不是小澈" in persona
    assert "强者感" in persona
    assert "温柔" in persona
    assert "护短" in persona
    assert "交易感" in persona
    assert "最后一层防线" in persona


def test_persona_avoids_catty_or_abusive_tone():
    cfg = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    persona = cfg["persona"]

    forbidden = ["喵", "猫味", "嘴臭", "毒舌", "自己没手机", "地震局值班"]
    for word in forbidden:
        assert word not in persona


if __name__ == "__main__":
    tests = [
        test_persona_uses_flerken_with_xiaozhe_style_not_identity,
        test_persona_avoids_catty_or_abusive_tone,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
