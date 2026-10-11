"""把 /api/ask 接到 _answer_or_summary，让模型不可用时退回检索摘要（第 16 轮 §3.2）。

现状：/api/ask 直接调 engine.answer()，模型故障时异常冒到外层，
      实测泄漏过 "Expecting value: line 1 column 1 (char 0)"。
      已新增 _answer_or_summary 但还没被调用。

修法：改成调用 _answer_or_summary，并把 ProviderError 分支接上
      _write_provider_error，保证任何响应体都不含 Python 异常原文。

用法：python patch_ask_route.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
WEBAPP = APP / "webapp.py"

OLD = '''                answer = self.services.engine.answer(

                    question,

                    worker_role=worker_role,

                    training_context=training_context,

                )

                response_payload = answer_payload(question, answer)'''

NEW = '''                try:

                    response_payload = self._answer_or_summary(

                        question, worker_role, training_context

                    )

                except ProviderError as exc:

                    self._write_provider_error(exc)

                    return'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = WEBAPP.read_text(encoding="utf-8")
    if "_answer_or_summary(" in text.split("def _answer_or_summary")[1][:2000] and OLD not in text:
        print("[跳过] 路由已接线")
        return 0

    if OLD not in text:
        print("[FAIL] 找不到 /api/ask 的调用锚点")
        return 1

    text = text.replace(OLD, NEW, 1)
    print("[ok] /api/ask 改走 _answer_or_summary")

    # _answer_or_summary 的签名要接受 training_context
    sig_old = "    def _answer_or_summary(self, question: str, mode: str, worker_role: str) -> dict[str, Any]:"
    sig_new = ("    def _answer_or_summary(\n"
               "        self, question: str, worker_role: str = \"\", training_context: str = \"\"\n"
               "    ) -> dict[str, Any]:")
    if sig_old in text:
        text = text.replace(sig_old, sig_new, 1)
        print("[ok] 修正 _answer_or_summary 签名")

    call_old = "            answer = engine.answer(question, worker_role=worker_role)"
    call_new = ("            answer = engine.answer(\n"
                "                question, worker_role=worker_role, training_context=training_context\n"
                "            )")
    if call_old in text:
        text = text.replace(call_old, call_new, 1)
        print("[ok] 把 training_context 传进 engine.answer")

    try:
        ast.parse(text)
    except SyntaxError as exc:
        print(f"[FAIL] 语法错误：{exc}")
        return 1
    print("[ok] 语法通过")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    WEBAPP.write_text(text, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
