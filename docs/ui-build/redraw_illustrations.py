"""重画线稿插画 + 修应急页空框（第 25 轮）。

用户反馈三处「太垃圾」：

  1. 应急页有一个**空的红色大框** —— 根因：ill-emergency 符号实际不在文件里
     （上轮插入未保住），<use> 指向不存在的符号 → 渲染成空框。
     叠加我的错误设计：给 .ill-emergency 设了红边框 + 粉底，
     让一个「插画缺失」看起来像「报警框」。两处都要修。

  2. PPE 六件套插画不成形 —— 原来只有轮廓弧线和方块，
     标签还挤在一起显示「手套 护目镜」，看不出是什么。

  3. 临边防护插画不像防护示意 —— 栏杆画成了方框，挡脚板只是一条线。

本次全部重画，风格对齐：viewBox 240x130、currentColor、细线、中文标注。

用法：python redraw_illustrations.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
TIERS = BUILD / "v16_tiers.css"

# ---------------------------------------------------------------------------
# 1) 临边防护：楼板 + 立杆 + 上/中栏杆 + 挡脚板 + 尺寸标注
# ---------------------------------------------------------------------------
ILL_EDGE = '''  <symbol id="ill-edge" viewBox="0 0 240 130">
    <!-- 楼板 / 作业面 -->
    <path d="M6 98h150v16H6z"/>
    <path d="M6 98h150"/>
    <!-- 两根立杆 -->
    <path d="M118 40v74M196 40v74"/>
    <!-- 上栏杆（1.2m） -->
    <path d="M108 46h96"/>
    <!-- 中栏杆 -->
    <path d="M108 70h96"/>
    <!-- 挡脚板 ≥180mm -->
    <path d="M108 88h96M108 98h96"/>
    <!-- 尺寸标注 -->
    <path d="M212 46v52"/>
    <path d="M206 46h12M206 98h12"/>
    <text x="150" y="34" font-size="10" fill="currentColor">临边防护栏杆 1.2m</text>
    <text x="16" y="86" font-size="10" fill="currentColor">作业面</text>
    <text x="118" y="122" font-size="10" fill="currentColor">挡脚板 ≥180mm</text>
  </symbol>

'''

# ---------------------------------------------------------------------------
# 2) PPE 六件套：两行三列，每件一个可辨识的图形 + 独立标签
# ---------------------------------------------------------------------------
ILL_PPE = '''  <symbol id="ill-ppe" viewBox="0 0 240 130">
    <!-- 安全帽 -->
    <path d="M17 46a15 15 0 0 1 30 0"/>
    <path d="M11 46h42"/>
    <path d="M32 31v15"/>
    <text x="18" y="63" font-size="10" fill="currentColor">安全帽</text>

    <!-- 护目镜 -->
    <circle cx="92" cy="42" r="10"/>
    <circle cx="118" cy="42" r="10"/>
    <path d="M102 42h6"/>
    <path d="M82 40l-8-5M128 40l8-5"/>
    <text x="92" y="63" font-size="10" fill="currentColor">护目镜</text>

    <!-- 防护手套 -->
    <path d="M172 44V30a4 4 0 0 1 8 0v12"/>
    <path d="M180 42V26a4 4 0 0 1 8 0v16"/>
    <path d="M188 44V30a4 4 0 0 1 8 0v12"/>
    <path d="M170 44h28v6a12 12 0 0 1-12 12h-4a12 12 0 0 1-12-12z"/>
    <text x="172" y="72" font-size="10" fill="currentColor">防护手套</text>

    <!-- 反光背心 -->
    <path d="M20 86l12-5h8l4 6 4-6h8l12 5v30H20z"/>
    <path d="M40 81v35M20 96h40"/>
    <text x="18" y="126" font-size="10" fill="currentColor">反光背心</text>

    <!-- 安全带 -->
    <path d="M96 82l10 9 10-9"/>
    <path d="M92 92h28l-4 24H96z"/>
    <path d="M92 98h28"/>
    <text x="92" y="126" font-size="10" fill="currentColor">安全带</text>

    <!-- 安全鞋 -->
    <path d="M172 112V92h14v12h16a8 8 0 0 1 8 8v4h-38z"/>
    <path d="M172 108h38"/>
    <text x="176" y="126" font-size="10" fill="currentColor">安全鞋</text>
  </symbol>

'''

# ---------------------------------------------------------------------------
# 3) 应急三步骤：停 / 撤 / 报
# ---------------------------------------------------------------------------
ILL_EMERGENCY = '''  <symbol id="ill-emergency" viewBox="0 0 240 130">
    <path d="M8 116h224"/>
    <!-- 1 停手 -->
    <path d="M34 96V74h6V60a4 4 0 0 1 8 0v14h4V56a4 4 0 0 1 8 0v18h4V62a4 4 0 0 1 8 0v16h4V70a4 4 0 0 1 8 0v18a14 14 0 0 1-14 14H48a14 14 0 0 1-14-14z"/>
    <path d="M26 46h44"/>
    <text x="26" y="38" font-size="10" fill="currentColor">1 停手</text>
    <text x="24" y="128" font-size="10" fill="currentColor">停止作业</text>
    <!-- 2 撤离 -->
    <circle cx="112" cy="60" r="6"/>
    <path d="M112 66v20M112 72l-9 8M112 72l9 8M112 86l-7 12M112 86l7 12"/>
    <path d="M132 76h30M152 68l10 8-10 8"/>
    <text x="104" y="38" font-size="10" fill="currentColor">2 撤离</text>
    <text x="100" y="128" font-size="10" fill="currentColor">撤到安全区</text>
    <!-- 3 报告 -->
    <rect x="184" y="72" width="34" height="26" rx="4"/>
    <path d="M192 86h18"/>
    <path d="M194 64a7 7 0 0 1 14 0"/>
    <path d="M201 54v6"/>
    <text x="182" y="38" font-size="10" fill="currentColor">3 报告</text>
    <text x="178" y="128" font-size="10" fill="currentColor">报告负责人</text>
  </symbol>

'''

TAG = re.compile(r"<symbol\b[^>]*id=\"(ill-[a-z]+)\"[^>]*>.*?</symbol>\s*", re.S)


def replace_symbol(body: str, name: str, markup: str) -> tuple[str, bool]:
    pattern = re.compile(
        rf'<symbol\b[^>]*id="{re.escape(name)}"[^>]*>.*?</symbol>\s*', re.S
    )
    if pattern.search(body):
        return pattern.sub(markup, body, count=1), True
    # 不存在就插到示意图区开头
    marker = "  <!-- ===== 示意图用（较大、线稿） ===== -->\n"
    if marker in body:
        return body.replace(marker, marker + "\n" + markup, 1), True
    return body, False


CSS_FIX = """
/* 修：应急插画原来被套上红边框 + 粉底，看起来像「报警框」。
   插画就是插画，用中性容器，不抢红警带的语义。 */
