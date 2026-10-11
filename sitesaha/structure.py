"""sitesaha/structure.py —— 把视觉/问答的固定格式文本解析成结构化字段。

背景（第 16 轮 §3.3）：
  inspect_image 返回 "- **作业类型**：深基坑开挖"，而前端用 textContent 输出，
  用户看到一堆星号和横杠。已确认改为「服务端结构化返回」。

为什么能可靠解析：我已收紧的 prompt 要求**固定四行结构**
  作业类型 / 可见风险 / 看不清的 / 依据
  所以解析是按已知结构做的，不是通用 Markdown 解析。

设计原则：
  · 解析失败不影响主流程 —— 始终保留 text 字段，前端可回退
  · 不引入任何依赖，纯正则与字符串处理
  · 「可见风险」每条拆成 where / what / action 三部分（前端可做三色徽标）
"""

from __future__ import annotations

import re
from typing import Any

# 章节标题（prompt 里约定的固定结构）
# 章节标题：允许「标题独占一行」或「标题 + 冒号 + 同行内容」两种形态。
# 实测模型两种都会用（如 "**看不清的**：画面左侧…"），
# 只匹配独占一行的写法会把内容误当成上一条风险。
_SECTION_PATTERNS = {
    "work_type": re.compile(r"\*{0,2}作业类型\*{0,2}\s*[:：]\s*(.+)"),
    "risks_header": re.compile(r"\*{0,2}可见风险\*{0,2}\s*[:：]?\s*(.*)$"),
    "uncertain_header": re.compile(r"\*{0,2}看不清的\*{0,2}\s*[:：]?\s*(.*)$"),
    "citations_header": re.compile(r"\*{0,2}依据\*{0,2}\s*[:：]?\s*(.*)$"),
}

_BULLET = re.compile(r"^\s*[-*\u2022]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*\d+[.、)]\s+(.*)$")
# 位置：以「画面X」「图X」「左上/中/右」等开头
_WHERE = re.compile(r"^(画面[^，,：:]{0,12}|图[^，,：:]{0,12}|左上[^，,：:]{0,8}|"
                    r"左[侧边][^，,：:]{0,8}|右[侧边][^，,：:]{0,8}|"
                    r"中[部间][^，,：:]{0,8}|下[部方][^，,：:]{0,8}|上[部方][^，,：:]{0,8}|"
                    r"背[景景][^，,：:]{0,8}|远[处景][^，,：:]{0,8}|近[处景][^，,：:]{0,8})"
                    r"\s*[:：]\s*(.+)$")
_ACTION = re.compile(r"(?:立即动作|安全动作|动作|处置)\s*[:：]\s*(.+)$")
_CITE = re.compile(r"^\s*[-*\u2022]?\s*\[(\d+)\]\s*(.+)$")
_PLAIN_CITE = re.compile(r"^\s*[-*\u2022]?\s*([A-Z]{2,}[A-Z0-9 /.\-]*\d[\w.\-]*)\s*(.*)$")


def _clean(value: str) -> str:
    """去掉 Markdown 标记与多余空白。"""
    text = value.strip()
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"^[-*\u2022]\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" 。；;，,")


def _split_risk(line: str) -> dict[str, str]:
    """把一条风险拆成 位置 / 现象 / 动作。拆不出就整体放进 what。"""
    body = _clean(line)
    item: dict[str, str] = {"where": "", "what": body, "action": ""}

    match = _ACTION.search(body)
    if match:
        item["action"] = _clean(match.group(1))
        body = body[: match.start()].strip(" ，,；;")
        item["what"] = _clean(body)

    where = _WHERE.match(item["what"])
    if where:
        item["where"] = _clean(where.group(1))
        item["what"] = _clean(where.group(2))
    return item


def parse_inspection(text: str) -> dict[str, Any]:
    """把视觉检查回答解析成 {work_type, risks[], uncertain[], citations[]}。

    解析不出任何字段时返回空结构，调用方应回退到纯文本。
    """
    result: dict[str, Any] = {
        "work_type": "",
        "risks": [],
        "uncertain": [],
        "citations": [],
    }
    if not text or not text.strip():
        return result

    section = ""
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        # 结尾免责声明不进结构
        if line.startswith("本页仅辅助识别") or line.startswith("本页指引"):
            continue

        match = _SECTION_PATTERNS["work_type"].search(line)
        if match:
            result["work_type"] = _clean(match.group(1))
            section = ""
            continue
        inline = ""
        matched_section = None
        for key, name in (("risks_header", "risks"),
                          ("uncertain_header", "uncertain"),
                          ("citations_header", "citations")):
            hit = _SECTION_PATTERNS[key].search(line)
            if hit:
                matched_section = name
                inline = (hit.group(1) or "").strip()
                break
        if matched_section:
            section = matched_section
            if not inline:
                continue
            line = inline

        bullet = _BULLET.match(line) or _NUMBERED.match(line)
        body = bullet.group(1) if bullet else line

        if section == "risks":
            item = _split_risk(body)
            if item["what"] or item["action"]:
                result["risks"].append(item)
        elif section == "uncertain":
            cleaned = _clean(body)
            if cleaned:
                result["uncertain"].append(cleaned)
        elif section == "citations":
            cite = _CITE.match(body) or _PLAIN_CITE.match(body)
            if cite:
                groups = cite.groups()
                if len(groups) == 2 and groups[0].isdigit():
                    result["citations"].append({"index": int(groups[0]), "title": _clean(groups[1])})
                else:
                    result["citations"].append({"index": None, "title": _clean(body)})
            else:
                cleaned = _clean(body)
                if cleaned:
                    result["citations"].append({"index": None, "title": cleaned})
        else:
            # 还没进入任何章节，但可能是紧跟作业类型的一行风险（模型有时省略小标题）
            if bullet and ("：" in body or ":" in body):
                item = _split_risk(body)
                if item["where"]:
                    result["risks"].append(item)

    return result


def parse_answer(text: str) -> dict[str, Any]:
    """解析文字问答回答里的引用块（[1] 标准名 / 章节）。

    问答格式不像视觉那样固定，所以只提取能确认的部分：
    行首的 [编号] 引用；其余保持原样由前端展示 text。
    """
    citations: list[dict[str, Any]] = []
    for raw_line in (text or "").split("\n"):
        match = _CITE.match(raw_line.strip())
        if match:
            citations.append({"index": int(match.group(1)), "title": _clean(match.group(2))})
    return {"citations": citations}


def strip_markdown(text: str) -> str:
    """去掉 Markdown 标记，用于生成纯文本版本（复制/朗读场景）。"""
    out_lines: list[str] = []
    for raw_line in (text or "").split("\n"):
        line = raw_line.rstrip()
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"^(\s*)[-*\u2022]\s+", r"\1· ", line)
        out_lines.append(line)
    return "\n".join(out_lines)
