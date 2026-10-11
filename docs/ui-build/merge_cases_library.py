"""把 cases 与 library 两个视图的内容并入 learn，然后删掉空壳。

新架构里「学习与资料」页 = 原 training + cases + library 三页内容。
理由（按用户意图分类）：工人要么在"问安全"，要么在"学习/查资料"，
案例、培训、标准都是"查阅"这一类，不该各占一个顶级导航项。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"


def take_section(body: str, section_id: str) -> tuple[str, str]:
    """取出 <section id="..."> 的内部内容，并把它从 body 里整段删除。"""
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
    whole = body[start:i]
    inner = re.sub(r"^<section\b[^>]*>", "", whole, count=1)
    inner = re.sub(r"</section>$", "", inner, count=1)
    return inner.strip(), body[:start] + body[i:]


def main() -> int:
    body = BODY.read_text(encoding="utf-8")
    before = len(body)

    cases_inner, body = take_section(body, "cases")
    library_inner, body = take_section(body, "library")
    print(f"[ok] 取出 #cases 内部 {len(cases_inner)} 字符")
    print(f"[ok] 取出 #library 内部 {len(library_inner)} 字符")

    # 找到 learn 的 </section> 位置，把内容插到它之前
    start = body.find('<section id="learn"')
    if start < 0:
        print("[FAIL] 找不到 #learn")
        return 1
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
    close_at = i - len("</section>")

    merged = (
        "\n\n      <!-- 原 #cases 内容：真实案例属于「查阅」类 -->\n"
        + cases_inner
        + "\n\n      <!-- 原 #library 内容：标准检索属于「查阅」类 -->\n"
        + library_inner
        + "\n\n    "
    )
    body = body[:close_at] + merged + body[close_at:]

    BODY.write_text(body, encoding="utf-8")
    print(f"\n[ok] 已并入 #learn，index_body.html {before} → {len(body)} 字符")

    sections = re.findall(r'<section id="([^"]+)"', body)
    views = re.findall(r'data-view="([^"]+)"', body)
    print(f"  视图 {len(sections)} 个：{sections}")
    print(f"  导航 {len(views)} 项：{views}")
    if sorted(sections) != sorted(views):
        print(f"  [FAIL] 仍不一致：仅视图 {set(sections) - set(views)}；仅导航 {set(views) - set(sections)}")
        return 1
    print("  [ok] 导航与视图一一对应")
    return 0


if __name__ == "__main__":
    sys.exit(main())
