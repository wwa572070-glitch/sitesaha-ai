"""按顺序把设计层注入 index_head.html 的 </style> 之前。

层序（后面的覆盖前面的）：
  1) V13 设计系统    —— 翠绿 + 深灰，重新定义令牌与组件
  2) V13 流程阶段    —— 首页五阶段的排版
  3) V13 布局        —— 单列阅读流、卡片与条目规则
  4) V13 暗色主题    —— V13 令牌的暗色版本，必须排在 V13 亮色之后

注意：V12 两层（靛蓝/琥珀）已被 V13 完全取代，不再注入。
它们留在样式表里只会让 900+ 条规则里大半是永远不会生效的死代码，
并且把颜色数从 101 抬到 190、字号档从 8 抬到 24 —— 那正是"看着乱"的工程根因。
文件仍保留在仓库中作为历史记录。

用法：python apply_v13_theme.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
HEAD = BUILD / "index_head.html"

# (文件, 起始标记, 结束标记, 说明)
# 顺序即层叠顺序，后面的覆盖前面的。主题层必须在暗色层之前，
# 否则主题层里写死的文字色会盖掉暗色层的浅色文字（踩过这个坑）。
#
# V13/V14 已归档：V15 两层已完整定义全部 142 个令牌（用 plan_layer_removal.py 验证过），
# 保留它们只会让 CSS 规则从 ~700 条涨到 1165 条、颜色从 108 个涨到 204 个。
LAYERS: list[tuple[str, str, str, str]] = [
    ("v13_phases.css", "/* ===== V13 PHASES BEGIN =====", "/* ===== V13 PHASES END ===== */", "V13 流程阶段"),
    ("v13_layout.css", "/* ===== V13 LAYOUT BEGIN =====", "/* ===== V13 LAYOUT END ===== */", "V13 布局"),
    ("v15_theme.css", "/* ===== V15 THEME BEGIN =====", "/* ===== V15 THEME END ===== */", "V15 工业警示风"),
    ("v15_dark.css", "/* ===== V15 DARK BEGIN =====", "/* ===== V15 DARK END ===== */", "V15 暗色"),
    ("v16_tiers.css", "/* ===== V16 TIERS BEGIN =====", "/* ===== V16 TIERS END ===== */", "V16 五档重量"),
    ("v17_palette.css", "/* ===== V17 PALETTE BEGIN =====", "/* ===== V17 PALETTE END ===== */", "V17 深蓝琥珀配色"),
]

# SVG 图标雪碧图：必须在 <body> 开头，<use> 才能解析到。
# 用 HTML 注释标记而不是 CSS 注释，因为它注入的是标签不是样式。
SPRITE_FILE = "v16_icons.svg.html"
SPRITE_BEGIN = "<!-- ===== V16 ICONS BEGIN ===== -->"
SPRITE_END = "<!-- ===== V16 ICONS END ===== -->"

# 已归档的历史层：必须从注入结果里清除，且不再注入
RETIRED: list[tuple[str, str, str]] = [
    ("/* ===== V12 THEME BEGIN =====", "/* ===== V12 THEME END ===== */", "V12 视觉层"),
    ("/* ===== V12 DARK BEGIN =====", "/* ===== V12 DARK END ===== */", "V12 暗色"),
    ("/* ===== V13 THEME BEGIN =====", "/* ===== V13 THEME END ===== */", "V13 设计系统"),
    ("/* ===== V14 THEME BEGIN =====", "/* ===== V14 THEME END ===== */", "V14 政务风"),
    ("/* ===== V13 DARK BEGIN =====", "/* ===== V13 DARK END ===== */", "V13 暗色"),
]


def strip_block(head: str, begin: str, end: str) -> str:
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", re.S)
    return pattern.sub("", head)


def main() -> int:
    if not HEAD.is_file():
        print("[FAIL] 缺少 index_head.html")
        return 1

    head = HEAD.read_text(encoding="utf-8")
    before = len(head)

    # 先全部撤掉，再按顺序追加，保证层序不受历史影响
    for _name, begin, end, _label in LAYERS:
        head = strip_block(head, begin, end)

    # 顺手清掉已废弃的历史层，防止它们被其它脚本重新带进来
    for begin, end, label in RETIRED:
        head, count = re.subn(
            re.escape(begin) + r".*?" + re.escape(end) + r"\n?", "", head, flags=re.S
        )
        if count:
            print(f"[ok] 清除已废弃的{label}（{count} 处）")

    if head.count("</style>") != 1:
        print(f"[FAIL] </style> 命中 {head.count('</style>')} 次，应为 1")
        return 1

    blocks: list[str] = []
    failed = False
    for name, begin, end, label in LAYERS:
        path = BUILD / name
        if not path.is_file():
            print(f"[FAIL] 缺少 {name}")
            failed = True
            continue
        content = path.read_text(encoding="utf-8").strip()
        blocks.append(f"{begin} */\n{content}\n{end}\n")
        print(f"[ok] 装载{label}（{name}，{len(content)} 字符）")

    if failed:
        return 1

    head = head.replace("</style>", "\n".join(blocks) + "</style>")

    # ---- SVG 图标雪碧图：注入到 body 分片（<body> 在 index_body.html 里，不在 head） ----
    body_path = BUILD / "index_body.html"
    if not body_path.is_file():
        print("[FAIL] 缺少 index_body.html")
        return 1
    body = body_path.read_text(encoding="utf-8")
    body = re.sub(
        re.escape(SPRITE_BEGIN) + r".*?" + re.escape(SPRITE_END) + r"\n?",
        "", body, flags=re.S,
    )
    sprite_path = BUILD / SPRITE_FILE
    if not sprite_path.is_file():
        print(f"[FAIL] 缺少 {SPRITE_FILE}")
        return 1
    sprite = sprite_path.read_text(encoding="utf-8").strip()
    body_at = body.find("<body>")
    if body_at < 0:
        print("[FAIL] index_body.html 里找不到 <body>")
        return 1
    insert_at = body_at + len("<body>")
    body = (body[:insert_at] + "\n" + SPRITE_BEGIN + "\n" + sprite + "\n"
            + SPRITE_END + body[insert_at:])
    body_path.write_text(body, encoding="utf-8")
    print(f"[ok] 装载 V16 图标雪碧图（{SPRITE_FILE}，{sprite.count('<symbol')} 个 symbol）")

    HEAD.write_text(head, encoding="utf-8")
    print(f"index_head.html：{before} → {len(head)} 字符")

    # 顺序自检：V13 必须出现在 V12 之后
    order = [head.find(begin) for _n, begin, _e, _l in LAYERS]
    if any(x < 0 for x in order):
        print("[FAIL] 有层没写进去")
        return 1
    if order != sorted(order):
        print(f"[FAIL] 层序不对：{order}")
        return 1
    print("[ok] 层序正确：V12 亮 → V12 暗 → V13 亮 → V13 暗")
    return 0


if __name__ == "__main__":
    sys.exit(main())