.ill-figure.ill-emergency {
  color: var(--brand-700);
  border: 1px solid var(--line);
  border-left-width: 1px;
  background: var(--surface-soft);
}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")
    applied = 0

    for name, markup in (("ill-edge", ILL_EDGE),
                         ("ill-ppe", ILL_PPE),
                         ("ill-emergency", ILL_EMERGENCY)):
        body, ok = replace_symbol(body, name, markup)
        if ok:
            applied += 1
            existed = f'id="{name}"' in body
            print(f"  [ok] {name} 已重画")
        else:
            print(f"  [FAIL] {name} 替换失败")
            return 1

    # 复验三个符号都在且各一份
    for name in ("ill-edge", "ill-ppe", "ill-emergency"):
        count = body.count(f'id="{name}"')
        if count != 1:
            print(f"  [FAIL] {name} 出现 {count} 次（应为 1）")
            return 1
    print("  [ok] 三个符号各 1 份")

    # 修应急插画容器样式
    old_style = """.ill-figure.ill-emergency {
  color: var(--brand-700);
  border-color: var(--risk-high);
  border-left-width: 4px;
  background: var(--risk-high-bg);
}"""
    if old_style in tiers:
        tiers = tiers.replace(old_style, CSS_FIX.strip(), 1)
        applied += 1
        print("  [ok] 应急插画改回中性容器（不再像报警框）")
    elif "插画就是插画" in tiers:
        print("  [跳过] 样式已修")
    else:
        print("  [注意] 未找到旧样式，跳过")

    if body.count(chr(92)):
        print("[FAIL] body 含反斜杠")
        return 1
    print("  [ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    TIERS.write_text(tiers, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
