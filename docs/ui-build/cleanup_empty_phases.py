"""清理首页里因为模块搬迁而变空的阶段块。

搬迁后首页残留了 4 个只带标题、没有内容的阶段：
  「现场作业」「出事怎么办」「培训与测验」「查标准与知识库」
它们对应的模块已经进了目标页，这些空壳必须删掉，否则页面末尾挂着一串
无内容的标题，比不改还乱。

用法：python cleanup_empty_phases.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"


def section_span(body: str, section_id: str) -> tuple[int, int]:
    start = body.find(f'<section id="{section_id}"')
    if start < 0:
        raise SystemExit(f"找不到 #{section_id}")
    depth = 0
    i = start
    while i < len(body):
        nxt = re.search(r"<(/?)section\b[^>]*>", body[i:])
        if not nxt:
            break
        depth += -1 if nxt.group(1) == "/" else 1
        i += nxt.end()
        if depth == 0:
            break
    return body.find(">", start) + 1, i - len("</section>")


PHASE = re.compile(
    r'\s*<div class="phase">\s*'
    r'<div class="phase-head">.*?</div>\s*'
    r'<div class="phase-rule"></div>\s*'
    r'(?:<(div|p|span)[^>]*>\s*</\1>\s*)*'
    r'</div>',
    re.S,
)


def main() -> int:
    body = BODY.read_text(encoding="utf-8")
    before = len(body)
    open_at, close_at = section_span(body, "home")
    home = body[open_at:close_at]

    found = PHASE.findall(home)
    titles = re.findall(r'class="phase-title">([^<]*)<', home)
    print(f"首页阶段标题 {len(titles)} 个：{titles}")

    home_new, count = PHASE.subn("", home)
    print(f"删除空阶段块 {count} 个")

    # 二次清理：剩下的 phase 容器若既无 panel 也无文本，也删掉
    def drop_if_empty(match: re.Match[str]) -> str:
        inner = match.group(0)
        if 'class="panel' in inner or 'id="' in inner:
            return inner
        return ""

    home_new = re.sub(r'<div class="phase(?:-single|-cols|-main|-side)?">.*?</div>\s*</div>',
                      drop_if_empty, home_new, flags=re.S)

    body = body[:open_at] + home_new + body[close_at:]
    BODY.write_text(body, encoding="utf-8")

    left = re.findall(r'class="phase-title">([^<]*)<', home_new)
    print(f"\nindex_body.html {before} → {len(body)} 字符")
    print(f"首页剩余阶段标题 {len(left)} 个：{left}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
