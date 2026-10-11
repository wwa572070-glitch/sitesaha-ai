"""清掉 V11 结构里已不存在的侧栏与领域分布引用，并把残留旧类名换成新类名。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
FILES = [BUILD / "index_script_a.js", BUILD / "index_script_b.js"]

# 简单替换
SIMPLE = [
    ('make("div", "source-meta"', 'make("div", "src"', "来源行类名"),
    ('"source-meta"', '"src"', "来源行类名(字符串)"),
]


def strip_side_documents(text: str) -> tuple[str, str]:
    """删掉 renderSideDocuments 函数定义。"""
    marker = "    function renderSideDocuments(documents) {"
    start = text.find(marker)
    if start < 0:
        return text, "未找到 renderSideDocuments 定义"
    end = text.find("\n    }\n", start)
    if end < 0:
        return text, "未找到 renderSideDocuments 结束位置"
    end += len("\n    }\n")
    return text[:start] + text[end:], ""


def strip_domain_distribution(text: str) -> tuple[str, str]:
    """删掉 renderDomainDistribution 函数定义（它依赖已移除的 sideDomains）。"""
    marker = "    function renderDomainDistribution(documents) {"
    start = text.find(marker)
    if start < 0:
        return text, "未找到 renderDomainDistribution 定义"
    # 找到函数结尾：下一个顶层 "    }\n" 之后紧跟空行
    end = text.find("\n    }\n", start)
    if end < 0:
        return text, "未找到 renderDomainDistribution 结束位置"
    end += len("\n    }\n")
    return text[:start] + text[end:], ""


def main() -> int:
    problems: list[str] = []

    for path in FILES:
        text = path.read_text(encoding="utf-8")
        original = text

        for old, new, label in SIMPLE:
            if old == new:
                continue
            count = text.count(old)
            if count:
                text = text.replace(old, new)
                print(f"  {path.name}: {label} ×{count}")

        if "renderSideDocuments" in text:
            text, err = strip_side_documents(text)
            if err:
                problems.append(f"{path.name}: {err}")
            else:
                print(f"  {path.name}: 已删除 renderSideDocuments 定义")

        if "renderDomainDistribution" in text:
            text, err = strip_domain_distribution(text)
            if err:
                problems.append(f"{path.name}: {err}")
            else:
                print(f"  {path.name}: 已删除 renderDomainDistribution 定义")

        # 删除对已移除函数的调用（逐个按行处理）
        lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped in {
                "renderSideDocuments(allDocuments);",
                "renderDomainDistribution(allDocuments);",
                "renderDomainDistribution(categories);",
            }:
                print(f"  {path.name}: 删除调用 {stripped}")
                continue
            lines.append(line)
        text = "\n".join(lines)

        if text != original:
            path.write_text(text, encoding="utf-8")
            print(f"[ok] {path.name} 已更新（{text.count(chr(10)) + 1} 行）")

    leftovers: list[str] = []
    for path in FILES:
        text = path.read_text(encoding="utf-8")
        for marker in ("sideDocuments", "sideDomains", "renderSideDocuments", "renderDomainDistribution", "source-meta"):
            if marker in text:
                leftovers.append(f"{path.name}: {marker}")

    if problems:
        print("\n问题：")
        for item in problems:
            print("  -", item)
    if leftovers:
        print("\n仍有残留：")
        for item in leftovers:
            print("  -", item)
        return 1
    print("\n[OK] 侧栏与领域分布引用已清理干净")
    return 0


if __name__ == "__main__":
    sys.exit(main())
