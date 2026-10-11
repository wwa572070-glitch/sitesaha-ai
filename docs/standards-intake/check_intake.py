"""校验人工录入的标准 Markdown 是否合规、可入库。

用法（在项目根运行）：
    python docs/standards-intake/check_intake.py                 # 校验 docs/standards-intake/*.md
    python docs/standards-intake/check_intake.py <文件或目录>…   # 校验指定路径

为什么需要它：人工录入的标准直接进知识库，一旦写错结构就会静默变成不可检索的数据，
或者更糟——用推测内容冒充标准条款。本脚本把两类问题都拦下来：
  1) 结构问题：标题格式、必备元数据字段、占位符残留
  2) 合规问题：缺少授权说明、缺少免责声明、出现推测性表述

通过后请把文件移到 data/sources/normalized/manual/ 并重建索引，
再用 docs/ui-build/verify_standards.py 交叉校验。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
ROOT = BUILD.parent.parent                       # 项目根
DEFAULT_SOURCE_DIR = BUILD
TARGET_DIR = ROOT / "data" / "sources" / "normalized" / "manual"
TEMPLATE_NAME = "TEMPLATE.md"

# 标题：  # GB 55034-2022 建筑与市政施工现场安全卫生与职业健康通用规范
#         # JGJ 46-2005 施工现场临时用电安全技术规范
# 编号部分要连号码与年份一起捕获，否则会把 "JGJ" 当成完整编号。
CODE_IN_TITLE = r"([A-Z]{2,4}(?:/[A-Z]+)?\s?\d+(?:\.\d+)?(?:-\d{4})?)"
TITLE_PATTERN = re.compile(rf"^#\s+{CODE_IN_TITLE}\s+(.+)$")

# 完整的标准编号（用于显示与二次校验）
FULL_CODE_PATTERN = re.compile(r"^[A-Z]{2,4}(?:/[A-Z]+)?\s?\d+(?:\.\d+)?(?:-\d{4})$")

# 必备的引用行（> 开头）
REQUIRED_FIELDS = {
    "标准状态": re.compile(r"^>\s*标准状态\s*[：:]\s*(\S+)"),
    "版本与实施日期": re.compile(r"^>\s*版本与实施日期\s*[：:]\s*(.+)$"),
    "来源": re.compile(r"^>\s*来源\s*[：:]\s*(.+)$"),
    "来源链接": re.compile(r"^>\s*来源链接\s*[：:]\s*(.+)$"),
    "采集时间": re.compile(r"^>\s*采集时间\s*[：:]\s*(\d{4}-\d{2}-\d{2})"),
    "授权说明": re.compile(r"^>\s*授权说明\s*[：:]\s*(.+)$"),
}

ALLOWED_STATUS = {"现行", "即将实施"}

# 必须出现的结构小节
REQUIRED_SECTIONS = ["适用范围", "新工人需要记住的要点", "免责说明"]

# 推测性表述：不允许用来代替标准原文
SPECULATIVE_PATTERNS = [
    (re.compile(r"应该(?:是|为|符合)?"), "使用「应该」这类不确定表述"),
    (re.compile(r"大概|可能要求|估计要求|似乎规定"), "使用推测性措辞"),
    (re.compile(r"根据经验|一般认为|通常规定为\s*\d"), "用经验或惯例代替条文"),
    (re.compile(r"（\s*待补\s*）|\(\s*待补\s*\)|TODO|TBD|XXX"), "存在未填写的待补占位"),
]

PLACEHOLDER_PATTERN = re.compile(r"TEMPLATE-")


def check_file(path: Path) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    warnings: list[str] = []
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()

    # 1) 占位符残留（模板本身除外）
    if path.name != TEMPLATE_NAME and PLACEHOLDER_PATTERN.search(text):
        leftover = len(PLACEHOLDER_PATTERN.findall(text))
        problems.append(f"仍有 {leftover} 处 TEMPLATE- 占位符未填写")

    # 2) 标题
    title_match = None
    for line in lines:
        if line.startswith("# "):
            title_match = TITLE_PATTERN.match(line)
            break
    if not title_match:
        problems.append("第一个一级标题必须形如「# 标准编号 标准名称」")
    else:
        code, name = title_match.group(1), title_match.group(2).strip()
        if len(name) < 4:
            problems.append(f"标准名称过短：{name!r}")
        if not FULL_CODE_PATTERN.match(code):
            problems.append(
                f"标准编号格式可疑：{code!r}（应形如 JGJ 46-2005 或 GB 55034-2022）"
            )
        warnings.append(f"识别到标准编号 {code}")

    # 3) 必备元数据
    for label, pattern in REQUIRED_FIELDS.items():
        if not any(pattern.match(line) for line in lines):
            problems.append(f"缺少元数据行「> {label}：…」")

    # 4) 状态取值
    status_value = ""
    for line in lines:
        match = REQUIRED_FIELDS["标准状态"].match(line)
        if match:
            status_value = match.group(1).strip()
            break
    if status_value and status_value not in ALLOWED_STATUS:
        problems.append(
            f"标准状态 {status_value!r} 不在允许集合 {sorted(ALLOWED_STATUS)}；"
            "已废止或被替代的标准不要录入"
        )

    # 5) 结构小节
    for section in REQUIRED_SECTIONS:
        if not re.search(rf"^#{{2,3}}\s*{re.escape(section)}", text, re.MULTILINE):
            problems.append(f"缺少必需小节「{section}」")

    # 6) 合规红线
    if "不是标准的完整替代品" not in text and "不替代" not in text:
        problems.append("免责说明里必须写明本文件不能替代正式标准文本")
    if "授权" not in text:
        problems.append("必须写明文本的授权/取得渠道")

    # 7) 推测性表述
    for pattern, reason in SPECULATIVE_PATTERNS:
        if pattern.search(text):
            problems.append(f"发现{reason}，标准条款不允许猜测或补全")

    # 8) 内容量提示（不判失败，只是提醒检索命中率）
    body_chars = len(re.sub(r"\s+", "", text))
    if body_chars < 400:
        warnings.append(f"正文仅约 {body_chars} 字，入库后检索命中率可能偏低")
    if body_chars > 60000:
        warnings.append(f"正文约 {body_chars} 字，建议按章节拆分以便检索")

    return problems, warnings


def collect_targets(args: list[str]) -> list[Path]:
    # 下划线开头的是自测样例与草稿，不参与默认扫描
    def is_candidate(path: Path) -> bool:
        return path.name != TEMPLATE_NAME and not path.name.startswith("_")

    if not args:
        return sorted(p for p in DEFAULT_SOURCE_DIR.glob("*.md") if is_candidate(p))
    targets: list[Path] = []
    for raw in args:
        path = Path(raw)
        if path.is_dir():
            targets.extend(sorted(p for p in path.glob("*.md") if is_candidate(p)))
        elif path.is_file():
            # 显式指定时不做过滤，方便直接校验草稿
            targets.append(path)
        else:
            print(f"[跳过] 路径不存在：{raw}")
    return targets


def main() -> int:
    targets = collect_targets(sys.argv[1:])
    if not targets:
        print("没有找到待校验的 Markdown 文件。")
        print(f"把按 {TEMPLATE_NAME} 填好的文件放到 {DEFAULT_SOURCE_DIR}，或直接传入路径。")
        return 0

    total_problems = 0
    for path in targets:
        problems, warnings = check_file(path)
        status = "通过" if not problems else f"不通过（{len(problems)} 个问题）"
        print(f"\n=== {path.name} — {status} ===")
        for item in warnings:
            print(f"  [提示] {item}")
        for item in problems:
            print(f"  [问题] {item}")
        total_problems += len(problems)

    print()
    if total_problems:
        print(f"共 {len(targets)} 个文件，发现 {total_problems} 个问题，未通过。")
        print("修好后重新运行；全部通过再执行下一步：")
        print(f"  1) 把文件移到 {TARGET_DIR.relative_to(ROOT)}")
        print("  2) python scripts/init_db.py        # 重建索引")
        print("  3) python docs/ui-build/verify_standards.py")
        return 1

    print(f"共 {len(targets)} 个文件，全部通过校验。")
    print("下一步：")
    print(f"  1) 把文件移到 {TARGET_DIR.relative_to(ROOT)}")
    print("  2) python scripts/init_db.py")
    print("  3) python docs/ui-build/verify_standards.py")
    print("  4) 起服务后用 /api/status 核对 documents / chunks 增长")
    return 0


if __name__ == "__main__":
    sys.exit(main())
