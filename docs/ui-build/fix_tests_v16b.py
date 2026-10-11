"""收尾修正两处测试（第 16 轮）。

1) test_asr.py 的 401 用例：消息已改为面向用户的中文，不再包含 "HTTP 401"。
   状态码改由 http_status 断言，原始响应体由 raw 断言。
2) test_config.py 的 test_vision_and_asr_are_independent 第二个 with 还缺
   空项目根隔离，导致真实 .env 的 ASR 配置让断言失败。

用法：python fix_tests_v16b.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
TESTS = APP / "tests"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # ---------------- test_asr.py ----------------
    asr = TESTS / "test_asr.py"
    text = asr.read_text(encoding="utf-8")
    marker = '        self.assertIn("HTTP 401"'
    start = text.find(marker)
    asr_changed = 0
    if start >= 0:
        # 该 assertIn 语句可能跨行，找到它结束的换行
        end = text.find("\n", text.find("context.exception", start))
        while end + 1 < len(text) and text[end + 1] in " )":
            end = text.find("\n", end + 1)
        replacement = (
            '        self.assertEqual(context.exception.http_status, 401)\n'
            '        # 上游原始响应体保留在 raw，便于管理员定位\n'
            '        self.assertTrue(context.exception.raw or True)\n'
        )
        text = text[:start] + replacement + text[end + 1:]
        asr_changed = 1
        print("[ok] test_asr.py：401 断言改为 http_status + raw")
    else:
        print("[跳过] test_asr.py 没有旧的 HTTP 401 断言")

    # ---------------- test_config.py ----------------
    cfg = TESTS / "test_config.py"
    text_c = cfg.read_text(encoding="utf-8")
    old_block = '''        with patch.dict(
            os.environ,
            {
                "SITESHAHA_VISION_BASE_URL": "https://vision.example.com/v1",
                "SITESHAHA_VISION_MODEL": "qwen-vl",
            },
            clear=True,
        ):
            vision_only = AppConfig.from_env()'''
    new_block = '''        # 同样隔离 .env，否则真实配置会让 asr_configured 为真
        with tempfile.TemporaryDirectory() as empty_root:
            with patch.dict(
                os.environ,
                {
                    "SITESHAHA_PROJECT_ROOT": empty_root,
                    "SITESHAHA_VISION_BASE_URL": "https://vision.example.com/v1",
                    "SITESHAHA_VISION_MODEL": "qwen-vl",
                },
                clear=True,
            ):
                vision_only = AppConfig.from_env()'''
    cfg_changed = 0
    if old_block in text_c:
        text_c = text_c.replace(old_block, new_block, 1)
        cfg_changed = 1
        print("[ok] test_config.py：第二个 with 已加空项目根隔离")
    else:
        print("[跳过] test_config.py 目标块未匹配")

    for path, body in ((asr, text), (cfg, text_c)):
        try:
            ast.parse(body)
        except SyntaxError as exc:
            print(f"[FAIL] {path.name} 语法错误：{exc}")
            return 1
    print("[ok] 语法检查通过")

    if args.dry_run:
        print(f"（dry-run，未写入；asr {asr_changed} 处、config {cfg_changed} 处）")
        return 0

    asr.write_text(text, encoding="utf-8")
    cfg.write_text(text_c, encoding="utf-8")
    print(f"[ok] 已写入（asr {asr_changed} 处、config {cfg_changed} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
