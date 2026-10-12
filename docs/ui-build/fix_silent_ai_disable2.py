"""补完「静默关闭」诊断（第 22 轮 P0）。

上一次两处没落：
  1. /healthz 的 reason 字段（锚点缩进/空行格式不对）
  2. _warn_about_disabled_ai 只被调用、没被定义（webapp 里那句其实会抛异常被吞掉）

本次按实际文件格式精确落位，并复验。

用法：python fix_silent_ai_disable2.py
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
CONFIG = APP / "sitesaha" / "config.py"
WEBAPP = APP / "webapp.py"

WARN_FUNC = '''

def _warn_about_disabled_ai(config) -> None:
    """AI 能力未就绪时打印醒目警告。

    为什么需要：这个失败以前是无声的 —— 页面只显示「未连接模型」，
    看不出是密钥缺失、被环境变量覆盖，还是模型名写错。
    本轮排查时就因为环境变量静默覆盖 .env，白找了一圈。
    """
    if config.llm_mode != "off" and config.model_configured and config.vision_configured:
        return

    print("!" * 66)
    print("警告：AI 能力未全部就绪")
    for feature in ("model", "vision", "asr"):
        reason = config.unavailable_reason(feature)
        if reason:
            print("  · " + feature + ": " + reason)
    if ENV_OVERRIDES:
        print("  以下外部环境变量覆盖了 .env 的同名配置：")
        for key in AI_KEYS:
            if key in ENV_OVERRIDES:
                shown = "***" if "KEY" in key else ENV_OVERRIDES[key]
                print("    - " + key + " = " + shown)
        print("  清除这些环境变量后重启，.env 才会生效。")
    print("!" * 66)
'''


def main() -> int:
    config = CONFIG.read_text(encoding="utf-8")
    webapp = WEBAPP.read_text(encoding="utf-8")
    applied = 0

    # ---- 1) 定义警告函数 ----
    if "_warn_about_disabled_ai" not in config:
        config = config.rstrip() + "\n" + WARN_FUNC
        applied += 1
        print("  [ok] _warn_about_disabled_ai 已定义")
    else:
        print("  [跳过] 警告函数已存在")

    try:
        ast.parse(config)
    except SyntaxError as exc:
        print(f"  [FAIL] config 语法：{exc}")
        return 1
    print("  [ok] config 语法通过")

    # ---- 2) /healthz 增加 reason ----
    if "vision_reason" in webapp:
        print("  [跳过] healthz 已有 reason")
    else:
        # 精确匹配（含空行）
        old = ('                    "vision_configured": self.services.config.vision_configured,\n'
               '\n'
               '                    "asr_configured": self.services.config.asr_configured,')
        new = ('                    "vision_configured": self.services.config.vision_configured,\n'
               '\n'
               '                    "asr_configured": self.services.config.asr_configured,\n'
               '\n'
               '                    # 为什么某项不可用 —— 让「静默关闭」可诊断\n'
               '                    "model_reason": self.services.config.unavailable_reason("model"),\n'
               '\n'
               '                    "vision_reason": self.services.config.unavailable_reason("vision"),')
        if old in webapp:
            webapp = webapp.replace(old, new, 1)
            applied += 1
            print("  [ok] /healthz 增加 model_reason / vision_reason")
        else:
            print("  [注意] 精确锚点未匹配，尝试正则")
            pattern = re.compile(
                r'("vision_configured":\s*self\.services\.config\.vision_configured,)\s*'
                r'("asr_configured")'
            )
            if pattern.search(webapp):
                webapp = pattern.sub(
                    r'\1\n\n                    "model_reason": '
                    r'self.services.config.unavailable_reason("model"),\n\n'
                    r'                    "vision_reason": '
                    r'self.services.config.unavailable_reason("vision"),\n\n'
                    r'                    \2',
                    webapp, count=1,
                )
                applied += 1
                print("  [ok] /healthz 增加 reason（正则方式）")
            else:
                print("  [FAIL] 两种锚点都没匹配")

    try:
        ast.parse(webapp)
    except SyntaxError as exc:
        print(f"  [FAIL] webapp 语法：{exc}")
        return 1
    print("  [ok] webapp 语法通过")

    CONFIG.write_text(config, encoding="utf-8")
    WEBAPP.write_text(webapp, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
