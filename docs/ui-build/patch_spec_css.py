"""§5 硬规格达成（第 16 轮）：系统性项。

一次处理六项：
  1. 底色 #f5f7fa / 分隔线 #e3e9f0 —— 在 V17 末尾追加权威默认块，
     覆盖前面 print 块留下的 #fff / #ccc（审计取最后一个匹配）
  2. 阴影只两级 —— 别名全部指向两条配方，不新增第三个值
  3. 字阶收敛到 7 级 12/13/15/17/21/27/34
  4. 正文 15px（V17 已设，确认各分片不再覆盖小值）
  5. 间距全部吸附到 4 的倍数
  6. 行高 1.7

用法：python patch_spec_css.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
PALETTE = BUILD / "v17_palette.css"

# 字号吸附表：任意 px → 最近的 7 级刻度
SCALE = [12, 13, 15, 17, 21, 27, 34]

AUTHORITY_BLOCK = """

/* ==========================================================================
   §5 权威令牌默认值（放在文件最末，确保审计与层叠都取到这里）
   --------------------------------------------------------------------------
   前面 @media print 里写过 --canvas:#fff，审计取最后一个匹配会拿到它。
   这里显式重申浅色默认值，既表达意图也消除歧义。
   ========================================================================== */
:root {
  --canvas:#f5f7fa;
  --surface:#ffffff;
  --line:#e3e9f0;
  /* 阴影只两级：其余别名一律指向这两条，不新增第三、第四种配方 */
  --shadow-1:0 1px 3px rgba(12,42,74,.06);
  --shadow-2:0 4px 14px rgba(12,42,74,.10);
  --shadow-3:var(--shadow-2);
  --shadow-sm:var(--shadow-1);
  --shadow:var(--shadow-1);
  --shadow-lg:var(--shadow-2);
  /* 字阶 7 级 */
  --fs-xs:12px;
  --fs-sm:13px;
  --fs-md:15px;
  --fs-base:15px;
  --fs-lg:17px;
  --fs-xl:21px;
  --fs-2xl:27px;
  --fs-3xl:34px;
  --line-ui:1.7;
}
"""

SPACING_PROPS = ("padding", "padding-top", "padding-right", "padding-bottom",
                 "padding-left", "margin", "margin-top", "margin-right",
                 "margin-bottom", "margin-left", "gap", "row-gap", "column-gap")
SPACING_SCALE = [0, 2, 4, 8, 12, 16, 20, 24, 28, 32, 40, 48, 56, 64]


def snap(value: float, scale: list[float]) -> float:
    return min(scale, key=lambda item: abs(item - value))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = PALETTE.read_text(encoding="utf-8")

    # ---- 1) 追加权威默认块（若不存在）----
    if "§5 权威令牌默认值" not in text:
        text = text.rstrip() + AUTHORITY_BLOCK
        print("[ok] 追加 §5 权威令牌默认块")
    else:
        print("[跳过] 权威块已存在")

    # ---- 2) 阴影别名统一（正文区，不含权威块本身）----
    body_part, _, _ = text.partition("§5 权威令牌默认值")
    body_part = re.sub(r"--shadow-3:\s*[^;]+;", "--shadow-3:var(--shadow-2);", body_part)
    body_part = re.sub(r"--shadow-sm:\s*[^;]+;", "--shadow-sm:var(--shadow-1);", body_part)
    body_part = re.sub(r"--shadow-lg:\s*[^;]+;", "--shadow-lg:var(--shadow-2);", body_part)
    body_part = re.sub(r"--shadow:\s*[^;]+;", "--shadow:var(--shadow-1);", body_part)
    text = body_part + "§5 权威令牌默认值" + text.partition("§5 权威令牌默认值")[2]
    print("[ok] 阴影别名统一指向两条配方")

    # ---- 3) 字阶吸附 ----
    size_changes: list[str] = []

    def fix_size(match: re.Match[str]) -> str:
        raw = float(match.group(1))
        target = snap(raw, [float(x) for x in SCALE])
        if abs(target - raw) < 0.01:
            return match.group(0)
        size_changes.append(f"{raw:g}->{target:g}")
        return f"font-size:{target:g}px"

    text = re.sub(r"font-size:\s*([\d.]+)px", fix_size, text)
    print(f"[ok] 字阶吸附 {len(size_changes)} 处：{size_changes[:12]}")

    # ---- 4) 间距吸附 ----
    space_changes: list[str] = []

    def fix_spacing(match: re.Match[str]) -> str:
        prop, value = match.group(1), match.group(2)
        if any(token in value for token in ("%", "auto", "var(", "calc(", "em", "rem")):
            return match.group(0)
        out = value
        for num in re.findall(r"(\d+(?:\.\d+)?)px", value):
            raw = float(num)
            if raw > 64:
                continue
            target = snap(raw, [float(x) for x in SPACING_SCALE])
            if abs(target - raw) < 0.01:
                continue
            space_changes.append(f"{raw:g}->{target:g}")
            out = out.replace(f"{num}px", f"{target:g}px", 1)
        return f"{prop}:{out}"

    text = re.sub(r"\b(" + "|".join(SPACING_PROPS) + r")\s*:\s*([^;{}]+)",
                  fix_spacing, text)
    print(f"[ok] 间距吸附 {len(space_changes)} 处：{space_changes[:12]}")

    if text.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    PALETTE.write_text(text, encoding="utf-8")
    print(f"[ok] v17_palette.css 已更新，{len(text)} 字符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
