"""排查 vision_configured=false 的根因（第 22 轮 P0）。

现象：/healthz 返回 model_configured=false、vision_configured=false，
      但 .env 里确实有 SITESHAHA_VISION_API_KEY / SITESHAHA_VISION_MODEL。

本脚本只做只读诊断，不输出任何密钥值。

用法：python diagnose_vision_config.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(APP))


def mask(value: str | None) -> str:
    if not value:
        return "（未设置）"
    return f"已设置，长度 {len(value)}"


def main() -> int:
    print("=" * 78)
    print("一、.env 文件")
    print("=" * 78)
    env_file = APP / ".env"
    print(f"  路径: {env_file}")
    print(f"  存在: {env_file.is_file()}")
    if env_file.is_file():
        print(f"  大小: {env_file.stat().st_size} 字节")
        keys = []
        for line in env_file.read_text(encoding="utf-8").split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            keys.append(line.split("=")[0].strip())
        print(f"  键数: {len(keys)}")
        for name in ("SITESHAHA_LLM_API_KEY", "SITESHAHA_VISION_API_KEY",
                     "SITESHAHA_ASR_API_KEY", "SITESHAHA_VISION_MODEL",
                     "SITESHAHA_VISION_BASE_URL", "SITESHAHA_LLM_MODE"):
            mark = "有" if name in keys else "**没有**"
            print(f"    {mark:<10} {name}")

    print()
    print("=" * 78)
    print("二、当前进程环境变量（服务是否读到 .env）")
    print("=" * 78)
    for name in ("SITESHAHA_LLM_MODE", "SITESHAHA_VISION_API_KEY",
                 "SITESHAHA_VISION_MODEL", "SITESHAHA_VISION_BASE_URL",
                 "SITESHAHA_VISION_API_STYLE"):
        print(f"  {name:<32} {mask(os.environ.get(name))}")

    print()
    print("=" * 78)
    print("三、加载 .env 后的配置判定")
    print("=" * 78)
    try:
        import webapp
        services = webapp.build_services()
        config = services.config
    except Exception as exc:  # noqa: BLE001
        print(f"  构建失败：{type(exc).__name__}: {exc}")
        return 1

    for name in ("llm_mode", "llm_base_url", "llm_model", "llm_api_style",
                 "vision_base_url", "vision_model", "vision_api_style",
                 "asr_base_url", "asr_model"):
        if hasattr(config, name):
            value = getattr(config, name)
            if "key" in name:
                value = mask(str(value))
            print(f"  {name:<22} {value}")

    print()
    print("  --- 判定结果 ---")
    for name in ("model_configured", "vision_configured", "asr_configured"):
        if hasattr(config, name):
            value = getattr(config, name)
            print(f"  {name:<22} {value}")

    print()
    print("=" * 78)
    print("四、判定逻辑（源码）")
    print("=" * 78)
    source = (APP / "sitesaha" / "config.py").read_text(encoding="utf-8")
    import re
    for prop in ("model_configured", "vision_configured", "asr_configured"):
        match = re.search(
            rf"def {prop}\(self\)[^\n]*\n((?:\s+[^\n]*\n)+)", source
        )
        if match:
            print(f"  --- {prop} ---")
            for line in match.group(1).rstrip().split("\n"):
                print("  " + line)
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
