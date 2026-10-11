"""修正测试以适配第 16 轮的两处变更。

变更 1：ASR 错误改为结构化 ProviderError，文案改成面向用户的中文说明
        （原来直接把 "HTTP 401" 这类技术串抛给用户）。
变更 2：项目根新增 .env（第 16 轮 §2.3 由用户配置），AppConfig.from_env()
        会 _load_dotenv(root/.env)。而测试用 patch.dict(os.environ, {}, clear=True)
        只清 os.environ，清不掉 .env 文件 —— 所以「默认未配置」的断言不再成立。
        修法：把 SITESHAHA_PROJECT_ROOT 指向一个空的临时目录，让 _load_dotenv 落空。

用法：python fix_tests_v16.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
TESTS = APP / "tests"


def patch_asr(text: str) -> tuple[str, int]:
    count = 0

    old1 = '        self.assertIn("靠近麦克风", str(context.exception))'
    new1 = ('        # 第 16 轮：错误改为结构化 ProviderError，文案面向用户\n'
            '        self.assertIn("没有识别出文字", str(context.exception))\n'
            '        self.assertEqual(context.exception.code, "audio_no_text")\n'
            '        self.assertIn("靠近麦克风", context.exception.hint)')
    if old1 in text:
        text = text.replace(old1, new1, 1)
        count += 1

    old2 = '        self.assertIn("HTTP 401"'
    new2 = '        # 第 16 轮：401 映射为可操作说明，原始状态码保存在 http_status\n        self.assertIn("密钥无效", str(context.exception))\n        self.assertEqual(context.exception.code, "provider_unauthorized")\n        self.assertEqual(context.exception.http_status, 401)\n        self.assertIn("HTTP 401"'
    if old2 in text:
        text = text.replace(old2, new2, 1)
        count += 1

    old3 = '        self.assertIn("连接失败", str(context.exception))'
    new3 = ('        # 第 16 轮：连接失败也给结构化错误\n'
            '        self.assertIn("连接模型服务失败", str(context.exception))\n'
            '        self.assertEqual(context.exception.code, "provider_unreachable")')
    if old3 in text:
        text = text.replace(old3, new3, 1)
        count += 1

    return text, count


def patch_config(text: str) -> tuple[str, int]:
    """给两处「默认未配置」的断言加上空项目根隔离。"""
    count = 0

    old = '''    def test_asr_is_unconfigured_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = AppConfig.from_env()'''
    new = '''    def test_asr_is_unconfigured_by_default(self) -> None:
        # 隔离真实 .env：指向一个空的临时项目根，_load_dotenv 会落空。
        # 否则项目里那份已配好 ASR 的 .env 会让「默认未配置」不再成立。
        with tempfile.TemporaryDirectory() as empty_root:
            with patch.dict(
                os.environ, {"SITESHAHA_PROJECT_ROOT": empty_root}, clear=True
            ):
                config = AppConfig.from_env()'''
    if old in text:
        text = text.replace(old, new, 1)
        count += 1

    old2 = '''        with patch.dict(
            os.environ,
            {
                "SITESHAHA_VISION_BASE_URL": "https://vision.example.com/v1",
                "SITESHAHA_VISION_MODEL": "qwen-vl",
                "SITESHAHA_ASR_BASE_URL": "https://asr.example.com/v1",
                "SITESHAHA_ASR_MODEL": "whisper-1",
            },
            clear=True,
        ):
            config = AppConfig.from_env()'''
    new2 = '''        with tempfile.TemporaryDirectory() as empty_root:
            with patch.dict(
                os.environ,
                {
                    "SITESHAHA_PROJECT_ROOT": empty_root,
                    "SITESHAHA_VISION_BASE_URL": "https://vision.example.com/v1",
                    "SITESHAHA_VISION_MODEL": "qwen-vl",
                    "SITESHAHA_ASR_BASE_URL": "https://asr.example.com/v1",
                    "SITESHAHA_ASR_MODEL": "whisper-1",
                },
                clear=True,
            ):
                config = AppConfig.from_env()'''
    if old2 in text:
        text = text.replace(old2, new2, 1)
        count += 1

    return text, count


def isolate_vision_only(text: str) -> tuple[str, int]:
    """test_vision_and_asr_are_independent 的第二个 with 也要隔离。"""
    old = '''        with patch.dict(
            os.environ,
            {
                "SITESHAHA_VISION_BASE_URL": "https://vision.example.com/'''
    if old not in text:
        return text, 0
    start = text.find(old)
    # 找到这一段的 config = AppConfig.from_env() 结束处
    end = text.find("config = AppConfig.from_env()", start)
    if end < 0:
        return text, 0
    end += len("config = AppConfig.from_env()")
    segment = text[start:end]
    if "SITESHAHA_PROJECT_ROOT" in segment:
        return text, 0
    # 在该 with 的字典里插入 PROJECT_ROOT
    fixed = segment.replace(
        "            {\n",
        "            {\n                \"SITESHAHA_PROJECT_ROOT\": empty_root,\n",
        1,
    )
    indent = "        "
    fixed = (indent + "with tempfile.TemporaryDirectory() as empty_root:\n"
             + "\n".join(("    " + line) if line.strip() else line
                         for line in fixed.split("\n")))
    return text[:start] + fixed + text[end:], 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asr = TESTS / "test_asr.py"
    cfg = TESTS / "test_config.py"

    text_a = asr.read_text(encoding="utf-8")
    text_a, n_a = patch_asr(text_a)

    text_c = cfg.read_text(encoding="utf-8")
    text_c, n_c = patch_config(text_c)
    text_c, n_v = isolate_vision_only(text_c)

    print(f"test_asr.py    改动 {n_a} 处")
    print(f"test_config.py 改动 {n_c + n_v} 处（含隔离 {n_v} 处）")

    for path, text in ((asr, text_a), (cfg, text_c)):
        import ast
        try:
            ast.parse(text)
        except SyntaxError as exc:
            print(f"[FAIL] {path.name} 语法错误：{exc}")
            return 1

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0

    asr.write_text(text_a, encoding="utf-8")
    cfg.write_text(text_c, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
