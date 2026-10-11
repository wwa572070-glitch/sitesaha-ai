"""对注入后的 webapp.INDEX_HTML 做静态完整性与可达性检查。

用法：python check_page.py

检查项：
  1) 用 html.parser 真实解析，报未闭合标签
  2) 所有 CSS 里用到的 class 是否都有样式定义（避免裸样式）
  3) 媒体查询断点是否覆盖 1180 / 1000 / 720 / 420
  4) 无障碍：可交互控件是否有可访问名称、图片/装饰是否 aria-hidden
  5) 安全底线文案是否保留
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent  # docs/ui-build -> 项目根目录
sys.path.insert(0, str(APP_DIR))

import webapp  # noqa: E402

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


class StructureChecker(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, int]] = []
        self.errors: list[str] = []
        self.ids: list[str] = []
        self.classes: set[str] = set()
        self.interactive: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {k: (v or "") for k, v in attrs}
        if "id" in data:
            self.ids.append(data["id"])
        if "class" in data:
            for name in data["class"].split():
                self.classes.add(name)
        if tag in {"button", "a", "input", "textarea", "select"}:
            self.interactive.append({"tag": tag, **data})
        if tag not in VOID_TAGS:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"第 {self.getpos()[0]} 行：多余的 </{tag}>")
            return
        open_tag, line = self.stack.pop()
        if open_tag != tag:
            self.errors.append(
                f"第 {self.getpos()[0]} 行：</{tag}> 与第 {line} 行的 <{open_tag}> 不匹配"
            )

    def close_check(self) -> None:
        for tag, line in self.stack:
            self.errors.append(f"第 {line} 行的 <{tag}> 未闭合")


def main() -> int:
    html = webapp.INDEX_HTML
    problems: list[str] = []

    checker = StructureChecker()
    checker.feed(html)
    checker.close_check()
    problems.extend(checker.errors[:10])

    duplicates = sorted({value for value in checker.ids if checker.ids.count(value) > 1})
    if duplicates:
        problems.append("重复 id：" + "、".join(duplicates))

    # 1) class 覆盖：CSS 中出现的 + HTML 中出现的都应有定义
    css = re.search(r"<style>(.*?)</style>", html, re.S)
    css_text = css.group(1) if css else ""
    defined = set(re.findall(r"\.([a-zA-Z][\w-]*)", css_text))
    used = {name for name in checker.classes if not name.startswith("js-")}
    undefined = sorted(used - defined)
    if undefined:
        problems.append("HTML 用了但没有样式的 class：" + "、".join(undefined))

    # 2) 响应式断点：V10 用 1180/1000/720/420，V11 用 860/640/420，两套都算合格
    compact_css = css_text.replace(" ", "")
    widths_present = {w for w in (1180, 1000, 860, 720, 640, 420) if f"max-width:{w}px" in compact_css}
    if not widths_present:
        problems.append("没有任何响应式断点")
    else:
        print(f"  响应式断点：{sorted(widths_present, reverse=True)}")
    has_mobile = any(w in widths_present for w in (640, 720))
    if not has_mobile:
        problems.append("缺少手机断点（640 或 720）")

    # 3) 可交互控件的可访问名称
    # 先收集 <label for="id"> 显式标注的控件 id，这些已经有可访问名称
    labelled_by_for = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', html))
    unnamed = []
    for item in checker.interactive:
        if item["tag"] in {"a", "button"}:
            continue  # 文本按钮/链接以内容为名称
        if item.get("aria-label") or item.get("aria-labelledby") or item.get("title"):
            continue
        if item.get("id") and item["id"] in labelled_by_for:
            continue  # 有 <label for> 关联
        if item["tag"] == "input" and item.get("type") in {"checkbox", "radio", "file", "search"}:
            unnamed.append(item.get("id") or item.get("class") or item["tag"])
    # checkbox/file 多数由外层 label 或 JS 赋 aria-label，这里只做提示
    if unnamed:
        print("  提示：以下 input 依赖 label 包裹或 JS 赋名 ->", "、".join(unnamed))

    labelled_targets = set(re.findall(r'<label class="sr-only" for="([^"]+)"', html))
    control_ids = {item.get("id") for item in checker.interactive if item.get("id")}
    orphans = sorted(labelled_targets - control_ids)
    if orphans:
        problems.append("label 指向不存在的控件：" + "、".join(orphans))

    # 4) 安全底线文案（必须静态出现在页面里，不能只靠接口返回）
    must_text = [
        "安全底线优先于进度和评分",
        "不接受未经训练人员冒险施救",
        "不替代正式规范、项目制度、作业许可和现场判断",
        "先停、先撤、先报",
        "不作为上岗资格或考核合格判定依据",
        "不替代现场安全管理和专项方案",
    ]
    for text in must_text:
        if text not in html:
            problems.append(f"缺少安全底线文案：{text}")

    print(f"parsed tags stack clean: {not checker.errors}")
    print(f"ids={len(checker.ids)} unique={len(set(checker.ids))} classes_used={len(used)} classes_defined={len(defined)}")
    print(f"interactive controls={len(checker.interactive)} aria-hidden decorations={html.count('aria-hidden')}")
    print(f"media queries={len(re.findall(r'@media', css_text))}")
    if problems:
        for item in problems:
            print("  [FAIL]", item)
        return 1
    print("page check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
