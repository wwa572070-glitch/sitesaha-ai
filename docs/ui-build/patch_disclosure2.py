"""§3 收尾：首页安全底线 + 学习页次要区块折叠（第 20 轮 P0）。

学习与资料页 6000px 太长，10 个区块平铺。把「次要参考类」收进折叠：
  标准现行状态 / 在线模型与培训上下文 / 知识库状态 / 检索与合规说明

保留默认展开的（用户主要来看这些）：
  培训路线 / 五步路线 / 学习积分 / 工种专项 / 知识测验 / 案例库

用法：python patch_disclosure2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"

TAG = re.compile(r"<(/?)(div)\b[^>]*?(/?)>")


def block_containing(html: str, needle: str, open_marker: str) -> tuple[int, int] | None:
    """找到包含 needle 的那个 open_marker 开头的 div 块边界。"""
    index = html.find(needle)
    if index < 0:
        return None
    start = html.rfind(open_marker, 0, index)
    if start < 0:
        return None
    depth = 0
    position = start
    while position < len(html):
        match = TAG.search(html, position)
        if not match:
            break
        position = match.end()
        if match.group(1) == "/":
            depth -= 1
            if depth == 0:
                return start, match.end()
        elif match.group(3) != "/":
            depth += 1
    return None


def wrap(html: str, span: tuple[int, int], summary: str, hint: str) -> str:
    start, end = span
    block = html[start:end]
    hint_html = f'<span class="disclosure-hint">{hint}</span>' if hint else ""
    return (
        html[:start]
        + '<details class="disclosure">\n'
        + f'  <summary>{summary}{hint_html}</summary>\n'
        + '  <div class="disclosure-body">\n' + block + '\n  </div>\n'
        + '</details>'
        + html[end:]
    )


TARGETS = [
    ("安全底线", '<div class="tier-l4">', "安全底线（三条，必读）", "展开看全部"),
    ("标准现行状态", '<div class="panel"', "标准现行状态", "46 部 · 现行 / 即将实施"),
    ("在线模型与培训上下文", '<div class="panel"', "在线模型与培训上下文", "技术信息"),
    ("知识库状态", '<div class="panel"', "知识库状态", "文档 / 片段 / 服务"),
    ("检索与合规说明", '<div class="panel"', "检索与合规说明", "使用边界"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    body = BODY.read_text(encoding="utf-8")
    # 学过的折叠：先全部展开成统一形态再处理，避免重复包裹
    for needle, marker, summary, hint in TARGETS:
        already = f'<summary>{summary}'
        if already in body:
            print(f"  [跳过] {summary} 已折叠")
            continue
        span = block_containing(body, needle, marker)
        if not span:
            print(f"  [跳过] 找不到「{needle}」")
            continue
        size = span[1] - span[0]
        body = wrap(body, span, summary, hint)
        applied += 1
        print(f"  [ok] {summary} 已折叠（原块 {size} 字符）")

    if body.count(chr(92)):
        print("[FAIL] body 含反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
