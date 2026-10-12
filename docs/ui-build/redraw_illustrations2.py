"""第二轮重画：提升造型准确度（第 26 轮，用户选 B 继续手写迭代）。

第一轮的问题是「能看懂但不好看」。本轮针对三处：

  1. PPE 六件套：给每件加**足量细节**让轮廓可辨识
     安全帽（帽壳+帽檐+顶筋）、护目镜（双镜片+鼻梁+镜腿）、
     手套（四指+掌+拇指）、反光背心（V 领+中缝+双反光条）、
     安全带（肩带+胸带+主带+腿环）、安全鞋（鞋帮+鞋头+系带）
  2. 临边防护：加**工人剪影**做比例参照，栏杆分上/中/挡脚板三层，
     尺寸线标注 1.2m
  3. 应急三步骤：手的造型改准，人物加动作线

统一约束：viewBox 240x130、currentColor、stroke-width 由容器给、中文标注 10px。

用法：python redraw_illustrations2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"

# ---------------------------------------------------------------------------
# 临边防护：楼板 + 工人剪影 + 三层栏杆 + 尺寸标注
# ---------------------------------------------------------------------------
EDGE = '''  <symbol id="ill-edge" viewBox="0 0 240 130">
    <path d="M8 96h140v18H8z"/>
    <path d="M8 96h140"/>
    <circle cx="52" cy="64" r="6"/>
    <path d="M52 70v14M52 76l-8 6M52 76l8 6M52 84l-6 12M52 84l6 12"/>
    <path d="M124 38v76M200 38v76"/>
    <path d="M112 44h96"/>
    <path d="M112 68h96"/>
    <path d="M112 88h96M112 96h96"/>
    <path d="M216 44v52"/>
    <path d="M210 44h12M210 96h12"/>
    <text x="18" y="90" font-size="10" fill="currentColor">作业面</text>
    <text x="126" y="32" font-size="10" fill="currentColor">临边防护栏杆 1.2m</text>
    <text x="112" y="124" font-size="10" fill="currentColor">挡脚板 ≥180mm</text>
  </symbol>

'''

# ---------------------------------------------------------------------------
# PPE 六件套：两行三列，每件带足量细节
# ---------------------------------------------------------------------------
PPE = '''  <symbol id="ill-ppe" viewBox="0 0 240 130">
    <path d="M24 46a20 20 0 0 1 40 0"/>
    <path d="M15 46h58"/>
    <path d="M44 26v20"/>
    <path d="M31 29v17M57 29v17"/>
    <text x="20" y="64" font-size="10" fill="currentColor">安全帽</text>

    <rect x="96" y="33" width="21" height="17" rx="7"/>
    <rect x="125" y="33" width="21" height="17" rx="7"/>
    <path d="M117 41h8"/>
    <path d="M96 39l-11-6M146 39l11-6"/>
    <text x="98" y="64" font-size="10" fill="currentColor">护目镜</text>

    <path d="M180 47V33a4 4 0 0 1 8 0v14"/>
    <path d="M188 45V30a4 4 0 0 1 8 0v15"/>
    <path d="M196 45V32a4 4 0 0 1 8 0v13"/>
    <path d="M204 47V36a4 4 0 0 1 8 0v11"/>
    <path d="M180 47h32v5a13 13 0 0 1-13 13h-6a13 13 0 0 1-13-13z"/>
    <path d="M180 51l-8 3a4 4 0 0 0 2 7l6-2"/>
    <text x="182" y="76" font-size="10" fill="currentColor">防护手套</text>

    <path d="M24 92l13-7 7 9 7-9 13 7-4 6v24H28v-24z"/>
    <path d="M44 94v28"/>
    <path d="M28 102h32M28 112h32"/>
    <text x="22" y="128" font-size="10" fill="currentColor">反光背心</text>

    <path d="M108 88l12 13 12-13"/>
    <path d="M108 100h24"/>
    <path d="M106 100h28v9h-28z"/>
    <path d="M110 109v5a6 6 0 0 0 6 6M130 109v5a6 6 0 0 1-6 6"/>
    <text x="106" y="128" font-size="10" fill="currentColor">安全带</text>

    <path d="M182 114V92h13v10h13a9 9 0 0 1 9 9v3z"/>
    <path d="M182 109h35"/>
    <path d="M187 94h5M187 99h5"/>
    <text x="184" y="128" font-size="10" fill="currentColor">安全鞋</text>
  </symbol>

'''

# ---------------------------------------------------------------------------
# 应急三步骤：停手 / 撤离 / 报告
# ---------------------------------------------------------------------------
EMERGENCY = '''  <symbol id="ill-emergency" viewBox="0 0 240 130">
    <path d="M10 106h220"/>
    <path d="M36 100V78h5V62a3.5 3.5 0 0 1 7 0v16h4V58a3.5 3.5 0 0 1 7 0v20h4V64a3.5 3.5 0 0 1 7 0v14h4V72a3.5 3.5 0 0 1 7 0v14a16 16 0 0 1-16 16H52a16 16 0 0 1-16-16z"/>
    <path d="M26 50h46"/>
    <text x="27" y="40" font-size="10" fill="currentColor">1 停手</text>
    <text x="26" y="124" font-size="10" fill="currentColor">停止作业</text>

    <circle cx="112" cy="56" r="6"/>
    <path d="M112 62v17M112 68l-10 7M112 68l10 7M112 79l-8 12M112 79l8 12"/>
    <path d="M130 74h28"/>
    <path d="M150 66l9 8-9 8"/>
    <text x="104" y="40" font-size="10" fill="currentColor">2 撤离</text>
    <text x="100" y="124" font-size="10" fill="currentColor">撤到安全区</text>

    <rect x="182" y="70" width="36" height="30" rx="5"/>
    <path d="M191 86h18"/>
    <circle cx="200" cy="60" r="6"/>
    <path d="M200 66v-4"/>
    <text x="180" y="40" font-size="10" fill="currentColor">3 报告</text>
    <text x="176" y="124" font-size="10" fill="currentColor">报告负责人</text>
  </symbol>

'''


def replace(body: str, name: str, markup: str) -> tuple[str, bool]:
    import re
    pattern = re.compile(
        rf'<symbol\b[^>]*id="{re.escape(name)}"[^>]*>.*?</symbol>\s*', re.S
    )
    if not pattern.search(body):
        return body, False
    return pattern.sub(markup, body, count=1), True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    applied = 0

    for name, markup in (("ill-edge", EDGE), ("ill-ppe", PPE), ("ill-emergency", EMERGENCY)):
        body, ok = replace(body, name, markup)
        if not ok:
            print(f"  [FAIL] {name} 未找到，中止（不改动）")
            return 1
        applied += 1
        print(f"  [ok] {name} 已重画")

    if body.count(chr(92)):
        print("[FAIL] body 含反斜杠")
        return 1

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0

    BODY.write_text(body, encoding="utf-8")
    # 写完立刻读回断言 —— 上一轮就是这里丢的，必须复验
    check = BODY.read_text(encoding="utf-8")
    print()
    all_ok = True
    for name in ("ill-edge", "ill-ppe", "ill-emergency", "ill-scaffold"):
        defined = check.count(f'<symbol id="{name}"')
        used = check.count(f'href="#{name}"')
        state = "OK" if (defined == 1 and used == 1) else "**问题**"
        if defined != 1:
            all_ok = False
        print(f"  复验 {name:<16} 定义 {defined}  引用 {used}  {state}")
    if not all_ok:
        print("[FAIL] 复验不通过，不谎报成功")
        return 1
    print(f"\n[OK] 已写入并复验通过（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
