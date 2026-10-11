"""把顶部的指标条并进 Hero 内部，压缩首屏。

对标问题：1440x900 下，顶栏(71) + 指标条(78) + 导航(54) 一共吃掉 203px，
再加上 hero 的 258px，用户要滚到 800px 才看到"提问/拍照/应急"三个主入口。
成熟平台的首屏一定把主操作放在第一眼位置。

做法：把 .stat-bar 这个独立横条移进 hero 卡片内部并改成一行紧凑数据，
首屏因此省下约 78px，主入口随之上移到可视范围内。
只改 DOM 位置与样式，id / 脚本逻辑一律不动。

用法：python merge_statbar_into_hero.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
MARK = "<!-- ===== STATBAR MERGED INTO HERO ===== -->"


def take_stat_bar(body: str) -> tuple[str, str]:
    """取出 .stat-bar 整块并从原位置删除。"""
    start = body.find('<div class="stat-bar"')
    if start < 0:
        raise SystemExit("[FAIL] 找不到 .stat-bar")
    depth = 0
    i = start
    while i < len(body):
        nxt = re.search(r"<(/?)div\b[^>]*>", body[i:])
        if not nxt:
            break
        depth += -1 if nxt.group(1) == "/" else 1
        i += nxt.end()
        if depth == 0:
            break
    return body[start:i], body[:start] + body[i:]


def main() -> int:
    body = BODY.read_text(encoding="utf-8")
    if MARK in body:
        print("[跳过] 已经合并过了")
        return 0

    bar, body = take_stat_bar(body)
    inner = re.search(r'<div class="stat-inner">(.*)</div>\s*</div>\s*$', bar, re.S)
    if not inner:
        print("[FAIL] 无法解析指标条内部结构")
        return 1
    cells = inner.group(1).rstrip()
    # 去掉 cells 末尾多出来的一层 </div>
    cells = re.sub(r"</div>\s*$", "", cells.rstrip())

    # 插到 hero 的 chips 之后（hero-sub 之前的位置关系不影响阅读顺序）
    anchor = '<div class="hero-sub">'
    if anchor not in body:
        print("[FAIL] 找不到 hero-sub 锚点")
        return 1

    merged = (
        f'{MARK}\n'
        f'        <div class="hero-stats" role="group" aria-label="知识库统计">\n'
        f'{cells}\n'
        f'        </div>\n\n        '
    )
    body = body.replace(anchor, merged + anchor, 1)

    # 标记 stat-bar 已隐藏（脚本仍在更新其中的数字，只是不再单独占一条横带）
    body = body.replace(
        '<div class="stat-bar">',
        '<div class="stat-bar is-merged">',
        1,
    ) if '<div class="stat-bar">' in body else body

    BODY.write_text(body, encoding="utf-8")
    print("[ok] 指标条已移入 Hero")
    print(f"index_body.html：{len(bar)} 字符的横条被合并")
    return 0


if __name__ == "__main__":
    sys.exit(main())
