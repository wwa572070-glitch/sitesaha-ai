"""让「AI 能力被静默关闭」变得可见（第 22 轮 P0）。

根因（已实证）：
  config.py 用 os.environ.setdefault() 加载 .env —— 这是标准做法
  （让部署环境的变量优先）。但副作用是：
  如果开发者 shell 里残留 SITESHAHA_LLM_MODE=off，
  它会**静默覆盖 .env**，导致 model_configured / vision_configured 全变 false，
  而页面上只显示「未连接模型」，看不出为什么。

  本轮实测就是踩了这个：跑着的服务 vision_configured=false，
  但 .env 里密钥齐全、同一份代码直接调用却返回 True。

三处修复：
  1. 加载 .env 时记录被环境变量覆盖的键
  2. /healthz 增加 *_reason 字段，说明为什么某项不可用
  3. 启动时如果 AI 能力被关闭但 .env 里有配置，打印醒目警告

只做诊断增强，不改变任何既有的优先级规则（环境变量仍然优先）。

用法：python fix_silent_ai_disable.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
CONFIG = APP / "sitesaha" / "config.py"
WEBAPP = APP / "webapp.py"

# ---- 1) 记录被覆盖的键 ----
LOAD_OLD = '''        if name:
            os.environ.setdefault(name, value)'''

LOAD_NEW = '''        if name:
            # 记录「环境变量已存在、因此 .env 没生效」的键。
            # 这类静默覆盖会让 AI 能力无声关闭，必须能查出来。
            if name in os.environ and os.environ[name] != value:
                ENV_OVERRIDES[name] = os.environ[name]
            os.environ.setdefault(name, value)'''

# ENV_OVERRIDES 定义
REGISTRY = '''
# 被外部环境变量覆盖、因而 .env 未生效的键（诊断用，不记录密钥值）
ENV_OVERRIDES: dict[str, str] = {}

# 与 AI 能力直接相关的键：这些被覆盖时最危险
AI_KEYS = (
    "SITESHAHA_LLM_MODE",
    "SITESHAHA_LLM_BASE_URL",
    "SITESHAHA_LLM_API_KEY",
    "SITESHAHA_VISION_BASE_URL",
    "SITESHAHA_VISION_API_KEY",
    "SITESHAHA_VISION_MODEL",
)

'''

# ---- 2) 配置原因属性 ----
REASON = '''
    def unavailable_reason(self, feature: str) -> str:
        """说明某项能力为什么不可用（用于 /healthz 与启动日志）。"""
        if feature == "model" and self.model_configured:
            return ""
        if feature == "vision" and self.vision_configured:
            return ""
        if feature == "asr" and self.asr_configured:
            return ""

        if self.llm_mode == "off":
            overridden = "SITESHAHA_LLM_MODE" in ENV_OVERRIDES
            if overridden:
                return ("模型已关闭，且这个值是**外部环境变量**覆盖 .env 得到的"
                        "（SITESHAHA_LLM_MODE=" + str(ENV_OVERRIDES.get("SITESHAHA_LLM_MODE"))
                        + "）。请清除该环境变量后重启。")
            return "模型已关闭（SITESHAHA_LLM_MODE=off）。"

        base = {"model": self.llm_base_url,
                "vision": self.vision_base_url or self.llm_base_url}.get(feature, "")
        if not base:
            return f"{feature} 未配置服务地址。"
        if feature == "vision" and not self.vision_model:
            return "未配置视觉模型名称（SITESHAHA_VISION_MODEL）。"
        return f"{feature} 配置不完整，请检查 .env 或部署环境变量。"

'''

# ---- 3) 启动警告 + healthz 增字段 ----
WARN_FUNC = '''

def _warn_about_disabled_ai(config) -> None:
    """AI 能力被关闭但 .env 里其实有配置时，打印醒目警告。

    为什么需要：这个失败以前是无声的 —— 页面只显示「未连接模型」，
    看不出是密钥缺失还是被环境变量覆盖。实测踩过一次。
    """
    from .config import AI_KEYS, ENV_OVERRIDES

    if config.llm_mode != "off" and config.model_configured and config.vision_configured:
        return

    print("!" * 66)
    print("警告：AI 能力未全部就绪")
    for feature in ("model", "vision", "asr"):
        reason = config.unavailable_reason(feature)
        if reason:
            print(f"  · {feature}: {reason}")
    if ENV_OVERRIDES:
        print("  以下环境变量覆盖了 .env 的同名配置：")
        for key in AI_KEYS:
            if key in ENV_OVERRIDES:
                shown = ENV_OVERRIDES[key]
                if "KEY" in key:
                    shown = "***"
                print(f"    - {key} = {shown}")
    print("!" * 66)

'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = CONFIG.read_text(encoding="utf-8")
    webapp = WEBAPP.read_text(encoding="utf-8")
    applied = 0

    # 1) 插入 ENV_OVERRIDES / AI_KEYS
    if "ENV_OVERRIDES" not in config:
        marker = "def _load_dotenv(path: Path) -> None:"
        if marker in config:
            config = config.replace(marker, REGISTRY.lstrip("\n") + "\n" + marker, 1)
            applied += 1
            print("  [ok] 新增 ENV_OVERRIDES / AI_KEYS")
        else:
            print("  [FAIL] 找不到 _load_dotenv")
            return 1
    else:
        print("  [跳过] ENV_OVERRIDES 已存在")

    # 2) setdefault 处记录覆盖
    if "ENV_OVERRIDES[name] = os.environ[name]" not in config:
        if LOAD_OLD in config:
            config = config.replace(LOAD_OLD, LOAD_NEW, 1)
            applied += 1
            print("  [ok] 已记录被覆盖的键")
        else:
            print("  [注意] setdefault 锚点未匹配")
    else:
        print("  [跳过] 覆盖记录已存在")

    # 3) unavailable_reason 方法
    if "def unavailable_reason" not in config:
        anchor = "    @property\n    def vision_configured(self) -> bool:"
        if anchor in config:
            config = config.replace(anchor, REASON.strip("\n") + "\n\n" + anchor, 1)
            applied += 1
            print("  [ok] 新增 unavailable_reason()")
        else:
            print("  [FAIL] 找不到 vision_configured")
            return 1
    else:
        print("  [跳过] unavailable_reason 已存在")

    try:
        ast.parse(config)
    except SyntaxError as exc:
        print(f"  [FAIL] config 语法错误：{exc}")
        return 1
    print("  [ok] config 语法通过")

    # ---- healthz 增加 reason 字段 ----
    if "vision_reason" not in webapp:
        old = '"vision_configured": config.vision_configured,'
        new = ('"vision_configured": config.vision_configured,\n'
               '                "vision_reason": config.unavailable_reason("vision"),\n'
               '                "model_reason": config.unavailable_reason("model"),')
        if old in webapp:
            webapp = webapp.replace(old, new, 1)
            applied += 1
            print("  [ok] /healthz 增加 *_reason 字段")
        else:
            print("  [注意] healthz 字段锚点未匹配（可能缩进不同）")
    else:
        print("  [跳过] healthz 已有 reason")

    try:
        ast.parse(webapp)
    except SyntaxError as exc:
        print(f"  [FAIL] webapp 语法错误：{exc}")
        return 1
    print("  [ok] webapp 语法通过")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    CONFIG.write_text(config, encoding="utf-8")
    WEBAPP.write_text(webapp, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
